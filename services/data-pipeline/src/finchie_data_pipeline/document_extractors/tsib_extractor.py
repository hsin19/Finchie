import glob
import logging
import os
from pathlib import Path
from typing import Any

from finchie_data_pipeline.document_extractors.base import BaseBillDocumentExtractor
from finchie_data_pipeline.document_extractors.tsib_estatement_extractor import extract_credit_card_statement
from finchie_data_pipeline.models.credit_card_bill import CreditCardBill

logger = logging.getLogger(__name__)


class TsibExtractor(BaseBillDocumentExtractor):
    @classmethod
    def config_name(cls):
        return "tsib"

    @classmethod
    def can_handle(cls, _, folder_path: Path) -> bool:
        return _is_tsib_main_folder(folder_path)

    @classmethod
    def extract(cls, config: Any, folder_path: Path) -> CreditCardBill | None:
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

        # TODO: convert raw_statement to CreditCardBill object
        return raw_statement


def _is_tsib_main_folder(folder_path):
    # Check if the folder contains the expected TSB_Creditcard_Estatement*.pdf files
    search_pattern = os.path.join(folder_path, "TSB_Creditcard_Estatement*.pdf")
    matching_files = glob.glob(search_pattern, recursive=True)
    return len(matching_files) > 0
