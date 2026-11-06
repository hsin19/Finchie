"""Decrypt a PDF and expose what the bank parsers read: text, positioned lines, page images."""

import io
import threading
from collections.abc import Sequence
from dataclasses import dataclass
from functools import cache
from types import TracebackType
from typing import Protocol, Self

import pdfplumber
import pikepdf
import pypdfium2
from PIL.Image import Image

from finchie_parser.documents import Attachment
from finchie_parser.errors import InvalidDocumentError, PasswordRequiredError

# PDFium is not thread-safe, not even for separate documents, and the server parses on several
# threads at once. Every call into it (open, render, close) holds this lock.
_PDFIUM = threading.Lock()


@dataclass(frozen=True)
class TextLine:
    text: str
    top: float
    bottom: float


class Document(Protocol):
    """What a bank parser may read. Tests provide fakes with synthetic text."""

    filename: str

    def page_texts(self) -> list[str]: ...

    def page_lines(self, page_index: int) -> list[TextLine]: ...

    def render(self, page_index: int, scale: float) -> Image: ...


class PdfDocument:
    def __init__(self, filename: str, data: bytes) -> None:
        self.filename = filename
        self._data = data
        self._plumber = pdfplumber.open(io.BytesIO(data))
        self._pdfium: pypdfium2.PdfDocument | None = None
        self.page_texts = cache(self._page_texts)

    def _page_texts(self) -> list[str]:
        return [page.extract_text() or "" for page in self._plumber.pages]

    def page_lines(self, page_index: int) -> list[TextLine]:
        lines = self._plumber.pages[page_index].extract_text_lines(return_chars=False)
        return [TextLine(line["text"], line["top"], line["bottom"]) for line in lines]

    def render(self, page_index: int, scale: float) -> Image:
        with _PDFIUM:
            if self._pdfium is None:
                self._pdfium = pypdfium2.PdfDocument(self._data)
            page = self._pdfium[page_index]
            bitmap = page.render(scale=scale)
            try:
                # A copy: the PIL image would otherwise share the bitmap's memory, freed below.
                return bitmap.to_pil().copy()
            finally:
                bitmap.close()
                page.close()

    def close(self) -> None:
        self._plumber.close()
        if self._pdfium is not None:
            with _PDFIUM:
                self._pdfium.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_: type[BaseException] | BaseException | TracebackType | None) -> None:
        self.close()


def open_pdf(attachment: Attachment, passwords: Sequence[str]) -> PdfDocument:
    """Open with no password first, then each configured one; return a decrypted copy."""
    for password in ("", *passwords):
        try:
            with pikepdf.open(io.BytesIO(attachment.data), password=password) as pdf:
                decrypted = io.BytesIO()
                pdf.save(decrypted)
        except pikepdf.PasswordError:
            continue
        except pikepdf.PdfError as error:
            raise InvalidDocumentError(f"{attachment.filename}: unreadable PDF ({error})") from error
        return PdfDocument(attachment.filename, decrypted.getvalue())
    raise PasswordRequiredError(f"{attachment.filename}: none of the configured passwords opens it")
