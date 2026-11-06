from datetime import date
from decimal import Decimal

from fakes import FakeDocument, FakeOcr

from finchie_parser.model import Kind
from finchie_parser.parsers.hsbc import HsbcParser

PAGE_1 = """1/2
HSBC Traveller s Infinite Credit Card
2026/05/08 3,000
2026/04/21 / -3,000
280,000 0
12,162"""

# Line numbers matter: FakeOcr places descriptions on them.
PAGE_2 = """2/2 O
3,000
04/05 04/05 -3,000
04/10 04/12 DEU EUR -10.00 04/10 -340
-3,340
-340
03/25 03/25 8,000
03/30 03/31 30
03/30 03/31 FRA EUR 60.00 03/30 2,000
04/02 04/03 JPN JPY 10,000.00 04/02 2,100
04/02 04/03 32
12,162
11,822
140,000 28,000"""

OCR = {
    1: {
        2: "全國繳費網繳款",
        3: "RefundTaxFreeShop",
        6: "年費",
        7: "國外交易手續費CAFEDEFLORE",
        8: "CAFEDEFLOREPARIS",
        9: "RAMENSHOPTOKYO",
        10: "國外交易手續費RAMENSHOP",
    }
}


def parse(ocr: FakeOcr | None):
    return HsbcParser().parse(FakeDocument([PAGE_1, PAGE_2]), ocr=ocr)


def test_hsbc_reads_unlabelled_statement_fields() -> None:
    statement = parse(FakeOcr(OCR)).statement
    assert statement.due_date == date(2026, 5, 8)
    assert statement.closing_date == date(2026, 4, 21)
    assert statement.reconciliation.stated == Decimal(12162)
    assert statement.total_due == Decimal(11822)


def test_hsbc_reconciles_new_charges_only() -> None:
    # The payment and the refund belong to the previous balance, not to this period's charges.
    reconciliation = parse(FakeOcr(OCR)).statement.reconciliation
    assert reconciliation.balanced
    assert reconciliation.computed == Decimal(12162)


def test_hsbc_takes_descriptions_from_ocr_and_classifies_with_them() -> None:
    rows = [(tx.description, tx.kind, tx.amount) for tx in parse(FakeOcr(OCR)).statement.transactions]
    assert rows == [
        ("全國繳費網繳款", Kind.PAYMENT, Decimal(-3000)),
        ("RefundTaxFreeShop", Kind.REFUND, Decimal(-340)),
        ("年費", Kind.ANNUAL_FEE, Decimal(8000)),
        ("國外交易手續費CAFEDEFLORE", Kind.FOREIGN_TRANSACTION_FEE, Decimal(30)),
        ("CAFEDEFLOREPARIS", Kind.PURCHASE, Decimal(2000)),
        ("RAMENSHOPTOKYO", Kind.PURCHASE, Decimal(2100)),
        ("國外交易手續費RAMENSHOP", Kind.FOREIGN_TRANSACTION_FEE, Decimal(32)),
    ]


def test_hsbc_maps_countries_and_foreign_amounts() -> None:
    by_description = {tx.description: tx for tx in parse(FakeOcr(OCR)).statement.transactions}
    cafe = by_description["CAFEDEFLOREPARIS"]
    assert (cafe.country, cafe.original_currency, cafe.original_amount) == ("FR", "EUR", Decimal("60.00"))
    assert by_description["RAMENSHOPTOKYO"].country == "JP"
    assert by_description["RefundTaxFreeShop"].country == "DE"


def test_hsbc_without_ocr_still_reconciles_and_warns() -> None:
    parsed = parse(None)
    assert parsed.statement.reconciliation.balanced
    assert all(tx.description == "" for tx in parsed.statement.transactions)
    assert parsed.warnings


def test_hsbc_warns_about_rows_ocr_missed() -> None:
    partial = {1: {n: text for n, text in OCR[1].items() if n != 9}}
    parsed = parse(FakeOcr(partial))
    assert len(parsed.warnings) == 1
    assert parsed.statement.reconciliation.balanced
