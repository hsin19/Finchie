"""Tiny generated PDFs: no real documents in the repository (ADR 0006)."""

import io
from email.message import EmailMessage

import pikepdf


def blank_pdf(user_password: str | None = None) -> bytes:
    pdf = pikepdf.new()
    pdf.add_blank_page()
    buffer = io.BytesIO()
    if user_password is None:
        pdf.save(buffer)
    else:
        pdf.save(buffer, encryption=pikepdf.Encryption(owner="owner-secret", user=user_password, R=6))
    return buffer.getvalue()


def email_with(*attachments: tuple[str, str, bytes]) -> bytes:
    """attachments: (filename, content type, data)."""
    message = EmailMessage()
    message["From"] = "statements@bank.example"
    message["To"] = "someone@example.com"
    message["Subject"] = "Your statement"
    message.set_content("See attachment.")
    for filename, content_type, data in attachments:
        maintype, subtype = content_type.split("/")
        message.add_attachment(data, maintype=maintype, subtype=subtype, filename=filename)
    return message.as_bytes()
