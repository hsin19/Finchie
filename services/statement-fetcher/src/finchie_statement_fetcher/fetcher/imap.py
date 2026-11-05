import email
import hashlib
import imaplib
import json
import logging
import os
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from email.message import Message

from finchie_statement_fetcher.utils.logging_utils import setup_console_logger
from finchie_statement_fetcher.utils.type_utils import coerce_to_instance

logger = logging.getLogger(__name__)


@dataclass
class ImapConfig:
    host: str = "imap.gmail.com"
    port: int = 993
    user: str = ""
    password: str | None = None
    password_env_var: str = "IMAP_PASSWORD"
    mailbox: str = "INBOX"
    query: str = ""
    days_ago: int = 30
    output_dir: str = "data/fetched_result/imap"
    use_gmail_search: bool = True
    timeout: int = 30


class ImapFetcherError(Exception):
    """Exception raised for errors in the IMAP fetch process."""

    pass


def _resolve_password(config: ImapConfig) -> str | None:
    """Look up password from env var first, then fall back to config field."""
    if config.password_env_var:
        env_password = os.environ.get(config.password_env_var)
        if env_password:
            logger.debug("Password loaded from env var %s", config.password_env_var)
            return env_password
    if config.password:
        logger.debug("Password loaded from config (env var %s not set)", config.password_env_var or "<none>")
        return config.password
    return None


def _build_search_criteria(config: ImapConfig) -> list[str]:
    """Assemble IMAP SEARCH criteria honouring days_ago and the configured query."""
    since_str = (datetime.now() - timedelta(days=config.days_ago)).strftime("%d-%b-%Y")
    criteria: list[str] = []

    query = config.query.strip() if config.query else ""
    if query:
        if config.use_gmail_search:
            # X-GM-RAW lets Gmail's IMAP accept its native search syntax (label:, has:, from:, …)
            escaped = query.replace("\\", "\\\\").replace('"', '\\"')
            criteria.extend(["X-GM-RAW", f'"{escaped}"'])
        else:
            criteria.append(query)

    criteria.extend(["SINCE", since_str])
    return criteria


def _sanitize_for_filename(value: str, fallback: str) -> str:
    if not value:
        return fallback
    cleaned = re.sub(r"[^A-Za-z0-9._-]", "_", value).strip("_")
    return cleaned or fallback


def _message_folder_name(uid: bytes, msg: Message) -> str:
    """Stable folder name per message — prefer Message-ID, fall back to UID."""
    raw_message_id = msg.get("Message-ID", "")
    msg_id = raw_message_id.strip().strip("<>") if raw_message_id else ""
    sanitized = _sanitize_for_filename(msg_id, fallback=uid.decode("utf-8", errors="ignore"))
    if len(sanitized) > 80:
        digest = hashlib.sha1(sanitized.encode("utf-8")).hexdigest()[:8]
        sanitized = sanitized[:60] + "_" + digest
    return sanitized


def _save_attachment(part: Message, filename: str, msg_dir: str) -> None:
    content_type = part.get_content_type()
    if content_type in ("application/pkcs7-signature", "application/x-pkcs7-signature"):
        logger.debug("Skipping signature attachment '%s'", filename)
        return

    payload = part.get_payload(decode=True)
    if not payload:
        logger.warning("Attachment '%s' has no payload", filename)
        return

    safe_name = os.path.basename(filename)
    if not safe_name:
        logger.warning("Empty filename for attachment in %s", msg_dir)
        return

    file_path = os.path.join(msg_dir, safe_name)
    with open(file_path, "wb") as f:
        f.write(payload)
    logger.debug("Attachment '%s' saved to %s", filename, file_path)


