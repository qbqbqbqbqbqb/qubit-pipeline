import logging
from colorlog import ColoredFormatter

def get_logger(name: str = "default") -> logging.Logger:
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
        logger.addHandler(console_handler)

        file_handler = logging.FileHandler('app.log', mode='a')
        file_formatter = logging.Formatter(
            "[%(asctime)s][%(name)s][%(levelname)s] %(message)s"
        )
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)

        logger.setLevel(logging.DEBUG)

    return logger