import logging
import os
from datetime import datetime

from common.config import Config
from finchie_data_pipeline.dispatcher import process

start_time = datetime.now()

# Setup logging configuration
log_dir = os.path.join("data", "logs")
os.makedirs(log_dir, exist_ok=True)
log_file = os.path.join(log_dir, f"pipeline_{datetime.now().strftime('%Y-%m-%d')}.log")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(), logging.FileHandler(log_file)],
)

logger = logging.getLogger(__name__)

logger.info("Starting Finchie Data Pipeline")

try:
    config = Config.get_default_builder().build().get()

    logger.debug("Configuration loaded successfully")

    process(config)

    elapsed_time = datetime.now() - start_time

    logger.info("Finchie Data Pipeline completed successfully in %s seconds", elapsed_time.total_seconds())
except Exception as e:
    logger.error("An error occurred during the Finchie Data Pipeline execution: %s", str(e))
    raise
