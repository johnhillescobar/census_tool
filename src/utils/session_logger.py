import logging
import sys
from datetime import datetime
from pathlib import Path


class StdoutLogger:
    """
    Captures stdout (print statements) and writes to both console and log file.
    """

    def __init__(self, log_file, original_stdout):
        self.log_file = log_file
        self.original_stdout = original_stdout

    def write(self, message):
        """Write to both original stdout and log file"""
        # Write to original stdout (console)
        self.original_stdout.write(message)
        # Write to log file
        if message.strip():  # Only write non-empty messages
            self.log_file.write(message)
            self.log_file.flush()

    def flush(self):
        """Flush both streams"""
        self.original_stdout.flush()
        self.log_file.flush()


class SessionLogger:
    """
    Captures all logs and print statements for an application session.
    Saves to timestamped file in logs/ directory.
    
    Usage:
        logger = SessionLogger("user_id")
        logger.start()
        # ... run application ...
        logger.stop()
    """

    def __init__(self, user_id: str):
        self.user_id = user_id
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log_dir = Path("logs")
        self.log_file = self.log_dir / f"{user_id}_{self.timestamp}.txt"
        self.file_handler = None
        self.stdout_file = None
        self.stdout_logger = None
        self.original_stdout = None

    def start(self):
        """Start capturing logs and stdout to file"""
        # Create logs directory
        self.log_dir.mkdir(parents=True, exist_ok=True)

        # Open log file for stdout capture
        self.stdout_file = open(self.log_file, "w", encoding="utf-8")

        # Redirect stdout to capture print statements
        self.original_stdout = sys.stdout
        self.stdout_logger = StdoutLogger(self.stdout_file, self.original_stdout)
        sys.stdout = self.stdout_logger

        # Create file handler for logging module
        self.file_handler = logging.FileHandler(
            self.log_file, mode="a", encoding="utf-8"
        )
        self.file_handler.setLevel(logging.DEBUG)

        # Format: timestamp - level - logger - message
        formatter = logging.Formatter(
            "%(asctime)s - %(levelname)s - %(name)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        self.file_handler.setFormatter(formatter)

        # Add to root logger (captures all logs)
        logging.getLogger().addHandler(self.file_handler)
        # Set root logger to DEBUG to capture everything
        logging.getLogger().setLevel(logging.DEBUG)

        # Log session start
        logging.info("=" * 80)
        logging.info(f"SESSION START: User {self.user_id}")
        logging.info(f"Timestamp: {self.timestamp}")
        logging.info(f"Log file: {self.log_file}")
        logging.info("=" * 80)

        return self.log_file

    def stop(self):
        """Stop capturing logs and stdout"""
        if self.file_handler:
            logging.info("=" * 80)
            logging.info(f"SESSION END: User {self.user_id}")
            logging.info("=" * 80)

            # Remove handler
            logging.getLogger().removeHandler(self.file_handler)
            self.file_handler.close()

        # Restore original stdout
        if self.original_stdout:
            sys.stdout = self.original_stdout

        # Close stdout file
        if self.stdout_file:
            self.stdout_file.close()

        return self.log_file
