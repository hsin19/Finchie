import base64
import json
import logging
import os
import os.path
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from finchie_data_pipeline.utils.logging_utils import setup_console_logger
from finchie_data_pipeline.utils.type_utils import coerce_to_instance

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]  # Read-only permission, only reading emails


@dataclass
class GmailConfig:
    base64_token: str | None = None
    credentials_file: str = "config/secret/gmail/credentials.json"
    token_file: str = "config/secret/gmail/token.json"
    output_dir: str = "data/extract/gmail"
    query: str = ""
    days_ago: int = 30


logger = logging.getLogger(__name__)

__all__ = ["extract_gmail_messages"]


class GmailExtractorError(Exception):
    """Exception raised for errors in the Gmail extraction process."""

    pass


def _get_credentials(config: GmailConfig) -> Credentials | None:
    """
    Get Gmail API credentials.
    First try to read from token in config, if failed then read from file.

    The token in config is expected to be a base64 encoded JSON string.
    """
    if config.base64_token:
        try:
            decoded_bytes = base64.b64decode(config.base64_token)
            token_json = json.loads(decoded_bytes.decode("utf-8"))
            creds = Credentials.from_authorized_user_info(token_json, SCOPES)
            if creds.valid:
                logger.info("Credentials loaded from base64 encoded token")
                return creds
        except Exception as e:
            logger.error("Error loading credentials from token: %s", e)

    creds = None
    if os.path.exists(config.token_file):
        creds = Credentials.from_authorized_user_file(config.token_file, SCOPES)
        logger.info("Credentials loaded from file: %s", config.token_file)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
            logger.debug("Credentials refreshed")
        else:
            flow = InstalledAppFlow.from_client_secrets_file(config.credentials_file, SCOPES)
            creds = flow.run_local_server(port=0)
            logger.debug("Credentials obtained from user authentication")
        with open(config.token_file, "w") as token_file:
            token_file.write(creds.to_json())
            logger.debug("Credentials saved to file: %s", config.token_file)
    return creds


def _save_message_data(service: Any, msg_id: str, msg_dir: str) -> None:
    """
    Get email details, content and attachments, and save to the specified directory.
    """
    msg = service.users().messages().get(userId="me", id=msg_id, format="full").execute()

    with open(os.path.join(msg_dir, "message.json"), "w", encoding="utf-8") as f:
        json.dump(msg, f, indent=4, ensure_ascii=False)

    payload = msg["payload"]
    if "parts" in payload:
        parts = payload["parts"]
        _save_message_parts(service, msg_id, msg_dir, parts)
    elif "body" in payload:
        _save_message_body(payload["body"], msg_dir)


def _save_message_parts(service: Any, msg_id: str, msg_dir: str, parts: list[dict[str, Any]]) -> None:
    """Recursively process email parts (including embedded HTML, plain text)."""
    for part in parts:
        _save_message_body(part, msg_dir)
        _save_attachment(service, msg_id, part, msg_dir)
        if "parts" in part:
            _save_message_parts(service, msg_id, msg_dir, part["parts"])


def _save_message_body(part: dict[str, Any], msg_dir: str) -> None:
    """Save the email body content."""
    if "body" not in part:
        return

    body = part["body"]
    mime_type = part.get("mimeType")

    if "data" not in body:
        return
    try:
        data = base64.urlsafe_b64decode(body["data"].encode("UTF-8")).decode("UTF-8")
    except UnicodeDecodeError:
        data = base64.urlsafe_b64decode(body["data"].encode("UTF-8"))

    if mime_type == "text/html":
        with open(os.path.join(msg_dir, "body.html"), "w", encoding="utf-8") as f:
            f.write(data)
    elif mime_type == "text/plain" or mime_type is None:
        with open(os.path.join(msg_dir, "body.txt"), "w", encoding="utf-8") as f:
            f.write(data)
    else:
        logger.warning("Unknown MIME type %s, saving as raw data.", mime_type)
        with open(os.path.join(msg_dir, "body_raw"), "wb") as f:
            f.write(data)


