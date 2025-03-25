from abc import ABC, abstractmethod
from pathlib import Path

from finchie_data_pipeline.models import CreditCardBill


class BaseBillDocumentExtractor(ABC):
    @classmethod
    @abstractmethod
    def can_handle(cls, folder_path: Path) -> bool:
        """
        Determines whether this extractor can process the given folder
        e.g., based on file names, sender information, PDF names, etc.
        """
        pass

    @classmethod
    @abstractmethod
    def extract(cls, folder_path: Path) -> CreditCardBill | None:
        """
        Extracts all statement data and converts it to the Common format
        """
        pass
