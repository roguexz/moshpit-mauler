import sys
from loguru import logger


def setup_logger(log_file: str = "moshpit.log", level: str = "INFO"):
    """
    Configures loguru to log to stdout and a rolling log file.

    Stdout receives the specified level logs formatted with colors.
    The log file receives DEBUG level logs and higher for complete system trace.
    """
    # Remove default handler to avoid duplicate logs
    logger.remove()

    # Colored console logger
    logger.add(
        sys.stderr,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        level=level,
        colorize=True,
    )

    # Rolling file logger
    logger.add(
        log_file,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
        level="DEBUG",
        rotation="10 MB",
        retention=3,
        compression="zip",
    )


# Initialize standard logging
setup_logger()
