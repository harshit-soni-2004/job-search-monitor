"""Logging configuration for Job Search Monitor."""

import logging
import os
import sys
from datetime import datetime
from pathlib import Path


def setup_logger(log_dir: str = "logs", log_level: str = "INFO") -> logging.Logger:
    """Set up and return the application logger."""
    os.makedirs(log_dir, exist_ok=True)
    today_str = datetime.now().strftime("%Y-%m-%d")
    log_file = Path(log_dir) / f"job_monitor_{today_str}.log"

    logger = logging.getLogger("JobSearchMonitor")
    logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    # Avoid adding handlers multiple times if already configured
    if logger.handlers:
        return logger

    # Console formatter
    console_handler = logging.StreamHandler(sys.stdout)
    console_format = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S"
    )
    console_handler.setFormatter(console_format)
    logger.addHandler(console_handler)

    # File formatter (more detailed)
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_format = logging.Formatter(
        "[%(asctime)s] [%(levelname)-7s] [%(filename)s:%(lineno)d] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    file_handler.setFormatter(file_format)
    logger.addHandler(file_handler)

    return logger