def _save_attachment(service: Any, msg_id: str, part: dict[str, Any], msg_dir: str) -> None:
    """Save email attachments."""
    file_name = part.get("filename")
    if not file_name:
        return

    file_name = os.path.basename(file_name)
    if not file_name:
        return

    mime_type = part.get("mimeType")
    if mime_type in ["application/x-pkcs7-signature", "application/pkcs7-signature"]:
        logger.debug("Skipping attachment '%s' with MIME type '%s'", file_name, mime_type)
        return

    body = part.get("body", {})
    if "attachmentId" not in body:
        logger.warning("Attachment '%s' does not have attachmentId.", file_name)
        return

    attachment_id = body["attachmentId"]

    headers = part.get("headers", [])
    content_disposition = _get_header(headers, "Content-Disposition")
    if "attachment" not in content_disposition.lower():
        logger.debug("Skipping attachment '%s' with Content Disposition is '%s'", file_name, content_disposition)
        return

    try:
        file_data = service.users().messages().attachments().get(userId="me", messageId=msg_id, id=attachment_id).execute()
        raw = base64.urlsafe_b64decode(file_data["data"].encode("UTF-8"))
        file_path = os.path.join(msg_dir, file_name)
        with open(file_path, "wb") as f:
            f.write(raw)
        logger.debug("Attachment '%s' saved to %s", part["filename"], file_path)
    except HttpError as error:
        logger.error("Error downloading attachment '%s': %s", part["filename"], error)


def _get_header(headers: list[dict[str, str]], name: str) -> str:
    for h in headers:
        if h.get("name", "").lower() == name.lower():
            return h.get("value", "")
    return ""


def extract_gmail_messages(config: GmailConfig | dict | None = None) -> list[str]:
    """
    Extract Gmail messages that match the query criteria and save them to local directories.

    Args:
        config (GmailConfig, dict, optional): If None, a default config will be created.

    Returns:
        List[str]: List of paths to all extracted message folders.

    Raises:
        GmailExtractorError: When credentials cannot be obtained or no matching messages are found.
        HttpError: When Gmail API calls fail.
        IOError: When file read/write operations fail.
        Other exceptions that might occur during processing will be propagated.
    """
    config = coerce_to_instance(config, GmailConfig)

    base_query = config.query

    today = datetime.now()
    start_date = today - timedelta(days=config.days_ago)

    start_date_str = start_date.strftime("%Y/%m/%d")

    date_filter = f" after:{start_date_str}"
    search_query = base_query + date_filter if base_query else date_filter.strip()

    logger.debug("Using search query: %s", search_query)

    if not search_query:
        raise GmailExtractorError("No query provided. Please specify a search query in the config.")

    creds = _get_credentials(config)
    if not creds:
        raise GmailExtractorError("Failed to obtain credentials.")

    service = build("gmail", "v1", credentials=creds)
    logger.debug("Gmail API service initialized.")

    results = service.users().messages().list(userId="me", q=search_query).execute()
    messages = results.get("messages", [])
    logger.debug("Found %d messages.", len(messages))

    if not messages:
        logger.info("No messages found with the specified criteria.")
        return []

    tstamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    message_folders = []

    for message in messages:
        logger.debug("Processing message: %s", message["id"])
        msg_dir = os.path.join(config.output_dir, tstamp, message["id"])
        os.makedirs(msg_dir, exist_ok=True)
        logger.debug("Message directory created: %s", msg_dir)

        _save_message_data(service, message["id"], msg_dir)
        message_folders.append(msg_dir)

    logger.info("Successfully processed %d messages", len(messages))
    return message_folders


if __name__ == "__main__":  # pragma: no cover
    setup_console_logger(logger)

    base64_token = ""

    config = GmailConfig(base64_token=base64_token, query="label:bill", days_ago=25)
    message_folders = extract_gmail_messages(config=config)
    print(f"Successfully extracted data to: {', '.join(message_folders)}")
