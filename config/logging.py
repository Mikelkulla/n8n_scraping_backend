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

TAG_PATH_MAP = (
    ("backend/routes/", "api"),
    ("backend\\routes\\", "api"),
    ("backend/scripts/google_api/", "places"),
    ("backend\\scripts\\google_api\\", "places"),
    ("backend/ai_email_service.py", "LLM"),
    ("backend\\ai_email_service.py", "LLM"),
    ("backend/database.py", "database"),
    ("backend\\database.py", "database"),
    ("backend/scripts/scraping/", "enrichment"),
    ("backend\\scripts\\scraping\\", "enrichment"),
    ("backend/scripts/selenium/", "selenium"),
    ("backend\\scripts\\selenium\\", "selenium"),
    ("config/job_functions.py", "jobs"),
    ("config\\job_functions.py", "jobs"),
)

TAG_LOGGER_MAP = (
    ("werkzeug", "api"),
    ("flask", "api"),
    ("backend.routes", "api"),
    ("backend.scripts.google_api", "places"),
    ("backend.ai_email_service", "LLM"),
    ("backend.database", "database"),
    ("backend.scripts.scraping", "enrichment"),
    ("backend.scripts.selenium", "selenium"),
    ("config.job_functions", "jobs"),
)

SENSITIVE_KEYS = {"authorization", "x-goog-api-key", "key", "api_key", "token", "secret", "password"}
VERBOSE_PAYLOAD_KEYS = {
    "body",
    "campaign_lead",
    "content",
    "email_draft",
    "emails",
    "final_email",
    "lead",
    "leads",
    "system_prompt",
    "user_prompt",
    "website_summary",
}
MAX_LOG_VALUE_LENGTH = 2000


def _truncate_log_value(value, max_length=MAX_LOG_VALUE_LENGTH):
    text = str(value)
    if len(text) <= max_length:
        return text
    return f"{text[:max_length]}...<truncated {len(text) - max_length} chars>"


def sanitize_for_logging(value, redact_keys=None, max_length=MAX_LOG_VALUE_LENGTH):
    """Returns a JSON-serializable, redacted copy of a value for DEBUG logs."""
    redact_keys = {str(key).lower() for key in (redact_keys or set())} | SENSITIVE_KEYS
    if isinstance(value, dict):
        sanitized = {}
        for key, item in value.items():
            key_text = str(key)
            if key_text.lower() in redact_keys:
                sanitized[key] = "<redacted>"
            elif key_text.lower() in VERBOSE_PAYLOAD_KEYS:
                sanitized[key] = "<omitted>"
            else:
                sanitized[key] = sanitize_for_logging(item, redact_keys=redact_keys, max_length=max_length)
        return sanitized
    if isinstance(value, (list, tuple, set)):
        return [sanitize_for_logging(item, redact_keys=redact_keys, max_length=max_length) for item in value]
    if isinstance(value, str):
        return _truncate_log_value(value, max_length=max_length)
    return value


def format_debug_payload(value):
    """Formats a sanitized payload for a one-line debug log entry."""
    try:
        return json.dumps(sanitize_for_logging(value), ensure_ascii=False, default=str)
    except TypeError:
        return _truncate_log_value(value)


def tag_for_logger_name(logger_name):
    """Returns the configured source tag for a logger/module name."""
    for prefix, tag in TAG_LOGGER_MAP:
        if logger_name == prefix or logger_name.startswith(f"{prefix}."):
            return tag
    return "app"


class LogTagFilter(logging.Filter):
    """Adds a log_tag attribute to records based on explicit extra data or source."""

    def filter(self, record):
        if getattr(record, "log_tag", None):
            return True

        logger_name = getattr(record, "name", "")
        tag = tag_for_logger_name(logger_name)
        if tag != "app":
            record.log_tag = tag
            return True

        pathname = os.path.normpath(getattr(record, "pathname", "")).replace(os.sep, "/")
        for path_fragment, tag in TAG_PATH_MAP:
            normalized_fragment = path_fragment.replace("\\", "/")
            if normalized_fragment in pathname:
                record.log_tag = tag
                return True

        record.log_tag = "app"
        return True


