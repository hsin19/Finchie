import logging
import os
from pathlib import Path
from typing import Any

from finchie_data_pipeline.document_extractors.base import BaseBillDocumentExtractor
from finchie_data_pipeline.document_extractors.tsib_extractor import TsibExtractor
from finchie_data_pipeline.models import CreditCardBill
from finchie_data_pipeline.source_extractors.gmail_extractor import extract_gmail_messages
from finchie_data_pipeline.utils.type_utils import to_bool

logger = logging.getLogger(__name__)

# List of all available document extractors
ALL_EXTRACTORS: list[type[BaseBillDocumentExtractor]] = [
    TsibExtractor,
]


def process(config: Any) -> None:
    source_result_dir_list = _extract_source(config)
    normalized_result = _extract_documents(config, source_result_dir_list)

    # TODO: load documents
    pass


def _extract_source(config: Any) -> list[str]:
    source_extractors_config = config.get("source_extractors", {})

    output_dir = source_extractors_config.get("output_dir", "data/extract")

    result: list[str] = []

    for source in source_extractors_config:
        source_extractor_config = source_extractors_config[source]
        if not isinstance(source_extractor_config, dict):
            continue

        if to_bool(source_extractor_config.get("disable", False)):
            logger.warning("Source %s is disabled", source)
            continue
        if not source_extractor_config.get("output_dir"):
            source_extractor_config["output_dir"] = os.path.join(output_dir, source)

        match source:
            case "gmail":
                result += extract_gmail_messages(source_extractor_config)

    return result


def _extract_documents(config: Any, source_result_dir_list: list[str]) -> list[CreditCardBill]:
    document_config = config.get("document_extractors", {})

    result = []
    for folder_path in source_result_dir_list:
        folder_path = Path(folder_path)
        if not folder_path.exists():
            logger.warning("Folder %s does not exist", folder_path)
            continue

        document = _extract_document(document_config, folder_path)
        if document:
            result.append(document)

    return result


def _extract_document(config: Any, folder_path: Path) -> CreditCardBill | None:
    result = None
    for extractor_cls in ALL_EXTRACTORS:
        document_config = config.get(extractor_cls.config_name(), {})

        if extractor_cls.can_handle(document_config, folder_path):
            logger.debug("Using extractor %s to process folder %s", extractor_cls.__name__, folder_path)
            result = extractor_cls.extract(document_config, folder_path)
            if result:
                break
            else:
                logger.warning("Extractor %s failed to extract data from folder %s", extractor_cls.__name__, folder_path)

    if not result:
        logger.warning("No suitable extractor found for folder %s", folder_path)
    return result
