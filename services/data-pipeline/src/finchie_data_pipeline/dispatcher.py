import logging
from pathlib import Path

from finchie_data_pipeline.document_extractors.base import BaseBillDocumentExtractor
from finchie_data_pipeline.document_extractors.tsib_extractor import TsibExtractor
from finchie_data_pipeline.models import CreditCardBill

logger = logging.getLogger(__name__)

# List of all available document extractors
ALL_EXTRACTORS: list[type[BaseBillDocumentExtractor]] = [
    TsibExtractor,
]


def extract_document(folder_path: Path) -> CreditCardBill | None:
    """
    Process a document folder by finding an appropriate extractor.

    This function iterates through all available extractors and uses the first one
    that can handle the specified folder to extract credit card bill data.

    Args:
        folder_path (Path): Path to the folder containing documents to be processed

    Returns:
        CreditCardBill | None: The extracted credit card bill data if successful, None otherwise
    """
    result = None
    for extractor_cls in ALL_EXTRACTORS:
        if extractor_cls.can_handle(folder_path):
            logger.debug("Using extractor %s to process folder %s", extractor_cls.__name__, folder_path)
            extractor = extractor_cls()
            result = extractor.extract(folder_path)
            if result:
                break
            else:
                logger.warning("Extractor %s failed to extract data from folder %s", extractor_cls.__name__, folder_path)

    if not result:
        logger.warning("No suitable extractor found for folder %s", folder_path)
    return result
