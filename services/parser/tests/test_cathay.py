from datetime import date
from decimal import Decimal

import pytest
from fakes import FakeDocument

from finchie_parser.errors import LayoutError
from finchie_parser.model import Kind
from finchie_parser.parsers.cathay import CathayParser

PAGE_1 = """信用卡帳單 115年04月
王Ｏ明 先生
115/04/01 80,000"""

PAGE_2 = """您本月消費明細如下：
上期帳單總額 500
03/18 03/18 本行自動扣繳 -500
繳款小計 -500
03/05 03/08 測試計程車隊 250 4321 TW TWD
03/09 03/10 台灣麥當勞ＭＯＰ－１ 180 4321 8765 TW TWD
03/12 03/14 CAFE PARIS 600 4321 FR EUR 17.50 03/12
正卡本期消費 1,030
本期應繳總額 1,030
◎ 您的新臺幣帳款將於 115/04/17 (遇假日順延)之次一營業日自帳號扣款1,030元整
國泰世華CUBE App"""


def parse():
    return CathayParser().parse(FakeDocument([PAGE_1, PAGE_2]), ocr=None).statement


def test_cathay_reads_statement_fields() -> None:
    statement = parse()
    assert statement.closing_date == date(2026, 4, 1)
    assert statement.due_date == date(2026, 4, 17)
    assert statement.total_due == Decimal(1030)
    assert statement.reconciliation.balanced


def test_cathay_parses_rows_with_and_without_wallet_card() -> None:
    rows = [(tx.description, tx.kind, tx.amount, tx.card_last4) for tx in parse().transactions]
    assert rows == [
        ("本行自動扣繳", Kind.PAYMENT, Decimal(-500), ""),
        ("測試計程車隊", Kind.PURCHASE, Decimal(250), "4321"),
        ("台灣麥當勞MOP-1", Kind.PURCHASE, Decimal(180), "4321"),
        ("CAFE PARIS", Kind.PURCHASE, Decimal(600), "4321"),
    ]


def test_cathay_records_foreign_amounts_only_for_foreign_currency() -> None:
    by_description = {tx.description: tx for tx in parse().transactions}
    cafe = by_description["CAFE PARIS"]
    assert (cafe.country, cafe.original_currency, cafe.original_amount) == ("FR", "EUR", Decimal("17.50"))
    taxi = by_description["測試計程車隊"]
    assert (taxi.country, taxi.original_currency, taxi.original_amount) == ("TW", "", None)


def test_cathay_is_recognized_by_text_on_page_2() -> None:
    assert CathayParser().matches_text(FakeDocument([PAGE_1, PAGE_2]))


def test_cathay_without_a_printed_subtotal_is_a_layout_error() -> None:
    # Unrecognized rows and no subtotal would otherwise reconcile as 0 == 0 with no transactions.
    unreadable = "\n".join(line for line in PAGE_2.splitlines() if not line.startswith(("03/", "正卡")))
    with pytest.raises(LayoutError, match="本期消費"):
        CathayParser().parse(FakeDocument([PAGE_1, unreadable]), ocr=None)


FEES_PAGE = """您本月消費明細如下：
03/12 03/14 CAFE PARIS 600 4321 FR EUR 17.50 03/12
03/12 04/01 國外交易手續費 -CAFEPA 9 4321
04/01 04/01 CUBE 卡年費優惠 0 4321
正卡本期消費 609
本期應繳總額 609
◎ 您的新臺幣帳款將於 115/04/17 (遇假日順延)之次一營業日自帳號扣款609元整
國泰世華CUBE App"""


def test_cathay_reads_fees_without_country_or_currency() -> None:
    statement = CathayParser().parse(FakeDocument([PAGE_1, FEES_PAGE]), ocr=None).statement
    rows = [(tx.description, tx.kind, tx.amount, tx.card_last4) for tx in statement.transactions]
    assert rows[1:] == [
        ("國外交易手續費 -CAFEPA", Kind.FOREIGN_TRANSACTION_FEE, Decimal(9), "4321"),
        ("CUBE 卡年費優惠", Kind.ANNUAL_FEE, Decimal(0), "4321"),
    ]
    assert statement.reconciliation.balanced
