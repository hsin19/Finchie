import json
import logging
import os
from dataclasses import asdict
from datetime import datetime
from typing import Any
from uuid import uuid4

from finchie_statement_fetcher.models import Statement
from finchie_statement_fetcher.storer.base_storer import BaseStorer
from finchie_statement_fetcher.utils.json_utils import JsonEncoder

logger = logging.getLogger(__name__)


class LocalJsonStorer(BaseStorer):
    """Storer that stores statements as JSON files on the local file system."""

    @classmethod
    def config_name(cls) -> str:
        return "local_json"

    @classmethod
    def store(cls, config: Any, statements: list[Statement]) -> None:
        """
        Store statements as JSON files to the local file system.

        Args:
            config (Any): Configuration for this storer, should include 'output_dir'
            statements (List[Statement]): The statements to store
        """
        output_dir = config.get("output_dir", "data/processed_result")

        # Create output directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)

        # Count successfully saved statements
        saved_count = 0

        for statement in statements:
            if not statement.source_name or not statement.source_id:
                logger.warning("Statement has no source name or ID, generating a timestamp-based ID")
                filename = f"statement_{datetime.now().strftime('%Y%m%d%H%M%S')}_{uuid4().hex[:6]}"
            else:
                filename = f"{statement.source_name}_{statement.source_id}"

            filename = f"{filename}.json"
            filepath = os.path.join(output_dir, filename)

            try:
                with open(filepath, "w", encoding="utf-8") as f:
                    json.dump(asdict(statement), f, cls=JsonEncoder, indent=2, ensure_ascii=False)
                logger.info("Saved statement to %s", filepath)
                saved_count += 1
            except Exception as e:
                logger.error("Failed to save statement to %s: %s", filepath, e)

        logger.info("Successfully saved %d/%d statements to %s", saved_count, len(statements), output_dir)
