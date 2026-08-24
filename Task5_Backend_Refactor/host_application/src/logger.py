"""
Centralized logging configuration for the EV Battery Diagnostic System host application.
Provides structured logging with console and file outputs.
"""

import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from datetime import datetime


def setup_logger(name='ev_battery_diagnostic', log_level=logging.INFO,
                log_dir='logs', max_bytes=5*1024*1024, backup_count=3):
    """
    Set up and configure a logger with console and rotating file handlers.

    Args:
        name (str): Logger name
        log_level (int): Logging level (default: INFO)
        log_dir (str): Directory to store log files
        max_bytes (int): Maximum size of log file before rotation (default: 5MB)
        backup_count (int): Number of backup files to keep (default: 3)

    Returns:
        logging.Logger: Configured logger instance
    """
    # Create logger
    logger = logging.getLogger(name)
    logger.setLevel(log_level)

    # Prevent duplicate handlers if logger already configured
    if logger.handlers:
        return logger

    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(module)s.%(funcName)s:%(lineno)d - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # File handler (with rotation)
    try:
        # Create log directory if it doesn't exist
        os.makedirs(log_dir, exist_ok=True)
        log_file = os.path.join(log_dir, f'{name}.log')

        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=max_bytes,
            backupCount=backup_count
        )
        file_handler.setLevel(log_level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except Exception as e:
        # If we can't create file handler, log to console only
        logger.warning(f"Could not set up file logging: {e}")

    return logger


def get_logger(name='ev_battery_diagnostic'):
    """
    Get an existing logger instance or create a new one with default settings.

    Args:
        name (str): Logger name

    Returns:
        logging.Logger: Logger instance
    """
    return logging.getLogger(name)