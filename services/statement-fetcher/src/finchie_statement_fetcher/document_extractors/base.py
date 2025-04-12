from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from finchie_statement_fetcher.models import Statement


class BaseStatementExtractor(ABC):
    @classmethod
    @abstractmethod
    def config_name(cls) -> str:
        """
        Returns the name of the configuration section for this extractor
        """
        pass

    @classmethod
    @abstractmethod
    def can_handle(cls, config: Any, folder_path: Path) -> bool:
        """
        Determines whether this extractor can process the given folder
        e.g., based on file names, sender information, PDF names, etc.
        """
        pass

    @classmethod
    @abstractmethod
    def extract(cls, config: Any, folder_path: Path) -> Statement | None:
        """
        Extracts all statement data and converts it to the Common format
        """
        pass
