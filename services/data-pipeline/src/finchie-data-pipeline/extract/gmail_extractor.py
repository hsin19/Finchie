from __future__ import print_function

import os
import os.path
import logging
import sys
import json
import base64
from datetime import datetime
from dataclasses import dataclass
from typing import Dict, List, Any, Union

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly"
]  # Read-only permission, only reading emails


@dataclass
class GmailConfig:
    base64_token: str | None = None
    credentials_file: str = "config/secret/gmail/credentials.json"
    token_file: str = "config/secret/gmail/token.json"
    output_dir: str = "data/extract/gmail"


logger = logging.getLogger(__name__)

__all__ = ["process_gmail_messages"]


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
            logger.error(f"Error loading credentials from token: {e}")

    # Read from file
    creds = None
    if os.path.exists(config.token_file):
        creds = Credentials.from_authorized_user_file(config.token_file, SCOPES)
        logger.info(f"Credentials loaded from file: {config.token_file}")

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
            logger.debug("Credentials refreshed")
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                config.credentials_file, SCOPES
            )
            creds = flow.run_local_server(port=0)
            logger.debug(f"Credentials obtained from user authentication")
        with open(config.token_file, "w") as token_file:
            token_file.write(creds.to_json())
            logger.debug(f"Credentials saved to file: {config.token_file}")
    return creds


def _save_message_data(service: Any, msg_id: str, msg_dir: str) -> None:
    """
    Get email details, content and attachments, and save to the specified directory.
    """
    msg = (
        service.users().messages().get(userId="me", id=msg_id, format="full").execute()
    )

    # Save complete email information in JSON format
    with open(os.path.join(msg_dir, "message.json"), "w", encoding="utf-8") as f:
        json.dump(msg, f, indent=4, ensure_ascii=False)

    # Process email content
    payload = msg["payload"]
    if "parts" in payload:
        parts = payload["parts"]
        _save_message_parts(service, msg_id, msg_dir, parts)
    elif "body" in payload:
        _save_message_body(payload["body"], msg_dir)


def _save_message_parts(
    service: Any, msg_id: str, msg_dir: str, parts: List[Dict[str, Any]]
) -> None:
    """Recursively process email parts (including embedded HTML, plain text)."""
    for part in parts:
        _save_message_body(part, msg_dir)
        _save_attachment(service, msg_id, part, msg_dir)
        if "parts" in part:
            _save_message_parts(service, msg_id, msg_dir, part["parts"])


def _save_message_body(part: Dict[str, Any], msg_dir: str) -> None:
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
        logger.warning(f"Unknown MIME type {mime_type}, saving as raw data.")
        with open(os.path.join(msg_dir, "body_raw"), "wb") as f:
            f.write(data)


def _save_attachment(
    service: Any, msg_id: str, part: Dict[str, Any], msg_dir: str
) -> None:
    """Save email attachments."""
    file_name = part.get("filename")
    if not file_name:
        return

    # Safely handle filename to avoid path injection
    file_name = os.path.basename(file_name)
    if not file_name:
        return

    mime_type = part.get("mimeType")
    if mime_type in ["application/x-pkcs7-signature", "application/pkcs7-signature"]:
        logger.debug(f"Skipping attachment '{file_name}' with MIME type '{mime_type}'")
        return

    body = part.get("body", {})
    if "attachmentId" not in body:
        logger.warning(f"Attachment '{file_name}' does not have attachmentId.")
        return

    attachment_id = body["attachmentId"]

    # Content-Disposition must be 'attachment' (not 'inline')
    headers = part.get("headers", [])
    content_disposition = _get_header(headers, "Content-Disposition")
    if "attachment" not in content_disposition.lower():
        logger.debug(
            f"Skipping attachment '{file_name}' with Content Disposition is '{content_disposition}'"
        )
        return

    try:
        file_data = (
            service.users()
            .messages()
            .attachments()
            .get(userId="me", messageId=msg_id, id=attachment_id)
            .execute()
        )
        raw = base64.urlsafe_b64decode(file_data["data"].encode("UTF-8"))
        file_path = os.path.join(msg_dir, file_name)
        with open(file_path, "wb") as f:
            f.write(raw)
        logger.debug(f"Attachment '{part['filename']}' saved to {file_path}")
    except HttpError as error:
        logger.error(f"Error downloading attachment '{part['filename']}': {error}")


def _get_header(headers: List[Dict[str, str]], name: str) -> str:
    for h in headers:
        if h.get("name", "").lower() == name.lower():
            return h.get("value", "")
    return ""


def process_gmail_messages(query: str, config: GmailConfig | None = None) -> List[str]:
    """
    Extract Gmail messages that match the query criteria and save them to local directories.

    Args:
        query (str): Gmail query string for filtering emails. Example: "label:bill after:2023/01/01"
        config (GmailConfig, optional): Gmail access configuration. If None, a default config will be created.

    Returns:
        List[str]: List of paths to all extracted message folders.

    Raises:
        GmailExtractorError: When credentials cannot be obtained or no matching messages are found.
        HttpError: When Gmail API calls fail.
        IOError: When file read/write operations fail.
        Other exceptions that might occur during processing will be propagated.
    """
    if config is None:
        config = GmailConfig()

    creds = _get_credentials(config)
    if not creds:
        raise GmailExtractorError("Failed to obtain credentials.")

    # Create Gmail API service object.
    service = build("gmail", "v1", credentials=creds)
    logger.debug("Gmail API service initialized.")

    # Call Gmail API to list messages matching the criteria.
    results = service.users().messages().list(userId="me", q=query).execute()
    messages = results.get("messages", [])
    logger.debug(f"Found {len(messages)} messages.")

    if not messages:
        logger.info("No messages found with the specified criteria.")
        return []

    tstamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    message_folders = []

    for message in messages:
        logger.debug(f"Processing message: {message['id']}")
        msg_dir = os.path.join(config.output_dir, tstamp, message["id"])
        os.makedirs(msg_dir, exist_ok=True)
        logger.debug(f"Message directory created: {msg_dir}")

        _save_message_data(service, message["id"], msg_dir)
        message_folders.append(msg_dir)

    logger.info(f"Successfully processed {len(messages)} messages")
    return message_folders


if __name__ == "__main__":
    # Set up logging
    logger.setLevel(logging.DEBUG)
    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    base64_token = ""
    # with open("config/secret/gmail/token.json", "r") as f:
    #     token_json = json.load(f)
    # base64_token = base64.b64encode(json.dumps(token_json).encode("utf-8")).decode("utf-8")

    message_folders = process_gmail_messages(
        "label:bill after:2025/3/01 before:2025/3/25",
        GmailConfig(
            base64_token=base64_token
        ),
    )
    print(f"Successfully extracted data to: {', '.join(message_folders)}")
