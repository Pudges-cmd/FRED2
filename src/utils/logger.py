# src/utils/logger.py
"""
Logging configuration and utilities
"""

import logging
import logging.handlers
import os
from pathlib import Path

def setup_logging(config=None):
    """
    Setup logging configuration
    
    Args:
        config (dict): Logging configuration
        
    Returns:
        logging.Logger: Configured logger
    """
    if config is None:
        config = {}
    
    # Get configuration values
    log_level = config.get('log_level', 'INFO')
    log_file = config.get('log_file', '/var/log/disaster-detection/system.log')
    max_log_size = config.get('max_log_size', '10MB')
    backup_count = config.get('backup_count', 5)
    
    # Convert log level string to constant
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)
    
    # Create log directory
    log_path = Path(log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Create logger
    logger = logging.getLogger()
    logger.setLevel(numeric_level)
    
    # Clear existing handlers
    logger.handlers.clear()
    
    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(numeric_level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # File handler with rotation
    try:
        # Parse max log size
        if max_log_size.endswith('MB'):
            max_bytes = int(max_log_size[:-2]) * 1024 * 1024
        elif max_log_size.endswith('KB'):
            max_bytes = int(max_log_size[:-2]) * 1024
        else:
            max_bytes = int(max_log_size)
        
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=max_bytes,
            backupCount=backup_count
        )
        file_handler.setLevel(numeric_level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
        
    except Exception as e:
        logger.warning(f"Could not setup file logging: {e}")
    
    return logger