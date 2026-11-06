import re
from abc import ABC, abstractmethod
from collections.abc import Iterable
from dataclasses import dataclass, field
from decimal import Decimal
from typing import ClassVar

from finchie_parser.errors import LayoutError
from finchie_parser.model import Kind, Statement, Transaction
from finchie_parser.ocr import Ocr
from finchie_parser.pdf import Document


@dataclass
class Parsed:
    statement: Statement
    warnings: list[str] = field(default_factory=list)


class StatementParser(ABC):
    """One bank's statement layout. Parsers are stateless and shared across threads."""

    name: ClassVar[str]
    # Bump when the output for the same input can change, so the backend knows what to re-parse.
    version: ClassVar[str]
    institution: ClassVar[str]
    filename_pattern: ClassVar[re.Pattern[str]]
    # Text that only this bank's statements contain on the first page.
    text_marker: ClassVar[str]

    def matches_filename(self, filename: str) -> bool:
        return bool(self.filename_pattern.search(filename))

    def matches_text(self, document: Document) -> bool:
        texts = document.page_texts()
        return bool(texts) and self.text_marker in texts[0]

    @abstractmethod
    def parse(self, document: Document, ocr: Ocr | None) -> Parsed: ...


def sum_new_charges(transactions: Iterable[Transaction]) -> Decimal:
    return sum((tx.amount for tx in transactions if tx.kind is not Kind.PAYMENT), Decimal(0))


def find(pattern: re.Pattern[str], texts: Iterable[str], what: str) -> re.Match[str]:
    for text in texts:
        for line in text.splitlines():
            if match := pattern.search(line):
                return match
    raise LayoutError(f"statement field not found: {what}")
