from abc import ABC, abstractmethod
from typing import Any

from finchie_statement_fetcher.models import Statement


class BaseStorer(ABC):
    """Base class for all statement storers."""

    @classmethod
    @abstractmethod
    def config_name(cls) -> str:
        """
        Returns the configuration name for this storer.
        This name will be used to match against the configuration keys.
        """
        pass

    @classmethod
    @abstractmethod
    def store(cls, config: Any, statements: list[Statement]) -> None:
        """
        Store the statements according to the provided configuration.

        Args:
            config (Any): Configuration for this storer
            statements (List[Statement]): The statements to store
        """
        pass
