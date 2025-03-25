import logging
import os
from datetime import datetime
from pathlib import Path

from finchie_data_pipeline.dispatcher import extract_document
from finchie_data_pipeline.source_extractors.gmail_extractor import process_gmail_messages

# Setup logging configuration
log_dir = os.path.join("data", "logs")
os.makedirs(log_dir, exist_ok=True)
log_file = os.path.join(log_dir, f"pipeline_{datetime.now().strftime('%Y-%m-%d')}.log")
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(), logging.FileHandler(log_file)],
)

logger = logging.getLogger(__name__)

today = datetime.today()
query = f"label:bill after:{today.year}/{today.month}/01 before:{today.year}/{today.month}/25"

logger.info("Starting Gmail message processing - query: %s", query)
folders: list[str] = process_gmail_messages(query)

for folder_path_str in folders:
    folder_path = Path(folder_path_str)
    logger.debug("Processing folder: %s", folder_path)
    bill = extract_document(folder_path)
    if bill:
        logger.info("Successfully extracted bill - card: %s, amount due: %s", bill.card_last_four, bill.total_due_amount)
    else:
        logger.warning("Failed to extract bill from folder: %s", folder_path)
