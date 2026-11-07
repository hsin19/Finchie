"""Test doubles. Fixture text is synthetic: invented merchants, amounts, and card numbers (ADR 0006)."""

from dataclasses import dataclass, field

from PIL.Image import Image

from finchie_parser.ocr import OcrLine
from finchie_parser.pdf import Document, TextLine

ROW_HEIGHT = 12.0


@dataclass
class FakeDocument:
    pages: list[str]
    filename: str = "fake.pdf"

    def page_texts(self, limit: int | None = None) -> list[str]:
        return self.pages[:limit]

    def page_lines(self, page_index: int) -> list[TextLine]:
        # Like pdfplumber: a thin band at each line's baseline.
        return [
            TextLine(text, baseline(n) - 1, baseline(n)) for n, text in enumerate(self.pages[page_index].splitlines())
        ]

    def render(self, page_index: int, scale: float) -> Image:
        raise AssertionError("fakes are never rendered")


@dataclass
class FakeOcr:
    """Returns given text for given line numbers of a page, positioned like real OCR boxes."""

    descriptions: dict[int, dict[int, str]] = field(default_factory=dict)
    calls: list[int] = field(default_factory=list)

    def read_column(self, document: Document, page_index: int, left: float, right: float) -> list[OcrLine]:
        self.calls.append(page_index)
        return [
            OcrLine(text, top=baseline(n) - 10, bottom=baseline(n) + 0.5, left=left + 10)
            for n, text in self.descriptions.get(page_index, {}).items()
        ]


def baseline(line_number: int) -> float:
    return 40 + line_number * ROW_HEIGHT
