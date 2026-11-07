"""Turn an uploaded document (e-mail or bare PDF) into its PDF attachments."""

import email
import email.policy
from dataclasses import dataclass
from email.message import EmailMessage

from finchie_parser.errors import InvalidDocumentError, UnsupportedDocumentError

PDF = "application/pdf"
EMAIL = "message/rfc822"


@dataclass(frozen=True)
class Attachment:
    filename: str
    data: bytes


def extract_pdfs(filename: str, content_type: str, content: bytes) -> list[Attachment]:
    if not content:
        raise InvalidDocumentError("document is empty")
    if content.startswith(b"%PDF"):
        return [Attachment(filename or "document.pdf", content)]
    if content_type == PDF:
        raise InvalidDocumentError("content type says PDF but the bytes are not one")
    if content_type in (EMAIL, "") or filename.lower().endswith(".eml"):
        return _from_email(content)
    raise UnsupportedDocumentError(f"unsupported content type {content_type!r}")


def _from_email(content: bytes) -> list[Attachment]:
    message = email.message_from_bytes(content, policy=email.policy.default)
    if not isinstance(message, EmailMessage) or not message.keys():
        raise InvalidDocumentError("not an e-mail message")
    attachments = []
    for part in message.walk():
        if part.is_multipart():
            continue
        name = part.get_filename() or ""
        # Banks send PDFs as application/octet-stream as often as application/pdf.
        if part.get_content_type() != PDF and not name.lower().endswith(".pdf"):
            continue
        data = part.get_payload(decode=True)
        if isinstance(data, bytes) and data.startswith(b"%PDF"):
            attachments.append(Attachment(name or "attachment.pdf", data))
    return attachments
