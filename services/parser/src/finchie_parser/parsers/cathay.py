import re
from decimal import Decimal

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
_PAYMENT = re.compile(r"^(?P<date>\d\d/\d\d) (?P<posted>\d\d/\d\d) (?P<desc>\D+) (?P<amt>-[\d,]+)$", re.ASCII)


class CathayParser(StatementParser):
    name = "cathay.credit_card"
    version = "1"
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
        new_charges = Decimal(0)

        transactions: list[Transaction] = []
        for line in (line for text in texts for line in text.splitlines()):
            if match := _NEW_CHARGES.match(line):
                new_charges += amount(match.group(1))
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
