"""Open a document for a person to read: an e-mail's headers, body, and attachments, PDFs decrypted."""

import base64
import dataclasses
import mimetypes
import re
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from email.message import EmailMessage

from finchie_parser.documents import PDF, Attachment, classify, read_email
from finchie_parser.errors import InvalidDocumentError, PasswordRequiredError
from finchie_parser.parsers import PARSERS, StatementParser
from finchie_parser.pdf import decrypt

# They sign the message; there is nothing in them to read.
_SIGNATURES = frozenset({"application/pkcs7-signature", "application/x-pkcs7-signature", "application/pgp-signature"})
_CID = re.compile(r"cid:([^\"'\s)>]+)", re.IGNORECASE)


@dataclass(frozen=True)
class File:
    filename: str
    content_type: str
    data: bytes
    locked: bool = False
    primary: bool = False


@dataclass(frozen=True)
class Email:
    sender: str
    recipient: str
    subject: str
    date: datetime | None
    html: str = ""
    text: str = ""


@dataclass(frozen=True)
class OpenedDocument:
    email: Email | None
    files: list[File]


def open_document(
    filename: str,
    content_type: str,
    content: bytes,
    *,
    passwords: Sequence[str],
    parsers: Sequence[StatementParser] = PARSERS,
) -> OpenedDocument:
    if classify(filename, content_type, content) == PDF:
        return OpenedDocument(None, _mark_primary([_pdf(filename or "document.pdf", content, passwords)], parsers))

    message = read_email(content)
    body = message.get_body(preferencelist=("html", "plain"))
    inline = {
        str(part["Content-ID"]).strip("<> "): part
        for part in message.walk()
        if not part.is_multipart() and part["Content-ID"]
    }
    html = text = ""
    embedded: set[str] = set()
    if body is not None and body.get_content_subtype() == "html":
        html = _CID.sub(lambda m: _data_uri(m, inline, embedded), _text_of(body))
    elif body is not None:
        text = _text_of(body)

    files = []
    for part in message.walk():
        if part.is_multipart() or part is body or part.get_content_type() in _SIGNATURES:
            continue
        if str(part["Content-ID"] or "").strip("<> ") in embedded:
            continue
        # The plain-text twin of an HTML body, or the body of a forwarded message inside this one.
        if part.get_content_maintype() == "text" and not part.is_attachment() and not part.get_filename():
            continue
        files.append(_file(part, passwords))

    date_header = message["Date"]
    return OpenedDocument(
        Email(
            sender=str(message["From"] or ""),
            recipient=str(message["To"] or ""),
            subject=str(message["Subject"] or ""),
            date=getattr(date_header, "datetime", None),
            html=html,
            text=text,
        ),
        _mark_primary(files, parsers),
    )


def _mark_primary(files: list[File], parsers: Sequence[StatementParser]) -> list[File]:
    """The statement by its attachment name, as parsing picks it; else the first PDF."""
    pdfs = [i for i, f in enumerate(files) if f.content_type == PDF]
    named = (i for i in pdfs if any(p.matches_filename(files[i].filename) for p in parsers))
    primary = next(named, pdfs[0] if pdfs else None)
    if primary is not None:
        files[primary] = dataclasses.replace(files[primary], primary=True)
    return files


def _file(part: EmailMessage, passwords: Sequence[str]) -> File:
    data = part.get_payload(decode=True)
    if not isinstance(data, bytes):
        data = b""
    content_type = part.get_content_type()
    name = part.get_filename()
    if data.startswith(b"%PDF"):
        return _pdf(name or "attachment.pdf", data, passwords)
    return File(name or f"attachment{mimetypes.guess_extension(content_type) or ''}", content_type, data)


def _pdf(filename: str, data: bytes, passwords: Sequence[str]) -> File:
    try:
        return File(filename, PDF, decrypt(Attachment(filename, data), passwords))
    except PasswordRequiredError:
        return File(filename, PDF, data, locked=True)
    except InvalidDocumentError:
        # Shown as it arrived: the browser's PDF viewer says what is wrong with it.
        return File(filename, PDF, data)


def _text_of(part: EmailMessage) -> str:
    try:
        return part.get_content()
    except LookupError:
        # A charset Python does not know: most of the text is still readable as UTF-8.
        payload = part.get_payload(decode=True)
        return payload.decode("utf-8", errors="replace") if isinstance(payload, bytes) else ""


def _data_uri(match: re.Match[str], inline: dict[str, EmailMessage], embedded: set[str]) -> str:
    part = inline.get(match.group(1))
    data = part.get_payload(decode=True) if part is not None else None
    if part is None or not isinstance(data, bytes):
        return match.group(0)
    embedded.add(match.group(1))
    return f"data:{part.get_content_type()};base64,{base64.b64encode(data).decode('ascii')}"
