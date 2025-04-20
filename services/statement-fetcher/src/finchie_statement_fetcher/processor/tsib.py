import getpass
import glob
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from finchie_statement_fetcher.models import Statement
from finchie_statement_fetcher.models.api_models import SourceType, StatementType, Transaction
from finchie_statement_fetcher.processor.base import BaseProcessor
from finchie_statement_fetcher.processor.tsib_estatement_extractor import extract_credit_card_statement
from finchie_statement_fetcher.utils import parse_taiwanese_date
from finchie_statement_fetcher.utils.logging_utils import setup_console_logger
from finchie_statement_fetcher.utils.type_utils import to_float

logger = logging.getLogger(__name__)


class TsibProcessor(BaseProcessor):
    @classmethod
    def config_name(cls):
        return "tsib"

    @classmethod
    def can_handle(cls, config: Any, folder_path: Path) -> bool:
        return _is_tsib_main_folder(folder_path)

    @classmethod
    def extract(cls, config: Any, folder_path: Path) -> Statement | None:
        # find TSB_Creditcard_Estatement*.pdf files in the folder_path
        search_pattern = os.path.join(folder_path, "TSB_Creditcard_Estatement*.pdf")
        matching_files = glob.glob(search_pattern, recursive=True)
        if not matching_files:
            logger.warning("No Taishin Bank credit card statement files found")
            return None

        if len(matching_files) > 1:
            logger.warning("Multiple Taishin Bank credit card statement files found, using the last one")

        pdf_path = matching_files[-1]
        password = config.get("estatement_password", None)

        raw_statement = extract_credit_card_statement(pdf_path, password=password)

        if raw_statement is None:
            logger.warning("Failed to extract statement from PDF")
            return None

        transactions: list[Transaction] = []
        for card in raw_statement.transactions:
            for transaction in card.transactions:
                transactions.append(
                    Transaction(
                        id=None,
                        description=transaction.description,
                        amount=to_float(transaction.new_taiwan_dollar_amount)[0],
                        date=parse_taiwanese_date(transaction.transaction_date) or datetime.min,
                    )
                )

        return Statement(
            type=StatementType.CREDIT_CARD_BILL,
            source_type=SourceType.CREDIT_CARD,
            source_name="TSIB",
            source_id=raw_statement.bill_info.get("帳單結帳日", "")[:6].replace("/", "_"),
            total_amount=to_float(raw_statement.bill_info.get("本期累計應繳金額", "0"))[0],
            previous_amount=to_float(raw_statement.bill_info.get("上期應繳總額", "0"))[0],
            previous_paid=to_float(raw_statement.bill_info.get("已繳退款總額", "0"))[0],
            previous_unpaid=to_float(raw_statement.bill_info.get("前期餘額", "0"))[0],
            current_amount=to_float(raw_statement.bill_info.get("本期新增款項", "0"))[0],
            currency="TWD",
            payment_due_date=parse_taiwanese_date(raw_statement.bill_info.get("繳款截止日", "")),
            transactions=transactions,
        )


def _is_tsib_main_folder(folder_path):
    # Check if the folder contains the expected TSB_Creditcard_Estatement*.pdf files
    search_pattern = os.path.join(folder_path, "TSB_Creditcard_Estatement*.pdf")
    matching_files = glob.glob(search_pattern, recursive=True)
    return len(matching_files) > 0


if __name__ == "__main__":  # pragma: no cover
    setup_console_logger(logger)

    # Search for TSB_Creditcard_Estatement files in all subdirectories under data\fetched_result\gmail
    search_pattern = os.path.join("data", "fetched_result", "gmail", "**", "TSB_Creditcard_Estatement*.pdf")
    matching_files = glob.glob(search_pattern, recursive=True)

    if not matching_files:
        print("No Taishin Bank credit card statement files found")
        sys.exit(1)

    pdf_path = matching_files[-1]
    print(f"File found: {pdf_path}")

    password = getpass.getpass("Enter PDF password: ")

    statement = TsibProcessor.extract(
        config={
            "estatement_password": password,
        },
        folder_path=Path(pdf_path).parent,
    )

    print(statement)
