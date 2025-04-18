import logging
import os
import sys
from datetime import datetime
from logging.handlers import RotatingFileHandler
from typing import Optional

from app.config.settings import get_settings

# Global logger configurations
_loggers = {}

def get_logger(name: str, log_level: Optional[str] = None) -> logging.Logger:
    """Get a configured logger.
    
    Args:
        name: Logger name
        log_level: Log level
        
    Returns:
        Configured logger
    """
    # Return existing logger if already configured
    if name in _loggers:
        return _loggers[name]
    
    # Create new logger
    logger = logging.getLogger(name)
    
    # Set log level
    settings = get_settings()
    level = log_level or (logging.DEBUG if settings.ui.debug else logging.INFO)
    logger.setLevel(level)
    
    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Create console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # Create file handler
    log_dir = settings.logging.file
    if not os.path.exists(log_dir):
        os.makedirs(log_dir, exist_ok=True)
        
    log_file = os.path.join(
        log_dir,
        f"{name.replace('.', '_')}_{datetime.now().strftime('%Y%m%d')}.log"
    )
    
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=10 * 1024 * 1024,  # 10 MB
        backupCount=5
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
    # Store logger
    _loggers[name] = logger
    
    return logger


def configure_logging():
    """Configure global logging settings."""
    settings = get_settings()
    
    # Set up root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    
    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Create console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    # Create file handler
    log_dir = settings.logging.file
    if not os.path.exists(log_dir):
        os.makedirs(log_dir, exist_ok=True)
        
    log_file = os.path.join(
        log_dir,
        f"manus_{datetime.now().strftime('%Y%m%d')}.log"
    )
    
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=50 * 1024 * 1024,  # 50 MB
        backupCount=10
    )
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)
    
    # Suppress noisy loggers
    logging.getLogger('aiohttp').setLevel(logging.WARNING)
    logging.getLogger('asyncio').setLevel(logging.WARNING)
