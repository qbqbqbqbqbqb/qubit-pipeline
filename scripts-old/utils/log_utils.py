import logging
from colorlog import ColoredFormatter
from logging.handlers import RotatingFileHandler

def get_logger(name: str = "default", 
               log_file: str = "app.log",
               warn_log_file: str = "app_warnings.log",
               max_bytes: int = 5 * 1024 * 1024,
               backup_count: int = 0) -> logging.Logger:
    
    logger = logging.getLogger(name)
    """
    Creates and returns a logger with colored, timestamped output.

    Ensures only one handler is added to avoid duplicate logs.
    Log messages include timestamp, logger name, level, and message,
    with colors for different log levels.

    Args:
        name (str): Name of the logger. Defaults to "default".

    Returns:
        logging.Logger: Configured logger instance.
    """
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
                log_file,
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
                warn_log_file, mode='a',
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
            # Fallback to basic logging
            logging.basicConfig(level=logging.DEBUG)

    return logger