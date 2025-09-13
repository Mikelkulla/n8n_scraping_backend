from datetime import datetime
import logging
import os
from logging.handlers import RotatingFileHandler
from backend.config import Config


def setup_logging(log_dir=Config.LOG_PATH, log_prefix=Config.LOG_PREFIX, max_bytes=Config.MAX_BYTES, log_level=Config.LOG_LEVEL):
    """Configures logging for the application.

    This function sets up a rotating file handler that creates a new log file
    daily. When a log file exceeds the specified maximum size, it is rotated,
    and the old file is renamed with a timestamp. It also configures log levels
    for the application and specific libraries.

    If the primary log directory cannot be created or written to, it falls back
    to using the current working directory.

    Args:
        log_dir (str, optional): The directory where log files will be stored.
            Defaults to `Config.LOG_PATH`.
        log_prefix (str, optional): The prefix for log file names. Defaults to
            `Config.LOG_PREFIX`.
        max_bytes (int, optional): The maximum size in bytes for a log file
            before it is rotated. Defaults to `Config.MAX_BYTES`.
        log_level (str, optional): The minimum log level to record (e.g., "INFO",
            "DEBUG"). Defaults to `Config.LOG_LEVEL`.
    """
    # Create date-based log file name (e.g., logprefix_24_08_2025.log)
    date_str = datetime.now().strftime("%d_%m_%Y")
    log_file = os.path.join(log_dir, f"{log_prefix}_{date_str}.log")

    # Map log level string to logging constants
    log_level_map = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR,
        "CRITICAL": logging.CRITICAL,
    }
    numeric_log_level = log_level_map.get(log_level.upper(), logging.INFO)

    # Custom RotatingFileHandler to rename rotated files with end timestamp
    class TimestampedRotatingFileHandler(RotatingFileHandler):
        """A rotating file handler that appends a timestamp to log files on rotation.

        This custom handler overrides the default rotation behavior to rename the
        old log file with a timestamp of when the rotation occurred, rather than
        using a simple numeric index.
        """
        def doRollover(self):
            """Performs the log file rotation.

            This method is called when the current log file exceeds its maximum
            size. It closes the current file, renames it with a timestamp
            (e.g., 'log_file_HH_MM_SS.log'), and opens a new log file for
            subsequent messages.
            """
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
        handler.setLevel(numeric_log_level)
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(filename)s - %(message)s')
        handler.setFormatter(formatter)

        # Configure the root logger
        logging.getLogger('').setLevel(numeric_log_level)
        logging.getLogger('').addHandler(handler)

        # Set log levels for specific libraries
        for lib, level_str in Config.LIBRARY_LOG_LEVELS.items():
            lib_level = log_level_map.get(level_str.upper(), logging.WARNING)
            logging.getLogger(lib).setLevel(lib_level)

        logging.info(f"Logging initialized to {log_file} with level {log_level} and max size {max_bytes} bytes")
    except (OSError, PermissionError) as e:
        # Fallback to current directory with date-based log file
        fallback_log_file = f"{log_prefix}_{date_str}.log"
        handler = TimestampedRotatingFileHandler(
            filename=fallback_log_file,
            maxBytes=max_bytes,
            backupCount=0
        )
        handler.setLevel(numeric_log_level)
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(filename)s - %(message)s')
        handler.setFormatter(formatter)

        logging.getLogger('').setLevel(numeric_log_level)
        logging.getLogger('').addHandler(handler)

        # Set log levels for specific libraries in fallback mode
        for lib, level_str in Config.LIBRARY_LOG_LEVELS.items():
            lib_level = log_level_map.get(level_str.upper(), logging.WARNING)
            logging.getLogger(lib).setLevel(lib_level)

        logging.error(f"Failed to save log to {log_file}: {e}")
        logging.info(f"Fallback logging initialized to {fallback_log_file} with level {log_level}")
        print(f"Error: Could not save log to {log_file}. Using {fallback_log_file} instead.")