def _save_message(msg: Message, msg_dir: str) -> None:
    """Walk MIME parts; write attachments + extracted bodies + a metadata sidecar."""
    metadata = {
        "subject": str(msg.get("Subject", "")),
        "from": str(msg.get("From", "")),
        "to": str(msg.get("To", "")),
        "date": str(msg.get("Date", "")),
        "message_id": str(msg.get("Message-ID", "")),
    }

    body_text_parts: list[str] = []
    body_html_parts: list[str] = []

    for part in msg.walk():
        if part.is_multipart():
            continue

        content_disposition = (part.get("Content-Disposition") or "").lower()
        filename = part.get_filename()
        content_type = part.get_content_type()

        if "attachment" in content_disposition and filename:
            _save_attachment(part, filename, msg_dir)
            continue

        if content_type == "text/plain":
            payload = part.get_payload(decode=True)
            if payload:
                charset = part.get_content_charset() or "utf-8"
                body_text_parts.append(payload.decode(charset, errors="replace"))
        elif content_type == "text/html":
            payload = part.get_payload(decode=True)
            if payload:
                charset = part.get_content_charset() or "utf-8"
                body_html_parts.append(payload.decode(charset, errors="replace"))

    with open(os.path.join(msg_dir, "message.json"), "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=4, ensure_ascii=False)

    if body_text_parts:
        with open(os.path.join(msg_dir, "body.txt"), "w", encoding="utf-8") as f:
            f.write("\n".join(body_text_parts))
    if body_html_parts:
        with open(os.path.join(msg_dir, "body.html"), "w", encoding="utf-8") as f:
            f.write("\n".join(body_html_parts))


def fetch_imap_messages(config: ImapConfig | dict | None = None) -> list[str]:
    """
    Fetch messages from an IMAP mailbox and save each one (attachments + body + metadata)
    into a per-message folder under ``config.output_dir``.

    Drop-in alternative to :func:`fetch_gmail_messages`. Pairs with a Gmail App Password
    so automation keeps running without OAuth's 7-day token expiry in Testing mode.

    Returns:
        List of folder paths, one per processed message.

    Raises:
        ImapFetcherError: on misconfiguration, connection failure, or auth failure.
    """
    config = coerce_to_instance(config, ImapConfig) or ImapConfig()

    if not config.user:
        raise ImapFetcherError("No IMAP user configured.")

    password = _resolve_password(config)
    if not password:
        raise ImapFetcherError(
            f"No IMAP password available. Set ${config.password_env_var or 'IMAP_PASSWORD'} or provide 'password' in config."
        )

    logger.debug("Connecting to %s:%d as %s", config.host, config.port, config.user)
    try:
        client = imaplib.IMAP4_SSL(config.host, config.port, timeout=config.timeout)
    except Exception as e:
        raise ImapFetcherError(f"Failed to connect to {config.host}:{config.port}: {e}") from e

    try:
        try:
            client.login(config.user, password)
        except imaplib.IMAP4.error as e:
            raise ImapFetcherError(f"IMAP login failed: {e}") from e

        logger.debug("Logged in as %s", config.user)

        status, _ = client.select(config.mailbox, readonly=True)
        if status != "OK":
            raise ImapFetcherError(f"Cannot select mailbox {config.mailbox!r}")

        criteria = _build_search_criteria(config)
        logger.debug("Search criteria: %s", criteria)

        status, data = client.uid("SEARCH", None, *criteria)
        if status != "OK":
            raise ImapFetcherError(f"IMAP search failed: status={status}")

        uids = data[0].split() if data and data[0] else []
        logger.debug("Found %d messages.", len(uids))

        if not uids:
            logger.info("No messages found with the specified criteria.")
            return []

        tstamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        message_folders: list[str] = []

        for uid in uids:
            status, msg_data = client.uid("FETCH", uid, "(RFC822)")
            if status != "OK" or not msg_data or not msg_data[0]:
                logger.warning("Failed to fetch UID %s", uid)
                continue

            envelope = msg_data[0]
            if not isinstance(envelope, tuple) or len(envelope) < 2:
                logger.warning("Unexpected fetch payload for UID %s: %r", uid, envelope)
                continue

            raw_email = envelope[1]
            msg = email.message_from_bytes(raw_email)

            folder_name = _message_folder_name(uid, msg)
            msg_dir = os.path.join(config.output_dir, tstamp, folder_name)
            os.makedirs(msg_dir, exist_ok=True)

            _save_message(msg, msg_dir)
            message_folders.append(msg_dir)
            logger.debug("Saved message UID=%s to %s", uid.decode("utf-8", errors="ignore"), msg_dir)

        logger.info("Successfully processed %d messages", len(message_folders))
        return message_folders
    finally:
        try:
            client.logout()
        except Exception:
            logger.debug("IMAP logout failed (already disconnected?)", exc_info=True)


if __name__ == "__main__":  # pragma: no cover
    setup_console_logger(logger)

    config = ImapConfig(
        user=os.environ.get("IMAP_USER", ""),
        query="label:bill",
        days_ago=25,
    )
    folders = fetch_imap_messages(config=config)
    print(f"Successfully extracted data to: {', '.join(folders)}")
