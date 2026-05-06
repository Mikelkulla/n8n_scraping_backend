from datetime import datetime
import logging
import os
from logging.handlers import RotatingFileHandler
from backend.app_settings import Config
import functools
import json

LOG_LEVEL_MAP = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}


def apply_log_level(log_level):
    """Applies a logging level to the root logger and existing handlers."""
    normalized = str(log_level or "INFO").strip().upper()
    numeric_log_level = LOG_LEVEL_MAP.get(normalized, logging.INFO)
    root_logger = logging.getLogger("")
    root_logger.setLevel(numeric_log_level)
    for handler in root_logger.handlers:
        handler.setLevel(numeric_log_level)
    return normalized if normalized in LOG_LEVEL_MAP else "INFO"

def log_function_call(func):
    """A decorator to log function calls, arguments, and return values.

    This decorator logs the entry and exit of a function, including its
    arguments and return value. This is useful for debugging and tracing the
    flow of execution.

    Args:
        func (callable): The function to be decorated.

    Returns:
        callable: The wrapped function.
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        # Log function entry with arguments
        # Exclude 'self' from args to avoid redundant logging
        args_repr = [
            repr(a) for a in args
            if not (hasattr(a, "__class__")
                    and a.__class__.__name__ == func.__qualname__.split(".")[0])
        ]
        kwargs_repr = [f"{k}={v!r}" for k, v in kwargs.items()]
        signature = ", ".join(args_repr + kwargs_repr)

        # Check if the function is a method of a class
        if "." in func.__qualname__:
            class_name, method_name = func.__qualname__.rsplit(".", 1)
            log_message = f"Calling {class_name}.{method_name}({signature})"
        else:
            log_message = f"Calling {func.__name__}({signature})"
        logging.debug(log_message)

        # Execute the function
        try:
            result = func(*args, **kwargs)

            # --- Handle Flask/FastAPI responses ---
            if hasattr(result, "status_code"):
                headers = dict(getattr(result, "headers", {}))
                body = result.get_data(as_text=True) if hasattr(result, "get_data") else str(result)

                # Try to pretty-print JSON body if possible
                try:
                    body = json.dumps(json.loads(body), indent=2, ensure_ascii=False)
                except Exception:
                    pass  # fallback: raw body string

                headers_str = "\n".join(f"{k}: {v}" for k, v in headers.items())
                log_text = {
                    "function_name": f"{func.__qualname__} returned:\n",
                    "status": f"\nRESPONSE STATUS {result.status_code}\n",
                    "headers": f"RESPONSE HEADERS\n{headers_str}\n",
                    "body" :f"\nRESPONSE BODY\n{body}"
                }
                logging.debug(f"{log_text.get('function_name')}")
                logging.info(f"{log_text.get('status')}{log_text.get('headers')}")
                logging.debug(f"{log_text.get('body')}")
            elif isinstance(result, tuple) and hasattr(result[0], "status_code"):
                resp_obj, status = result
                headers = dict(getattr(resp_obj, "headers", {}))
                body = resp_obj.get_data(as_text=True)

                try:
                    body = json.dumps(json.loads(body), indent=2, ensure_ascii=False)
                except Exception:
                    pass

                headers_str = "\n".join(f"{k}: {v}" for k, v in headers.items())
                log_text = {
                    "function_name": f"{func.__qualname__} returned:\n",
                    "status": f"\nRESPONSE STATUS {status}\n",
                    "headers": f"RESPONSE HEADERS\n{headers_str}\n",
                    "body": f"\nRESPONSE BODY\n{body}"
                }
                logging.debug(f"{log_text.get('function_name')}")
                logging.info(f"{log_text.get('status')}{log_text.get('headers')}")
                logging.debug(f"{log_text.get('body')}")

            else:
                # Normal function
                logging.debug(f"{func.__qualname__} returned {result!r}")

            return result

        except Exception as e:
            logging.error(f"Exception in {func.__qualname__}: {e}", exc_info=True)
            raise

    return wrapper

def log_all_methods(cls):
    """A class decorator to apply the log_function_call decorator to all methods.

    This decorator iterates over the attributes of a class and wraps any
    callable (i.e., method) with the `log_function_call` decorator. This allows
    for automatic logging of all methods in a class.

    Args:
        cls (type): The class to be decorated.

    Returns:
        type: The decorated class.
    """
    for attr_name, value in cls.__dict__.items():
        if callable(value):
            setattr(cls, attr_name, log_function_call(value))
    return cls

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
    numeric_log_level = LOG_LEVEL_MAP.get(log_level.upper(), logging.INFO)

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
            lib_level = LOG_LEVEL_MAP.get(level_str.upper(), logging.WARNING)
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
            lib_level = LOG_LEVEL_MAP.get(level_str.upper(), logging.WARNING)
            logging.getLogger(lib).setLevel(lib_level)

        logging.error(f"Failed to save log to {log_file}: {e}")
        logging.info(f"Fallback logging initialized to {fallback_log_file} with level {log_level}")
        print(f"Error: Could not save log to {log_file}. Using {fallback_log_file} instead.")
