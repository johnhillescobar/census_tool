import logging
from datetime import datetime
from pathlib import Path

from src.llm.category_detector import detect_category_with_llm

project_root = Path(__file__).parent


# Set up logging
LOG_FORMAT = "%(asctime)s - %(levelname)s - %(name)s - %(message)s"
logs_dir = project_root / "logs"
logs_dir.mkdir(exist_ok=True)
cli_logs_dir = logs_dir / "cli_logs"
cli_logs_dir.mkdir(parents=True, exist_ok=True)
cli_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
debug_log_path = cli_logs_dir / f"cli_log_{cli_timestamp}.txt"

console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(logging.Formatter(LOG_FORMAT))

file_handler = logging.FileHandler(debug_log_path, mode="a", encoding="utf-8")
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(logging.Formatter(LOG_FORMAT))

root_logger = logging.getLogger()
root_logger.setLevel(logging.DEBUG)
root_logger.handlers.clear()
root_logger.addHandler(console_handler)
root_logger.addHandler(file_handler)


logger = logging.getLogger(__name__)

if __name__ == "__main__":
    # user_question = "According to the 2023 ACS 1-year data, what is the estimated total population of the United States?"
    user_question = "Social characteristics comparison profile for the U.S. (2023)."
    logger.info(f"User question: {user_question}")
    result = detect_category_with_llm(user_question)
    logger.info(f"Category detection result: {result}")
