import threading
import time

import pypdfium2
import pytest
from pdfs import blank_pdf
from PIL import Image

from finchie_parser.documents import Attachment
from finchie_parser.errors import InvalidDocumentError, PasswordRequiredError
from finchie_parser.pdf import open_pdf


def test_unencrypted_pdf_opens_without_passwords() -> None:
    with open_pdf(Attachment("a.pdf", blank_pdf()), []) as document:
        assert document.page_texts() == [""]


def test_encrypted_pdf_opens_with_any_configured_password() -> None:
    with open_pdf(Attachment("a.pdf", blank_pdf("right")), ["wrong", "right"]) as document:
        assert len(document.page_texts()) == 1


def test_encrypted_pdf_without_a_matching_password_is_rejected() -> None:
    with pytest.raises(PasswordRequiredError):
        open_pdf(Attachment("a.pdf", blank_pdf("right")), ["wrong"])


def test_corrupt_pdf_is_invalid() -> None:
    with pytest.raises(InvalidDocumentError):
        open_pdf(Attachment("a.pdf", b"%PDF-1.7 truncated"), [])


class _Concurrency:
    """Counts callers inside fake PDFium at the same time."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.active = 0
        self.peak = 0

    def enter(self) -> None:
        with self._lock:
            self.active += 1
            self.peak = max(self.peak, self.active)
        time.sleep(0.02)
        with self._lock:
            self.active -= 1


def test_pdfium_is_never_called_from_two_threads_at_once(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _Concurrency()

    class FakeBitmap:
        def to_pil(self) -> Image.Image:
            calls.enter()
            return Image.new("RGB", (1, 1))

        def close(self) -> None:
            calls.enter()

    class FakePage:
        def render(self, scale: float) -> FakeBitmap:
            calls.enter()
            return FakeBitmap()

        def close(self) -> None:
            calls.enter()

    class FakePdfium:
        def __init__(self, data: bytes) -> None:
            calls.enter()

        def __getitem__(self, index: int) -> FakePage:
            calls.enter()
            return FakePage()

        def close(self) -> None:
            calls.enter()

    monkeypatch.setattr(pypdfium2, "PdfDocument", FakePdfium)
    start = threading.Barrier(4)

    def parse_one() -> None:
        with open_pdf(Attachment("a.pdf", blank_pdf()), []) as document:
            start.wait()
            document.render(0, 1.0)

    threads = [threading.Thread(target=parse_one) for _ in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert calls.peak == 1
