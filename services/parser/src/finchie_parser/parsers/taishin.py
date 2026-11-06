import re
from decimal import Decimal

from finchie_parser.model import Kind, Reconciliation, Statement, Transaction
from finchie_parser.ocr import Ocr
from finchie_parser.parsers.base import Parsed, StatementParser, find, sum_new_charges
from finchie_parser.pdf import Document
from finchie_parser.text import amount, clean, roc_date

_CLOSING = re.compile(r"^帳單結帳日 (\d{3}/\d\d/\d\d)$", re.ASCII)
_DUE = re.compile(r"^繳款截止日 (\d{3}/\d\d/\d\d)$", re.ASCII)
_NEW_CHARGES = re.compile(r"^\+本期新增款項 (-?[\d,]+)$", re.ASCII)
_TOTAL_DUE = re.compile(r"^=本期累計應繳金額 (-?[\d,]+)$", re.ASCII)
_CARD = re.compile(r"\(卡號末四碼:(\d{4})\)", re.ASCII)
# "<date> <posted> <description> <amount>" then either "<MMDD> <country> <currency> <foreign amount>"
# for foreign-currency lines or just "<country>". Long descriptions wrap: the row then has an empty
# description, with its first half on the line above and the rest (usually the city) below.
_ROW = re.compile(
    r"^(?P<date>\d{3}/\d\d/\d\d) (?P<posted>\d{3}/\d\d/\d\d) ?(?P<desc>.*?) ?(?P<amt>-?[\d,]+)"
    r"(?: \d{4} (?P<fxcountry>[A-Z]{2}) (?P<cur>[A-Z]{3}) (?P<orig>[\d,]+(?:\.\d+)?)| (?P<country>[A-Z]{2}))?$",
    re.ASCII,
)


class TaishinParser(StatementParser):
    name = "taishin.credit_card"
    version = "1"
    institution = "taishin"
    filename_pattern = re.compile(r"^TSB_Creditcard_Estatement_\d+\.pdf$", re.IGNORECASE)
    text_marker = "台新"

    def parse(self, document: Document, ocr: Ocr | None) -> Parsed:
        texts = document.page_texts()
        closing = roc_date(find(_CLOSING, texts, "帳單結帳日").group(1))
        due = roc_date(find(_DUE, texts, "繳款截止日").group(1))
        new_charges = amount(find(_NEW_CHARGES, texts, "本期新增款項").group(1))
        total_due = amount(find(_TOTAL_DUE, texts, "本期累計應繳金額").group(1))

        lines = [line for text in texts for line in text.splitlines() if line.strip()]
        transactions: list[Transaction] = []
        card = ""
        i = 0
        while i < len(lines):
            line = lines[i]
            if match := _CARD.search(line):
                card = match.group(1)
            elif match := _ROW.match(line):
                description = match["desc"]
                if not description and 0 < i < len(lines) - 1:
                    description = f"{lines[i - 1]} {lines[i + 1]}"
                    i += 1
                value = amount(match["amt"])
                description = clean(description)
                kind = _kind(description, value)
                transactions.append(
                    Transaction(
                        transaction_date=roc_date(match["date"]),
                        posting_date=roc_date(match["posted"]),
                        description=description,
                        kind=kind,
                        amount=value,
                        original_amount=amount(match["orig"]) if match["orig"] else None,
                        original_currency=match["cur"] or "",
                        country=match["fxcountry"] or match["country"] or "",
                        card_last4="" if kind is Kind.PAYMENT else card,
                    )
                )
            i += 1

        statement = Statement(
            institution=self.institution,
            closing_date=closing,
            due_date=due,
            currency="TWD",
            total_due=total_due,
            transactions=transactions,
            reconciliation=Reconciliation(sum_new_charges(transactions), new_charges, "本期新增款項"),
        )
        return Parsed(statement)


def _kind(description: str, value: Decimal) -> Kind:
    if "國外交易服務費" in description:
        return Kind.FOREIGN_TRANSACTION_FEE
    if "年費" in description:
        return Kind.ANNUAL_FEE
    if value < 0 and ("扣繳" in description or "繳款" in description):
        return Kind.PAYMENT
    if "折抵" in description:
        return Kind.REBATE
    if value < 0:
        return Kind.REFUND
    return Kind.PURCHASE
