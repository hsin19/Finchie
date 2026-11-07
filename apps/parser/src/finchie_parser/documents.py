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


def classify(filename: str, content_type: str, content: bytes) -> str:
    """PDF or EMAIL: the bytes decide first, then the declared type or the file name."""
    if not content:
        raise InvalidDocumentError("document is empty")
    if content.startswith(b"%PDF"):
        return PDF
    if content_type == PDF:
        raise InvalidDocumentError("content type says PDF but the bytes are not one")
    if content_type in (EMAIL, "") or filename.lower().endswith(".eml"):
        return EMAIL
    raise UnsupportedDocumentError(f"unsupported content type {content_type!r}")


def read_email(content: bytes) -> EmailMessage:
    message = email.message_from_bytes(content, policy=email.policy.default)
    if not isinstance(message, EmailMessage) or not message.keys():
        raise InvalidDocumentError("not an e-mail message")
    return message


def extract_pdfs(filename: str, content_type: str, content: bytes) -> list[Attachment]:
    if classify(filename, content_type, content) == PDF:
        return [Attachment(filename or "document.pdf", content)]
    message = read_email(content)
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
