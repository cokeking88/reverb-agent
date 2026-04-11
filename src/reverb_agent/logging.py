"""Logging utilities for Reverb Agent."""

import logging
import os
from pathlib import Path

# Log file path
LOG_DIR = Path.home() / ".reverb-agent" / "logs"
LOG_FILE = LOG_DIR / "reverb.log"


def setup_logger(name: str) -> logging.Logger:
    """Get a logger that writes to the reverb log file."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    
    # File handler
    fh = logging.FileHandler(LOG_FILE)
    fh.setLevel(logging.DEBUG)
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    fh.setFormatter(formatter)

    if not logger.handlers:
        logger.addHandler(fh)

    return logger


# Default logger
logger = setup_logger('reverb')
