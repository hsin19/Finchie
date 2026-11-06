import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

import pycountry

from finchie_parser.errors import LayoutError
from finchie_parser.model import Kind, Reconciliation, Statement, Transaction
from finchie_parser.ocr import Ocr, OcrLine
from finchie_parser.parsers.base import Parsed, StatementParser
from finchie_parser.pdf import Document
from finchie_parser.text import amount, iso_date, month_day

# HSBC renders every label and every transaction description as an image; the text layer only
# carries dates and numbers. Page 1 lists the due date first, then the closing date.
_P1_DATE = re.compile(r"^(\d{4}/\d\d/\d\d) ", re.ASCII)
_FX_ROW = re.compile(
    r"^(?P<date>\d\d/\d\d) (?P<posted>\d\d/\d\d) (?P<country>[A-Z]{3}) (?P<cur>[A-Z]{3})"
    r" (?P<orig>-?[\d,]+(?:\.\d+)?) \d\d/\d\d (?P<amt>-?[\d,]+)$",
    re.ASCII,
)
# Fees, payments, and the annual fee: no country or currency.
_PLAIN_ROW = re.compile(r"^(?P<date>\d\d/\d\d) (?P<posted>\d\d/\d\d) (?P<amt>-?[\d,]+)$", re.ASCII)
_NUMBER = re.compile(r"^-?[\d,]+$", re.ASCII)

# Unlabelled amounts on the transaction pages, in order:
#   1 previous balance, [payment and adjustment rows], 2 payments subtotal, 3 carried balance,
#   [new charge rows], 4 new charges subtotal, 5 total due.
_CARRIED_BALANCE, _NEW_CHARGES, _TOTAL_DUE = 3, 4, 5

# Description column, in PDF points.
_DESCRIPTION_LEFT, _DESCRIPTION_RIGHT = 120.0, 335.0


@dataclass
class _Row:
    match: re.Match[str]
    page_index: int
    top: float
    bottom: float
    new_charge: bool
    description: str = ""


class HsbcParser(StatementParser):
    name = "hsbc.credit_card"
    version = "1"
    institution = "hsbc"
    filename_pattern = re.compile(r"^eStatement_\d{6}\.pdf$", re.IGNORECASE)
    text_marker = "HSBC"

    def parse(self, document: Document, ocr: Ocr | None) -> Parsed:
        texts = document.page_texts()
        page1_dates = [match.group(1) for line in texts[0].splitlines() if (match := _P1_DATE.match(line))]
        if len(page1_dates) < 2:
            raise LayoutError("due and closing dates not found on page 1")
        due, closing = iso_date(page1_dates[0]), iso_date(page1_dates[1])

        rows, numbers = self._scan(document, len(texts))
        if len(numbers) < _TOTAL_DUE:
            raise LayoutError("new charges subtotal and total due not found")

        warnings: list[str] = []
        if ocr is None:
            warnings.append("OCR disabled: HSBC transaction descriptions are empty")
        else:
            warnings += _attach_descriptions(document, rows, ocr)

        transactions = [self._transaction(row, closing) for row in rows]
        computed = sum((tx.amount for tx, row in zip(transactions, rows, strict=True) if row.new_charge), Decimal(0))
        statement = Statement(
            institution=self.institution,
            closing_date=closing,
            due_date=due,
            currency="TWD",
            total_due=numbers[_TOTAL_DUE - 1],
            transactions=transactions,
            reconciliation=Reconciliation(computed, numbers[_NEW_CHARGES - 1], "消費/新增款項/循環息/其他費用小計"),
        )
        return Parsed(statement, warnings)

    @staticmethod
    def _scan(document: Document, page_count: int) -> tuple[list[_Row], list[Decimal]]:
        rows: list[_Row] = []
        numbers: list[Decimal] = []
        for page_index in range(1, page_count):
            for line in document.page_lines(page_index):
                if len(numbers) >= _TOTAL_DUE:
                    return rows, numbers
                if _NUMBER.match(line.text):
                    numbers.append(amount(line.text))
                elif match := _FX_ROW.match(line.text) or _PLAIN_ROW.match(line.text):
                    new_charge = len(numbers) >= _CARRIED_BALANCE
                    rows.append(_Row(match, page_index, line.top, line.bottom, new_charge))
        return rows, numbers

    @staticmethod
    def _transaction(row: _Row, closing: date) -> Transaction:
        match = row.match
        value = amount(match["amt"])
        foreign = "cur" in match.re.groupindex
        description = row.description
        if foreign:
            kind = Kind.REFUND if value < 0 else Kind.PURCHASE
        elif not row.new_charge and value < 0:
            kind = Kind.PAYMENT
        elif "年費" in description:
            kind = Kind.ANNUAL_FEE
        else:
            kind = Kind.FOREIGN_TRANSACTION_FEE
        currency = match["cur"] if foreign else ""
        return Transaction(
            transaction_date=month_day(match["date"], closing),
            posting_date=month_day(match["posted"], closing),
            description=description,
            kind=kind,
            amount=value,
            original_amount=amount(match["orig"]) if foreign and currency != "TWD" else None,
            original_currency=currency if currency != "TWD" else "",
            country=_alpha2(match["country"]) if foreign else "",
        )


def _attach_descriptions(document: Document, rows: list[_Row], ocr: Ocr) -> list[str]:
    warnings = []
    for page_index in sorted({row.page_index for row in rows}):
        lines = ocr.read_column(document, page_index, _DESCRIPTION_LEFT, _DESCRIPTION_RIGHT)
        for row in (row for row in rows if row.page_index == page_index):
            row.description = _text_on_baseline(lines, row.bottom)
            if not row.description:
                warnings.append(f"no OCR text for the row at page {page_index + 1}, y={row.bottom:.0f}")
    return warnings


def _text_on_baseline(lines: list[OcrLine], baseline: float) -> str:
    # pdfplumber reports the text-layer row as a ~1 pt band at its baseline, while an OCR box spans
    # the full glyph height above it. Their bottoms agree within about a point; rows are 12 pt apart.
    hits = [line for line in lines if abs(line.bottom - baseline) <= 3.0]
    return " ".join(line.text for line in sorted(hits, key=lambda line: line.left))


def _alpha2(alpha3: str) -> str:
    country = pycountry.countries.get(alpha_3=alpha3)
    return country.alpha_2 if country else ""
