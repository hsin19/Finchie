import re
from decimal import Decimal

from finchie_parser.errors import LayoutError
from finchie_parser.model import Kind, Reconciliation, Statement, Transaction
from finchie_parser.ocr import Ocr
from finchie_parser.parsers.base import Parsed, StatementParser, find, sum_new_charges
from finchie_parser.pdf import Document
from finchie_parser.text import amount, clean, month_day, roc_date

# Page 1 prints the closing date next to the credit limit: "115/10/01 140,000".
_CLOSING = re.compile(r"^(\d{3}/\d\d/\d\d) [\d,]+$", re.ASCII)
# The auto-debit notice carries the due date, already moved past holidays.
_DUE = re.compile(r"將於\s*(\d{3}/\d\d/\d\d)", re.ASCII)
_NEW_CHARGES = re.compile(r"^(?:正卡|附卡)本期消費 (-?[\d,]+)$", re.ASCII)
_TOTAL_DUE = re.compile(r"^本期應繳總額 (-?[\d,]+)$", re.ASCII)
# "<date> <posted> <description> <amount> <card last 4> [<wallet card last 4>] <country> <currency>
#  [<foreign amount> [<conversion date>]]"
_ROW = re.compile(
    r"^(?P<date>\d\d/\d\d) (?P<posted>\d\d/\d\d) (?P<desc>.+?) (?P<amt>-?[\d,]+) (?P<card>\d{4})(?: \d{4})?"
    r" (?P<country>[A-Z]{2}) (?P<cur>[A-Z]{3})(?: (?P<orig>[\d,]+(?:\.\d+)?)(?: \d\d/\d\d)?)?$",
    re.ASCII,
)
# Fees and the annual fee name no country or currency:
# "<date> <posted> <description> <amount> <card last 4>", e.g. "12/21 01/01 國外交易手續費 -AUSTRA 6 7218".
_PLAIN_ROW = re.compile(
    r"^(?P<date>\d\d/\d\d) (?P<posted>\d\d/\d\d) (?P<desc>.+?) (?P<amt>-?[\d,]+) (?P<card>\d{4})$", re.ASCII
)
_PAYMENT = re.compile(r"^(?P<date>\d\d/\d\d) (?P<posted>\d\d/\d\d) (?P<desc>\D+) (?P<amt>-[\d,]+)$", re.ASCII)


class CathayParser(StatementParser):
    name = "cathay.credit_card"
    version = "2"
    institution = "cathay"
    filename_pattern = re.compile(r"^信用卡電子帳單消費明細_\d+\.pdf$")
    text_marker = "國泰世華"

    def matches_text(self, document: Document) -> bool:
        # The bank's name sits in an image on page 1; the fine print on page 2 names it.
        return any(self.text_marker in text for text in document.page_texts()[:2])

    def parse(self, document: Document, ocr: Ocr | None) -> Parsed:
        texts = document.page_texts()
        closing = roc_date(find(_CLOSING, texts[:1], "closing date").group(1))
        due = roc_date(find(_DUE, texts, "due date").group(1))
        total_due = amount(find(_TOTAL_DUE, texts, "本期應繳總額").group(1))
        # One subtotal per card holder (正卡, 附卡). None until one is read: taking a missing subtotal as
        # zero would let a layout change that also hides every row reconcile as balanced and empty.
        new_charges: Decimal | None = None

        transactions: list[Transaction] = []
        for line in (line for text in texts for line in text.splitlines()):
            if match := _NEW_CHARGES.match(line):
                new_charges = (new_charges or Decimal(0)) + amount(match.group(1))
            elif match := _ROW.match(line):
                value = amount(match["amt"])
                foreign = match["cur"] != "TWD"
                transactions.append(
                    Transaction(
                        transaction_date=month_day(match["date"], closing),
                        posting_date=month_day(match["posted"], closing),
                        description=clean(match["desc"]),
                        kind=Kind.REFUND if value < 0 else Kind.PURCHASE,
                        amount=value,
                        original_amount=amount(match["orig"]) if foreign and match["orig"] else None,
                        original_currency=match["cur"] if foreign else "",
                        country=match["country"],
                        card_last4=match["card"],
                    )
                )
            elif match := _PLAIN_ROW.match(line):
                value = amount(match["amt"])
                description = clean(match["desc"])
                transactions.append(
                    Transaction(
                        transaction_date=month_day(match["date"], closing),
                        posting_date=month_day(match["posted"], closing),
                        description=description,
                        kind=_plain_kind(description, value),
                        amount=value,
                        card_last4=match["card"],
                    )
                )
            elif match := _PAYMENT.match(line):
                transactions.append(
                    Transaction(
                        transaction_date=month_day(match["date"], closing),
                        posting_date=month_day(match["posted"], closing),
                        description=clean(match["desc"]),
                        kind=Kind.PAYMENT,
                        amount=amount(match["amt"]),
                    )
                )

        if new_charges is None:
            raise LayoutError("statement field not found: 本期消費")

        statement = Statement(
            institution=self.institution,
            closing_date=closing,
            due_date=due,
            currency="TWD",
            total_due=total_due,
            transactions=transactions,
            reconciliation=Reconciliation(sum_new_charges(transactions), new_charges, "本期消費"),
        )
        return Parsed(statement)


def _plain_kind(description: str, value: Decimal) -> Kind:
    if "國外交易手續費" in description:
        return Kind.FOREIGN_TRANSACTION_FEE
    if "年費" in description:
        return Kind.ANNUAL_FEE
    return Kind.REFUND if value < 0 else Kind.PURCHASE
