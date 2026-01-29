"""
Logging Configuration for VolGuard
"""
import logging
import sys
from logging.handlers import RotatingFileHandler
from config import Config

def setup_logger(name: str = "volguard", level: int = logging.INFO):
    """
    Setup logger with console and file handlers
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # Prevent duplicate handlers
    if logger.handlers:
        return logger
    
    # Format
    formatter = logging.Formatter(
        '%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # File handler (rotating)
    try:
        file_handler = RotatingFileHandler(
            f"{Config.LOG_DIR}/volguard.log",
            maxBytes=10*1024*1024,  # 10MB
            backupCount=5
        )
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except Exception as e:
        logger.warning(f"Could not create file handler: {e}")
    
    return logger

# Create default logger
logger = setup_logger()
