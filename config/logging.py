# Set up logging
from datetime import datetime
import logging
import os
from backend.config import Config


def setup_logging(log_dir=Config.LOG_PATH, log_prefix=Config.LOG_PREFIX):
    """
    Sets up logging with a timestamped log file in the specified directory.
    Includes the source file name in log messages for better traceability.
    Creates the directory if it doesn't exist and falls back to the current directory if there's an error.
    
    Parameters:
        log_dir (str): Directory to save the log file.
        log_prefix (str): Prefix for the log file name.
    
    Returns:
        None
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = os.path.join(log_dir, f"{log_prefix}_{timestamp}.log")
    
    try:
        os.makedirs(log_dir, exist_ok=True)
        logging.basicConfig(
            filename=log_file,
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(filename)s - %(message)s'
        )
        logging.info(f"Logging initialized to {log_file}")
    except (OSError, PermissionError) as e:
        fallback_log_file = f"{log_prefix}_{timestamp}.log"
        logging.basicConfig(
            filename=fallback_log_file,
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(filename)s - %(message)s'
        )
        logging.error(f"Failed to save log to {log_file}: {e}")
        logging.info(f"Fallback logging initialized to {fallback_log_file}")
        print(f"Error: Could not save log to {log_file}. Using {fallback_log_file} instead.")