class TaggedFormatter(logging.Formatter):
    """Uses compact INFO logs and filename-rich non-INFO logs."""

    INFO_FORMAT = "%(asctime)s - %(levelname)s - [%(log_tag)s] - %(message)s"
    DETAIL_FORMAT = "%(asctime)s - %(levelname)s - [%(log_tag)s] - %(filename)s - %(message)s"

    def __init__(self):
        super().__init__()
        self.info_formatter = logging.Formatter(self.INFO_FORMAT)
        self.detail_formatter = logging.Formatter(self.DETAIL_FORMAT)

    def format(self, record):
        if not getattr(record, "log_tag", None):
            LogTagFilter().filter(record)
        formatter = self.info_formatter if record.levelno == logging.INFO else self.detail_formatter
        return formatter.format(record)


class TagOnlyFilter(LogTagFilter):
    """Allows only records for selected log tags."""

    def __init__(self, tags):
        super().__init__()
        self.tags = set(tags)

    def filter(self, record):
        super().filter(record)
        return record.log_tag in self.tags


class MinimumLevelFilter(LogTagFilter):
    """Allows records at or above one level from all tags."""

    def __init__(self, minimum_level):
        super().__init__()
        self.minimum_level = minimum_level

    def filter(self, record):
        super().filter(record)
        return record.levelno >= self.minimum_level


def apply_log_level(log_level):
    """Applies a logging level to the root logger and existing handlers."""
    normalized = str(log_level or "INFO").strip().upper()
    numeric_log_level = LOG_LEVEL_MAP.get(normalized, logging.INFO)
    root_logger = logging.getLogger("")
    root_logger.setLevel(numeric_log_level)
    for handler in root_logger.handlers:
        handler.setLevel(numeric_log_level)
    return normalized if normalized in LOG_LEVEL_MAP else "INFO"


def _get_request_log_context():
    try:
        from flask import has_request_context, request
    except ImportError:
        return None
    if not has_request_context():
        return None
    body = request.get_json(silent=True)
    if body is None:
        body = request.get_data(as_text=True) if request.get_data() else None
    return {
        "method": request.method,
        "path": request.path,
        "query": request.args.to_dict(flat=False),
        "body": body,
    }


def _response_to_log_payload(result):
    status = getattr(result, "status_code", None)
    resp_obj = result
    if isinstance(result, tuple) and result and hasattr(result[0], "status_code"):
        resp_obj = result[0]
        status = result[1] if len(result) > 1 else getattr(resp_obj, "status_code", None)
    if not hasattr(resp_obj, "status_code"):
        return None

    body = resp_obj.get_data(as_text=True) if hasattr(resp_obj, "get_data") else str(resp_obj)
    try:
        body = json.loads(body)
    except Exception:
        pass
    return {
        "status": status,
        "headers": dict(getattr(resp_obj, "headers", {})),
        "body": _summarize_response_body(body),
    }


def _summarize_response_body(body):
    if isinstance(body, dict):
        summary = {}
        for key, value in body.items():
            if str(key).lower() in VERBOSE_PAYLOAD_KEYS:
                summary[key] = "<omitted>"
            elif isinstance(value, list):
                summary[key] = f"<list length={len(value)}>"
            elif isinstance(value, dict):
                summary[key] = f"<dict keys={len(value)}>"
            else:
                summary[key] = value
        return summary
    if isinstance(body, list):
        return f"<list length={len(body)}>"
    if body:
        return _truncate_log_value(body, max_length=500)
    return body

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
        request_context = _get_request_log_context()
        log_extra = {"log_tag": tag_for_logger_name(func.__module__)}
        is_route_handler = bool(request_context and func.__module__.startswith("backend.routes."))

        if is_route_handler:
            logging.info(
                "%s %s",
                request_context["method"],
                request_context["path"],
                extra=log_extra,
            )
            logging.debug(
                "API request %s",
                format_debug_payload(request_context),
                extra=log_extra,
            )

        # Log function entry with arguments
        # Exclude 'self' from args to avoid redundant logging
        args_repr = [
            "<arg>" for a in args
            if not (hasattr(a, "__class__")
                    and a.__class__.__name__ == func.__qualname__.split(".")[0])
        ]
        kwargs_repr = [f"{k}=<omitted>" for k in kwargs]
        signature = ", ".join(args_repr + kwargs_repr)

        # Check if the function is a method of a class
        if "." in func.__qualname__:
            class_name, method_name = func.__qualname__.rsplit(".", 1)
            log_message = f"Calling {class_name}.{method_name}({signature})"
        else:
            log_message = f"Calling {func.__name__}({signature})"
        logging.debug(log_message, extra=log_extra)

        # Execute the function
        try:
            result = func(*args, **kwargs)

            response_payload = _response_to_log_payload(result)
            if response_payload and is_route_handler:
                logging.debug(
                    "API response %s",
                    format_debug_payload(response_payload),
                    extra=log_extra,
                )
            else:
                # Normal function
                logging.debug(f"{func.__qualname__} returned", extra=log_extra)

            return result

        except Exception as e:
            logging.error(
                f"Exception in {func.__qualname__}: {e}",
                exc_info=True,
                extra=log_extra,
            )
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


