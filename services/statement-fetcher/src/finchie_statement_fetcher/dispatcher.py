import logging
import os
from pathlib import Path
from typing import Any

from finchie_statement_fetcher.fetcher import fetch_gmail_messages
from finchie_statement_fetcher.models import Statement
from finchie_statement_fetcher.processor import BaseProcessor, TsibProcessor
from finchie_statement_fetcher.utils.type_utils import to_bool

logger = logging.getLogger(__name__)

# List of all available document extractors
ALL_PROCESSORS: list[type[BaseProcessor]] = [
    TsibProcessor,
]


def process(config: Any) -> None:
    fetch_result_dir_list = _fetch_data(config)
    normalized_result = _process_fetched_dirs(config, fetch_result_dir_list)

    # TODO: load data
    pass


def _fetch_data(config: Any) -> list[str]:
    fetcher_config = config.get("fetcher", {})

    output_dir = fetcher_config.get("output_dir", "data/fetched_result")

    result: list[str] = []

    for source in fetcher_config:
        source_config = fetcher_config[source]
        if not isinstance(source_config, dict):
            continue

        if to_bool(source_config.get("disable", False))[0]:
            logger.warning("Source %s is disabled", source)
            continue
        if not source_config.get("output_dir"):
            source_config["output_dir"] = os.path.join(output_dir, source)

        match source:
            case "gmail":
                result += fetch_gmail_messages(source_config)

    return result


def _process_fetched_dirs(config: Any, source_result_dir_list: list[str]) -> list[Statement]:
    document_config = config.get("document_processor", {})

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


def _extract_document(config: Any, folder_path: Path) -> Statement | None:
    result = None
    for processor_cls in ALL_PROCESSORS:
        processor_config = config.get(processor_cls.config_name(), {})

        if processor_cls.can_handle(processor_config, folder_path):
            logger.debug("Using processor %s to process folder %s", processor_cls.__name__, folder_path)
            result = processor_cls.extract(processor_config, folder_path)
            if result:
                break
            else:
                logger.warning("Processor %s failed to extract data from folder %s", processor_cls.__name__, folder_path)

    if not result:
        logger.warning("No suitable processor found for folder %s", folder_path)
    return result
