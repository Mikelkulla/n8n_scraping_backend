from datetime import datetime
import logging
import os
from logging.handlers import RotatingFileHandler
from backend.config import Config


def setup_logging(log_dir=Config.LOG_PATH, log_prefix=Config.LOG_PREFIX, max_bytes=Config.MAX_BYTES):
    """
    Sets up logging with a date-based log file in the specified directory.
    Rotates the log file when it exceeds max_bytes, appending a timestamp to the rotated file.
    Includes the source file name in log messages for better traceability.
    Creates the directory if it doesn't exist and falls back to the current directory if there's an error.

    Parameters:
        log_dir (str): Directory to save the log file.
        log_prefix (str): Prefix for the log file name.
        max_bytes (int): Maximum file size in bytes before rotation (default: 100MB).

    Returns:
        None
    """
    # Create date-based log file name (e.g., logprefix_24_08_2025.log)
    date_str = datetime.now().strftime("%d_%m_%Y")
    log_file = os.path.join(log_dir, f"{log_prefix}_{date_str}.log")

    # Custom RotatingFileHandler to rename rotated files with end timestamp
    class TimestampedRotatingFileHandler(RotatingFileHandler):
        def doRollover(self):
            # First, close the existing stream to release the file handle.
            if self.stream:
                self.stream.close()
                self.stream = None
            
            end_time = datetime.now().strftime("%H_%M_%S")
            # Rename the current log file with the end timestamp.
            if os.path.exists(self.baseFilename):
                rotated_file = f"{self.baseFilename[:-4]}_{end_time}.log"
                os.rename(self.baseFilename, rotated_file)
            
            # Explicitly open a new stream. This is more robust than waiting for
            # the next log message to trigger the open.
            if not self.delay:
                self.stream = self._open()

    try:
        # Create log directory if it doesn't exist
        os.makedirs(log_dir, exist_ok=True)

        # Set up the custom rotating file handler
        handler = TimestampedRotatingFileHandler(
            filename=log_file,
            maxBytes=max_bytes,
            backupCount=0  # No numbered backups, as we're using timestamps
        )
        handler.setLevel(logging.INFO)
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(filename)s - %(message)s')
        handler.setFormatter(formatter)

        # Configure the root logger
        logging.getLogger('').setLevel(logging.INFO)
        logging.getLogger('').addHandler(handler)

        logging.info(f"Logging initialized to {log_file} with max size {max_bytes} bytes")
    except (OSError, PermissionError) as e:
        # Fallback to current directory with date-based log file
        fallback_log_file = f"{log_prefix}_{date_str}.log"
        handler = TimestampedRotatingFileHandler(
            filename=fallback_log_file,
            maxBytes=max_bytes,
            backupCount=0
        )
        handler.setLevel(logging.INFO)
        handler.setFormatter(formatter)

        logging.getLogger('').setLevel(logging.INFO)
        logging.getLogger('').addHandler(handler)

        logging.error(f"Failed to save log to {log_file}: {e}")
        logging.info(f"Fallback logging initialized to {fallback_log_file}")
        print(f"Error: Could not save log to {log_file}. Using {fallback_log_file} instead.")