def _configure_handler(handler, numeric_log_level):
    handler.setLevel(numeric_log_level)
    handler.addFilter(LogTagFilter())
    handler.setFormatter(TaggedFormatter())
    return handler


def _build_tagged_handler(log_dir, log_prefix, date_str, max_bytes, numeric_log_level, record_filter):
    handler = TimestampedRotatingFileHandler(
        filename=os.path.join(log_dir, f"{log_prefix}_{date_str}.log"),
        maxBytes=max_bytes,
        backupCount=0,
    )
    handler.setLevel(numeric_log_level)
    handler.addFilter(record_filter)
    handler.setFormatter(TaggedFormatter())
    return handler


def _configure_root_logger(handlers, numeric_log_level):
    root_logger = logging.getLogger("")
    root_logger.setLevel(numeric_log_level)
    root_logger.addFilter(LogTagFilter())
    for handler in handlers:
        root_logger.addHandler(handler)

    for logger_name, _tag in TAG_LOGGER_MAP:
        logging.getLogger(logger_name).addFilter(LogTagFilter())
    logging.getLogger("werkzeug").setLevel(logging.WARNING)


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

        # Set up the main custom rotating file handler
        handler = TimestampedRotatingFileHandler(
            filename=log_file,
            maxBytes=max_bytes,
            backupCount=0  # No numbered backups, as we're using timestamps
        )
        _configure_handler(handler, numeric_log_level)
        handlers = [
            handler,
            _build_tagged_handler(log_dir, "LLM", date_str, max_bytes, numeric_log_level, TagOnlyFilter({"LLM"})),
            _build_tagged_handler(log_dir, "Enrichment", date_str, max_bytes, numeric_log_level, TagOnlyFilter({"enrichment"})),
            _build_tagged_handler(log_dir, "Errors", date_str, max_bytes, logging.WARNING, MinimumLevelFilter(logging.WARNING)),
        ]

        # Configure the root logger
        _configure_root_logger(handlers, numeric_log_level)

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
        _configure_handler(handler, numeric_log_level)
        fallback_dir = os.getcwd()
        handlers = [
            handler,
            _build_tagged_handler(fallback_dir, "LLM", date_str, max_bytes, numeric_log_level, TagOnlyFilter({"LLM"})),
            _build_tagged_handler(fallback_dir, "Enrichment", date_str, max_bytes, numeric_log_level, TagOnlyFilter({"enrichment"})),
            _build_tagged_handler(fallback_dir, "Errors", date_str, max_bytes, logging.WARNING, MinimumLevelFilter(logging.WARNING)),
        ]

        _configure_root_logger(handlers, numeric_log_level)

        # Set log levels for specific libraries in fallback mode
        for lib, level_str in Config.LIBRARY_LOG_LEVELS.items():
            lib_level = LOG_LEVEL_MAP.get(level_str.upper(), logging.WARNING)
            logging.getLogger(lib).setLevel(lib_level)

        logging.error(f"Failed to save log to {log_file}: {e}")
        logging.info(f"Fallback logging initialized to {fallback_log_file} with level {log_level}")
        print(f"Error: Could not save log to {log_file}. Using {fallback_log_file} instead.")
