from datetime import date
from decimal import Decimal

from fakes import FakeDocument

from finchie_parser.model import Kind
from finchie_parser.parsers.taishin import TaishinParser

PAGE_1 = """115年 03月 信用卡電子帳單
帳 務 資 訊
帳單結帳日 115/04/07
繳款截止日 115/04/22
上期應繳總額 2,000
-已繳退款總額 2,000
=前期餘額 0
+本期新增款項 3,170
=本期累計應繳金額 3,170
本期最低應繳金額 1,000"""

PAGE_2 = """消費日 入帳起息日消費明細 新臺幣金額 外幣折算日 消費地 幣別 外幣金額
台新銀行帳戶自動轉帳扣繳台新信用
115/03/24 115/03/24 -2,000
卡款
Richart卡(原測試御璽) (卡號末四碼:1111)
115/03/05 115/03/07 統一超商－測試店A9999 TAIPEI 65 TW
非常長的商店名稱股份有限公司A9999
115/03/06 115/03/09 1,500 TW
TAIPEI
115/03/10 115/03/11 BOOKSTORE ONLINEO1234 SEATTL 640 0309 US USD 20.00
115/03/10 115/03/11 國外交易服務費－640.00 10
Richart卡(原測試商務 (卡號末四碼:2222)
115/03/15 115/03/16 HOTEL BOOKINGO9157 Intern -800 SG
信用卡消費折抵_測試百貨股份有限
115/03/16 115/03/18 -45
公司
115/04/07 115/04/07 商務卡年費 1,800 TW
115/04/07 115/04/07 商務卡年費減免 -1,800 TW
115/03/20 115/03/22 健身中心 1,800 TW
自民國115年06月結帳日之次日起，您適用之循環信用利率為5.00%"""


def parse():
    return TaishinParser().parse(FakeDocument([PAGE_1, PAGE_2]), ocr=None).statement


def test_taishin_reads_statement_fields() -> None:
    statement = parse()
    assert statement.closing_date == date(2026, 4, 7)
    assert statement.due_date == date(2026, 4, 22)
    assert statement.total_due == Decimal(3170)
    assert statement.reconciliation.balanced


def test_taishin_joins_wrapped_descriptions() -> None:
    descriptions = [tx.description for tx in parse().transactions]
    assert "台新銀行帳戶自動轉帳扣繳台新信用 卡款" in descriptions
    assert "非常長的商店名稱股份有限公司A9999 TAIPEI" in descriptions
    assert "信用卡消費折抵_測試百貨股份有限 公司" in descriptions
    # The line after a wrapped row is consumed, not parsed again.
    assert len(descriptions) == 10


def test_taishin_classifies_lines() -> None:
    kinds = {tx.description: tx.kind for tx in parse().transactions}
    assert kinds["台新銀行帳戶自動轉帳扣繳台新信用 卡款"] is Kind.PAYMENT
    assert kinds["國外交易服務費-640.00"] is Kind.FOREIGN_TRANSACTION_FEE
    assert kinds["HOTEL BOOKINGO9157 Intern"] is Kind.REFUND
    assert kinds["信用卡消費折抵_測試百貨股份有限 公司"] is Kind.REBATE
    assert kinds["商務卡年費"] is Kind.ANNUAL_FEE
    assert kinds["商務卡年費減免"] is Kind.ANNUAL_FEE


def test_taishin_tracks_cards_countries_and_foreign_amounts() -> None:
    by_description = {tx.description: tx for tx in parse().transactions}
    assert by_description["台新銀行帳戶自動轉帳扣繳台新信用 卡款"].card_last4 == ""
    assert by_description["統一超商-測試店A9999 TAIPEI"].card_last4 == "1111"
    assert by_description["健身中心"].card_last4 == "2222"
    book = by_description["BOOKSTORE ONLINEO1234 SEATTL"]
    assert (book.country, book.original_currency, book.original_amount) == ("US", "USD", Decimal("20.00"))
    assert by_description["HOTEL BOOKINGO9157 Intern"].country == "SG"
