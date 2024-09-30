import logging
from logging.handlers import RotatingFileHandler
import os

def setup_logger():
    # Create logs directory if it doesn't exist
    if not os.path.exists('logs'):
        os.makedirs('logs')
        print(f"Created logs directory: {os.path.abspath('logs')}")

    # Main logger
    logger = logging.getLogger('main_logger')
    logger.setLevel(logging.DEBUG)

    # Formatter
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # File handler for all logs
    all_log_path = os.path.abspath('logs/all.log')
    all_handler = RotatingFileHandler(all_log_path, maxBytes=10*1024*1024, backupCount=5)
    all_handler.setLevel(logging.DEBUG)
    all_handler.setFormatter(formatter)
    print(f"All logs file: {all_log_path}")

    # File handler for error logs
    error_log_path = os.path.abspath('logs/error.log')
    error_handler = RotatingFileHandler('logs/error.log', maxBytes=10*1024*1024, backupCount=5)
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(formatter)

    # Console handler for info logs (excluding errors)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    console_handler.addFilter(lambda record: record.levelno < logging.ERROR)

    # Add handlers to logger
    logger.addHandler(all_handler)
    logger.addHandler(error_handler)
    logger.addHandler(console_handler)

    return logger

# Create and configure logger
logger = setup_logger()

def log_error(message):
    """
    Log an error message without showing it to the user.
    """
    logger.error(message)

def log_info(message):
    """
    Log an info message that will be shown to the user.
    """
    logger.info(message)