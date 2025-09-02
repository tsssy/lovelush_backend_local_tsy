"""Global logging configuration."""

import logging
import logging.config
import sys
from pathlib import Path
from typing import Optional

from app.core.config.settings import settings


class ColoredFormatter(logging.Formatter):
    """Custom formatter with colors for different log levels."""

    # Color codes
    COLORS = {
        "DEBUG": "\033[36m",  # Cyan
        "INFO": "\033[32m",  # Green
        "WARNING": "\033[33m",  # Yellow
        "ERROR": "\033[31m",  # Red
        "CRITICAL": "\033[35m",  # Magenta
        "RESET": "\033[0m",  # Reset
    }

    def format(self, record) -> str:
        return super().format(record)


class ExceptionFormatter(logging.Formatter):
    """Custom formatter that automatically includes exception info for errors."""

    def format(self, record) -> str:
        # Automatically add exception info for ERROR and CRITICAL levels
        if record.levelno >= logging.ERROR and record.exc_info is None:
            # Check if we're in an exception context
            if sys.exc_info()[0] is not None:
                record.exc_info = sys.exc_info()

        return super().format(record)


class LoggerConfig:
    """Global logger configuration manager."""

    _initialized = False

    @classmethod
    def setup_logging(
        cls,
        log_level: str = "INFO",
        log_file: Optional[str] = None,
        log_format: Optional[str] = None,
        use_colors: bool = True,
    ) -> None:
        """Setup global logging configuration."""

        if cls._initialized:
            return

        if log_format is None:
            log_format = "[%(asctime)s][%(levelname)s] %(name)s: %(message)s"

        # Create logs directory if it doesn't exist
        if log_file:
            log_path = Path(log_file)
            log_path.parent.mkdir(parents=True, exist_ok=True)

        # Choose formatter based on color support
        if use_colors:
            console_formatter = {
                "class": "colorlog.ColoredFormatter",
                "format": "%(log_color)s[%(asctime)s][%(levelname)s] %(name)s: %(reset)s%(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S",
                "log_colors": {
                    "DEBUG": "cyan",
                    "INFO": "green",
                    "WARNING": "yellow",
                    "ERROR": "red",
                    "CRITICAL": "bold_red",
                },
            }
        else:
            console_formatter = {"format": log_format, "datefmt": "%Y-%m-%d %H:%M:%S"}

        # Configure logging
        logging_config = {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "standard": console_formatter,
                "detailed": {
                    "format": "[%(asctime)s] - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s",
                    "datefmt": "%Y-%m-%d %H:%M:%S",
                },
                "detailed_with_exc": {
                    "format": "[%(asctime)s] - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s",
                    "datefmt": "%Y-%m-%d %H:%M:%S",
                },
                "colored": console_formatter,
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "level": log_level,
                    "formatter": "colored" if use_colors else "standard",
                    "stream": sys.stdout,
                }
            },
            "root": {"level": log_level, "handlers": ["console"]},
            "loggers": {
                "uvicorn": {
                    "level": "INFO",
                    "handlers": ["console"],
                    "propagate": False,
                },
                "uvicorn.error": {
                    "level": "INFO",
                    "handlers": ["console"],
                    "propagate": False,
                },
                "uvicorn.access": {
                    "level": "INFO",
                    "handlers": ["console"],
                    "propagate": False,
                },
                "httpx": {
                    "level": "WARNING",
                    "handlers": ["console"],
                    "propagate": False,
                },
                "telegram": {
                    "level": "INFO",
                    "handlers": ["console"],
                    "propagate": False,
                },
            },
        }

        # Add file handler if log_file is specified
        if log_file:
            logging_config["handlers"]["file"] = {
                "class": "logging.handlers.RotatingFileHandler",
                "level": log_level,
                "formatter": "detailed",
                "filename": log_file,
                "maxBytes": 10 * 1024 * 1024,  # 10MB
                "backupCount": 5,
            }
            logging_config["root"]["handlers"].append("file")

            # Add file handler to specific loggers
            for logger_name in logging_config["loggers"]:
                logging_config["loggers"][logger_name]["handlers"].append("file")

        logging.config.dictConfig(logging_config)
        cls._initialized = True


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance with the given name."""
    return logging.getLogger(name)


def log_error_with_traceback(logger: logging.Logger, message: str):
    """Helper function to log errors with automatic exception info."""
    logger.error(message, exc_info=True)


# Setup logging on module import
LoggerConfig.setup_logging(
    log_level=getattr(settings, "log_level", "INFO"),
    log_file=(
        getattr(settings, "log_file", None)
        if getattr(settings, "log_file", "")
        else None
    ),
    use_colors=getattr(settings, "log_colors", True),
)

# Global logger instance for general use
logger = get_logger(__name__)
