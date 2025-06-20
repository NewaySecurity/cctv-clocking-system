"""
Utility functions for the NEWAY SECURITY CCTV CLOCKING SYSTEM.

This module provides configuration loading, logging setup, and other
utility functions used throughout the application.
"""

import os
import logging
import logging.config
from pathlib import Path
from typing import Dict, Any, Optional

import yaml
from dotenv import load_dotenv

# Load environment variables from .env file if it exists
load_dotenv()

# Constants
PROJECT_ROOT = Path(__file__).parent.parent.absolute()
CONFIG_DIR = PROJECT_ROOT / "config"
LOGS_DIR = PROJECT_ROOT / "logs"
FACES_DIR = PROJECT_ROOT / "faces"

# Ensure directories exist
for directory in [CONFIG_DIR, LOGS_DIR, FACES_DIR]:
    directory.mkdir(exist_ok=True)

# Configure logging
def setup_logging() -> None:
    """Configure the logging system."""
    log_config = {
        'version': 1,
        'disable_existing_loggers': False,
        'formatters': {
            'standard': {
                'format': '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
            },
        },
        'handlers': {
            'console': {
                'level': 'INFO',
                'formatter': 'standard',
                'class': 'logging.StreamHandler',
                'stream': 'ext://sys.stdout',
            },
            'file': {
                'level': 'DEBUG',
                'formatter': 'standard',
                'class': 'logging.handlers.RotatingFileHandler',
                'filename': LOGS_DIR / 'application.log',
                'maxBytes': 10485760,  # 10MB
                'backupCount': 10,
            },
        },
        'loggers': {
            '': {  # root logger
                'handlers': ['console', 'file'],
                'level': 'DEBUG',
                'propagate': True
            }
        }
    }
    
    # Create logs directory if it doesn't exist
    LOGS_DIR.mkdir(exist_ok=True)
    
    # Apply configuration
    logging.config.dictConfig(log_config)

# Get logger for module
def get_logger(name: str) -> logging.Logger:
    """
    Get a logger for the specified module.
    
    Args:
        name: The name of the module.
        
    Returns:
        A configured logger instance.
    """
    return logging.getLogger(name)

# Configuration handling
def load_config(config_name: str = "default") -> Dict[str, Any]:
    """
    Load configuration from YAML file with environment variable overrides.
    
    Args:
        config_name: Name of the configuration file (without extension).
        
    Returns:
        Dictionary containing configuration values.
        
    Raises:
        FileNotFoundError: If the configuration file doesn't exist.
    """
    config_file = CONFIG_DIR / f"{config_name}.yml"
    
    if not config_file.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_file}")
    
    with open(config_file, 'r') as f:
        config = yaml.safe_load(f)
    
    # Override with environment variables
    # Format: NEWAY_SECTION_KEY
    for key, value in os.environ.items():
        if key.startswith('NEWAY_'):
            parts = key.split('_')[1:]
            if len(parts) >= 2:
                section = parts[0].lower()
                subkey = '_'.join(parts[1:]).lower()
                
                if section in config and subkey in config[section]:
                    # Convert value to the same type as in the config
                    original_type = type(config[section][subkey])
                    if original_type == bool:
                        config[section][subkey] = value.lower() in ('true', 'yes', '1')
                    else:
                        config[section][subkey] = original_type(value)
    
    return config

# Initialize logging on module import
setup_logging()
logger = get_logger(__name__)
logger.info("Utilities module initialized")

