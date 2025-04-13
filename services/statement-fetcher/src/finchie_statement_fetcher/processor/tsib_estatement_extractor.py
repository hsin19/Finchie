import getpass
import glob
import logging
import os
import re
import sys
from dataclasses import dataclass, field

import pdfplumber

from finchie_statement_fetcher.utils.logging_utils import setup_console_logger


@dataclass
class RawTransaction:
    """
    Transaction details from the credit card statement
    """

    transaction_date: str
    """消費日"""
    posting_date: str
    """入帳起息日"""
    description: str
    """消費明細"""
    new_taiwan_dollar_amount: str
    """新臺幣金額"""
    foreign_currency_date: str | None = None
    """外幣折算日"""
    location: str | None = None
    """消費地"""
    currency: str | None = None
    """幣別"""
    foreign_currency_amount: str | None = None
    """外幣金額"""


@dataclass
class RawCardTransactions:
    """
    transactions grouped by card
    """

    card_name: str | None = None
    """e.g. @GoGo虛擬御璽卡"""
    card_holder_name: str | None = None
    """e.g. 葉信賢"""
    card_last_four: str | None = None
    """e.g. 1234"""
    transactions: list[RawTransaction] = field(default_factory=list)
    """List of transactions for this card"""


@dataclass
class RawEStatement:
    """
    Credit card statement summary information
    """

    bill_info: dict[str, str]
    transactions: list[RawCardTransactions]
    """List of transactions for this card"""


logger = logging.getLogger(__name__)


def _extract_bill_info(text: str) -> dict[str, str]:
    """Extract the credit card bill summary information"""

    patterns = {
        # 帳務資訊
        "帳單結帳日": r"帳單結帳日\s*(\d+/\d+/\d+)",
        "繳款截止日": r"繳款截止日\s*(\d+/\d+/\d+)",
        "上期應繳總額": r"上期應繳總額\s*(\d+(?:,\d+)?)",
        "已繳退款總額": r"已繳退款總額\s*(\d+(?:,\d+)?)",
        "前期餘額": r"前期餘額\s*(\d+(?:,\d+)?)",
        "本期新增款項": r"本期新增款項\s*(\d+(?:,\d+)?)",
        "本期累計應繳金額": r"本期累計應繳金額\s*(\d+(?:,\d+)?)",
        "本期最低應繳金額": r"本期最低應繳金額\s*(\d+(?:,\d+)?)",
        # 信用額度及利率資訊
        "信用額度": r"信用額度\(NT\)\s*(\d+(?:,\d+)?)",
        "國內預借現金額": r"國內預借現金額度\s*(\d+(?:,\d+)?)",
        "國外預借現金額度": r"國外預借現金額度\s*(\d+(?:,\d+)?)",
        "分期吉時金額度": r"分期吉時金額度\s*(\d+(?:,\d+)?)",
        "循環信用利率": r"循環信用利率\s*(\d+(?:,\d+)?(?:.\d+)+)%",
        # 點數
        "上期結餘點數/里數": r"上期結餘點數/里數\s+([ \d,\*]+)",
        "新增回饋": r"新增回饋\s+([ \d,\*]+)",
        "活動回饋/調整": r"活動回饋/調整\s+([ \d,\*]+)",
        "本期使用點數/里數": r"本期使用點數/里數\s+([ \d,\*]+)",
        "本期結餘回饋": r"本期結餘回饋\s+([ \d,\*]+)",
    }

    bill_data = {}

    # Extract data using regex patterns
    for key, pattern in patterns.items():
        match = re.search(pattern, text)
        if match:
            value = match.group(1)
            bill_data[key] = value
        else:
            logger.warning("Failed to extract %s", key)

    return bill_data


