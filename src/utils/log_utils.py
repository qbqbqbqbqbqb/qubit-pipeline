"""
Utilities for logging configuration.

This module provides functions to set up and configure loggers with colored console output,
file logging for all messages, and separate warning logs. It uses rotating file handlers
to manage log file sizes and prevent excessive disk usage.
"""

import logging
import os
from colorlog import ColoredFormatter
from logging.handlers import RotatingFileHandler


def get_logger(name: str = "default",
               log_dir: str = "logs",
               log_file: str = "app.log",
               warn_log_file: str = "app_warnings.log",
               max_bytes: int = 5 * 1024 * 1024,
               backup_count: int = 0) -> logging.Logger:
    """
    Creates and returns a logger with colored console output and file logging.

    This function configures a logger with:
    - Colored, timestamped console output using colorlog.
    - Rotating file handler for all log levels (DEBUG and above).
    - Separate rotating file handler for warnings and above.
    - Ensures only one set of handlers is added to avoid duplicate logs.

    Args:
        name (str): Name of the logger. Defaults to "default".
        log_file (str): Path to the file for all log messages. Defaults to "app.log".
        warn_log_file (str): Path to the file for warning and above messages. Defaults to "app_warnings.log".
        max_bytes (int): Maximum size in bytes for each log file before rotation. Defaults to 5MB.
        backup_count (int): Number of backup log files to keep. Defaults to 0 (no backups).

    Returns:
        logging.Logger: A configured logger instance ready for use.

    Raises:
        Exception: If there's an error during logger setup, falls back to basic logging configuration.
    """

    os.makedirs(log_dir, exist_ok=True)

    log_path = os.path.join(log_dir, log_file)
    warn_log_path = os.path.join(log_dir, warn_log_file)

    logger = logging.getLogger(name)

    if not logger.hasHandlers():
        try:
            console_handler = logging.StreamHandler()
            formatter = ColoredFormatter(
                "%(log_color)s[%(asctime)s][%(name)s][%(levelname)s] %(message)s",
                log_colors={
                    'DEBUG': 'cyan',
                    'INFO': 'green',
                    'WARNING': 'yellow',
                    'ERROR': 'red',
                    'CRITICAL': 'bold_red',
                }
            )
            console_handler.setFormatter(formatter)
            console_handler.setLevel(logging.DEBUG)
            logger.addHandler(console_handler)

            file_handler_all = RotatingFileHandler(
                log_path,
                mode='a',
                maxBytes=max_bytes,
                backupCount=backup_count,
                encoding='utf-8'
            )
            fmt = logging.Formatter("[%(asctime)s][%(name)s][%(levelname)s] %(message)s")
            file_handler_all.setFormatter(fmt)
            file_handler_all.setLevel(logging.DEBUG)
            logger.addHandler(file_handler_all)

            file_handler_warn = RotatingFileHandler(
                warn_log_path, mode='a',
                maxBytes=max_bytes,
                backupCount=backup_count,
                encoding='utf-8'
            )
            file_handler_warn.setFormatter(fmt)
            file_handler_warn.setLevel(logging.WARNING)
            logger.addHandler(file_handler_warn)

            logger.setLevel(logging.DEBUG)
        except Exception as e:
            print(f"Error setting up logger {name}: {e}")

            logging.basicConfig(level=logging.DEBUG)

    return logger