import logging
import sys


class WakalatLogger:
    def __init__(self, name="DocRetriever", level=logging.INFO):
        """
        Initialize custom logger.

        Args:
            name (str): Logger name
            level: Logging level (default: INFO)
        """
        self.logger = logging.getLogger(name)
        self.logger.setLevel(level)

        # Clear any existing handlers
        self.logger.handlers.clear()

        # Create formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )

        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(level)
        console_handler.setFormatter(formatter)
        self.logger.addHandler(console_handler)

        # # File handler
        # file_handler = logging.FileHandler(f'doc_retriever_{datetime.now().strftime("%Y%m%d")}.log')
        # file_handler.setLevel(level)
        # file_handler.setFormatter(formatter)
        # self.logger.addHandler(file_handler)

    def debug(self, message):
        """Log debug message."""
        self.logger.debug(message)

    def info(self, message):
        """Log info message."""
        self.logger.info(message)

    def warning(self, message):
        """Log warning message."""
        self.logger.warning(message)

    def error(self, message):
        """Log error message."""
        self.logger.error(message)

    def critical(self, message):
        """Log critical message."""
        self.logger.critical(message)

    def exception(self, message):
        """Log exception with traceback."""
        self.logger.exception(message)