def _extract_transactions(text: str) -> list[RawCardTransactions]:
    """Extract transaction details from the statement text"""

    header_pattern = r"消費日\s*入帳起息日\s*消費明細\s*新臺幣金額\s*外幣折算日\s*消費地\s*幣別\s*外幣金額"
    match = re.search(header_pattern, text)
    if not match:
        logger.warning("Header not found in the text")
        return []
    start_line = match.start()

    lines = text[start_line:].split("\n")[1:]  # Skip the header line

    card_pattern = re.compile(r"^(\S+)\s+(\S+)\s+\(卡號末四碼:(\d{4})\)$")

    ntd_transaction_pattern = re.compile(
        r"^(?P<transaction_date>\d+/\d+/\d+)"  # 消費日
        r"\s+(?P<posting_date>\d+/\d+/\d+)"  # 入帳起息日
        r"(?P<description>.*?)?"  # 消費明細 (optional)
        r"\s+(?P<amount>-?\d+(?:,\d+)*)"  # 新臺幣金額
        r"(?:\s+(?P<location>[A-Z]+))?$"  # 消費地 (optional)
    )

    foreign_transaction_pattern = re.compile(
        r"^(?P<transaction_date>\d+/\d+/\d+)"  # 消費日
        r"\s+(?P<posting_date>\d+/\d+/\d+)"  # 入帳起息日
        r"(?P<description>.*?)?"  # 消費明細 (optional)
        r"\s+(?P<ntd_amount>-?\d+(?:,\d+)*)"  # 新臺幣金額
        r"\s+(?P<forex_date>\d+)"  # 外幣折算日
        r"\s+(?P<location>[A-Z]+)"  # 消費地
        r"\s+(?P<currency>[A-Z]+)"  # 幣別
        r"\s+(?P<foreign_amount>-?\d+(?:,\d+)*(?:.\d+))$"  # 外幣金額
    )

    # when the description is too long, it will be split into multiple lines
    # first line: description phase 1
    # second line: transaction information without description
    # third line: description phase 2

    current_card = RawCardTransactions()
    transactions = [current_card]

    i = 0
    none_processed_lines = []
    while i < len(lines):
        line = lines[i].strip()
        i += 1
        if not line:
            continue

        # Check if the line contains card information
        card_match = card_pattern.match(line)
        if card_match:
            current_card = RawCardTransactions(
                card_name=card_match.group(1), card_holder_name=card_match.group(2), card_last_four=card_match.group(3)
            )
            transactions.append(current_card)
            continue

        # Check if the line contains transaction information
        ntd_match = ntd_transaction_pattern.match(line)
        if ntd_match:
            description = ntd_match.group("description").strip()
            description, i = _process_multiple_description(description, none_processed_lines, lines, i)
            if description is None:
                continue

            transaction = RawTransaction(
                transaction_date=ntd_match.group("transaction_date"),
                posting_date=ntd_match.group("posting_date"),
                description=description,
                new_taiwan_dollar_amount=ntd_match.group("amount"),
                location=ntd_match.group("location") if ntd_match.group("location") else "",
            )
            current_card.transactions.append(transaction)
            continue

        # Check if the line contains foreign transaction information
        foreign_match = foreign_transaction_pattern.match(line)
        if foreign_match:
            description = foreign_match.group("description").strip()
            description, i = _process_multiple_description(description, none_processed_lines, lines, i)
            if description is None:
                continue

            transaction = RawTransaction(
                transaction_date=foreign_match.group("transaction_date"),
                posting_date=foreign_match.group("posting_date"),
                description=description,
                new_taiwan_dollar_amount=foreign_match.group("ntd_amount"),
                foreign_currency_date=foreign_match.group("forex_date"),
                location=foreign_match.group("location"),
                currency=foreign_match.group("currency"),
                foreign_currency_amount=foreign_match.group("foreign_amount"),
            )
            current_card.transactions.append(transaction)
            continue

        none_processed_lines.append(line)
        if len(none_processed_lines) > 2:
            logger.debug("process end with %s", none_processed_lines)
            break

    return transactions


def _process_multiple_description(description: str, none_processed_lines: list, lines: list, current_index: int) -> tuple[str | None, int]:
    """
    Process missing or multi-line transaction descriptions
    """
    if not description:
        if not none_processed_lines or current_index >= len(lines):
            logger.warning("Transaction description is missing")
            return None, current_index

        previous_line = none_processed_lines.pop().strip()
        next_line = lines[current_index].strip()
        current_index += 1
        description = f"{previous_line}{next_line}".strip()

    return description, current_index


def extract_credit_card_statement(pdf_path: str, password: str | None = None) -> RawEStatement | None:
    """Parse a credit card statement PDF into CreditCardBill object"""

    try:
        with pdfplumber.open(pdf_path, password=password) as pdf:
            full_text = ""
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    full_text += text + "\n"
    except Exception:
        logger.error("Failed to read PDF file: %s", pdf_path)
        return None

    # Extract bill summary information
    raw_bill = _extract_bill_info(full_text)

    # Extract transactions
    raw_transactions = _extract_transactions(full_text)

    return RawEStatement(
        bill_info=raw_bill,
        transactions=raw_transactions,
    )


if __name__ == "__main__":  # pragma: no cover
    setup_console_logger(logger)

    # Search for TSB_Creditcard_Estatement files in all subdirectories under data\extract\gmail
    search_pattern = os.path.join("data", "extract", "gmail", "**", "TSB_Creditcard_Estatement*.pdf")
    matching_files = glob.glob(search_pattern, recursive=True)

    if not matching_files:
        print("No Taishin Bank credit card statement files found")
        sys.exit(1)

    pdf_path = matching_files[-1]
    print(f"File found: {pdf_path}")

    password = getpass.getpass("Enter PDF password: ")

    bill = extract_credit_card_statement(pdf_path, password=password)

    if not bill:
        print("Failed to parse the PDF file")
        sys.exit(1)

    print("Bill summary:")
    for key, value in bill.bill_info.items():
        print(f"{key}: {value}")

    print("\nTransactions:")
    for card in bill.transactions:
        print(f"\nCard: {card.card_name} ({card.card_last_four})")
        for transaction in card.transactions:
            print(f"  Date: {transaction.transaction_date}, {transaction.description}, {transaction.new_taiwan_dollar_amount}")
