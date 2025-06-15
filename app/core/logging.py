import logging
import sys
from pathlib import Path
from typing import Optional

from .config import settings


def setup_logging(
    level: Optional[str] = None,
    log_file: Optional[str] = None,
    log_format: Optional[str] = None
) -> logging.Logger:
    """
    Setup logging configuration for the application.
    
    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Path to log file
        log_format: Log message format
    
    Returns:
        Configured logger instance
    """
    # Use settings defaults if not provided
    level = level or settings.log_level
    log_file = log_file or settings.log_file
    log_format = log_format or settings.log_format
    
    # Create logger
    logger = logging.getLogger("phasenav")
    logger.setLevel(getattr(logging, level.upper()))
    
    # Remove existing handlers to avoid duplicates
    logger.handlers.clear()
    
    # Create formatter
    formatter = logging.Formatter(log_format)
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # File handler
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    return logger


def get_logger(name: str = "phasenav") -> logging.Logger:
    """Get a logger instance."""
    return logging.getLogger(name)


# Initialize default logger
logger = setup_logging()