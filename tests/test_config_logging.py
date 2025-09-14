import sys
import os
import pytest
import logging
from datetime import datetime
from unittest.mock import patch, MagicMock

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from config.logging import setup_logging, TimestampedRotatingFileHandler
from backend.config import Config


@pytest.fixture(autouse=True)
def reset_logging():
    """Reset logging state before and after each test."""
    yield
    logging.shutdown()
    root_logger = logging.getLogger('')
    root_logger.handlers = []
    # Clear logger cache to prevent state from leaking between tests
    for name in list(logging.Logger.manager.loggerDict):
        del logging.Logger.manager.loggerDict[name]

@patch('config.logging.Config')
def test_setup_logging_basic_configuration(mock_config, tmp_path):
    """Test basic logging setup and configuration."""
    # Arrange
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    
    mock_config.LOG_PATH = str(log_dir)
    mock_config.LOG_PREFIX = "test_log"
    mock_config.MAX_BYTES = 1024
    mock_config.LOG_LEVEL = "DEBUG"
    mock_config.LIBRARY_LOG_LEVELS = {}

    # Act
    setup_logging(
        log_dir=mock_config.LOG_PATH,
        log_prefix=mock_config.LOG_PREFIX,
        max_bytes=mock_config.MAX_BYTES,
        log_level=mock_config.LOG_LEVEL
    )

    # Assert
    date_str = datetime.now().strftime("%d_%m_%Y")
    expected_log_file = log_dir / f"test_log_{date_str}.log"
    
    assert expected_log_file.exists()
    
    root_logger = logging.getLogger('')
    assert root_logger.level == logging.DEBUG
    
    # Check that our handler was added, ignoring pytest's own handlers
    handler = next((h for h in reversed(root_logger.handlers) if isinstance(h, TimestampedRotatingFileHandler)), None)
    assert handler is not None
    assert handler.baseFilename == str(expected_log_file)
    assert handler.maxBytes == mock_config.MAX_BYTES


@patch('os.makedirs')
@patch('config.logging.Config')
def test_setup_logging_fallback_mechanism(mock_makedirs, mock_config, tmp_path, caplog):
    """Test the fallback logging mechanism when the primary directory fails."""
    # Arrange
    mock_makedirs.side_effect = PermissionError("Permission denied")
    
    log_dir = tmp_path / "unwritable_logs"
    
    mock_config.LOG_PATH = str(log_dir)
    mock_config.LOG_PREFIX = "fallback_log"
    # Set max_bytes to a large value to avoid rollover in this test
    mock_config.MAX_BYTES = 1024 * 1024
    mock_config.LOG_LEVEL = "INFO"
    mock_config.LIBRARY_LOG_LEVELS = {}

    # Act
    original_cwd = os.getcwd()
    os.chdir(str(tmp_path))
    try:
        setup_logging(
            log_dir=mock_config.LOG_PATH,
            log_prefix=mock_config.LOG_PREFIX,
            max_bytes=mock_config.MAX_BYTES,
            log_level=mock_config.LOG_LEVEL
        )
    finally:
        os.chdir(original_cwd)

    # Assert
    date_str = datetime.now().strftime("%d_%m_%Y")
    fallback_log_file = tmp_path / f"fallback_log_{date_str}.log"
    
    assert fallback_log_file.exists()
    
    root_logger = logging.getLogger('')
    assert root_logger.level == logging.INFO
    
    handler = next((h for h in reversed(root_logger.handlers) if isinstance(h, TimestampedRotatingFileHandler)), None)
    assert handler is not None
    # The handler's baseFilename is an absolute path.
    assert handler.baseFilename == str(fallback_log_file)
    
    assert "Failed to save log" in caplog.text
    assert "Fallback logging initialized" in caplog.text


@patch('config.logging.Config')
def test_timestamped_rotating_file_handler_rotation(mock_config, tmp_path):
    """Test that the TimestampedRotatingFileHandler rotates logs correctly."""
    # Arrange
    log_dir = tmp_path / "logs"
    log_dir.mkdir()

    mock_config.LOG_PATH = str(log_dir)
    mock_config.LOG_PREFIX = "rotation_test"
    mock_config.MAX_BYTES = 200  # Small size to trigger rotation
    mock_config.LOG_LEVEL = "INFO"
    mock_config.LIBRARY_LOG_LEVELS = {}

    # Mock datetime to control filenames
    with patch('config.logging.datetime') as mock_datetime:
        mock_datetime.now.return_value = datetime(2023, 1, 1, 12, 0, 0)
        
        setup_logging(
            log_dir=mock_config.LOG_PATH,
            log_prefix=mock_config.LOG_PREFIX,
            max_bytes=mock_config.MAX_BYTES,
            log_level=mock_config.LOG_LEVEL
        )

        # Act
        # Log messages to exceed maxBytes
        for i in range(10):
            logging.info("This is a test log message to force rotation.")
        
        # Change the time for the rotated file's timestamp
        mock_datetime.now.return_value = datetime(2023, 1, 1, 12, 5, 0)
        
        # Trigger rotation by logging one more message
        logging.info("This message should trigger the rotation.")

    # Assert
    date_str = "01_01_2023"
    original_log_file = log_dir / f"rotation_test_{date_str}.log"
    rotated_log_file = log_dir / f"rotation_test_{date_str}_12_00_00.log"
    
    # After rotation, the original file should be the new log, and the rotated file should exist
    assert original_log_file.exists()
    assert rotated_log_file.exists()
    assert original_log_file.stat().st_size < mock_config.MAX_BYTES


def test_do_rollover_method(tmp_path):
    """Test the doRollover method directly."""
    # Arrange
    log_file = tmp_path / "rollover.log"
    log_file.write_text("some initial log data")
    
    handler = TimestampedRotatingFileHandler(log_file, maxBytes=10, backupCount=1)
    handler.stream = open(log_file, 'a') # Manually set the stream for the test
    
    # Mock datetime to control the timestamp in the rotated filename
    with patch('config.logging.datetime') as mock_datetime:
        mock_datetime.now.return_value = datetime(2023, 1, 1, 10, 30, 0)
        
        # Act
        handler.doRollover()

    # Assert
    rotated_file = tmp_path / "rollover_10_30_00.log"
    assert rotated_file.exists()
    assert log_file.exists()
    assert log_file.stat().st_size == 0
    assert handler.stream is not None # stream is reopened


@patch('config.logging.Config')
def test_setup_logging_library_levels(mock_config, tmp_path):
    """Test that log levels for specific libraries are set correctly."""
    # Arrange
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    
    mock_config.LOG_PATH = str(log_dir)
    mock_config.LOG_PREFIX = "lib_test"
    mock_config.MAX_BYTES = 1024
    mock_config.LOG_LEVEL = "INFO"
    mock_config.LIBRARY_LOG_LEVELS = {
        "test_lib_1": "DEBUG",
        "test_lib_2": "WARNING",
    }

    # Act
    setup_logging(
        log_dir=mock_config.LOG_PATH,
        log_prefix=mock_config.LOG_PREFIX,
        max_bytes=mock_config.MAX_BYTES,
        log_level=mock_config.LOG_LEVEL
    )

    # Assert
    assert logging.getLogger("test_lib_1").level == logging.DEBUG
    assert logging.getLogger("test_lib_2").level == logging.WARNING
    # Check a library not in the config defaults to the root logger level
    assert logging.getLogger("unspecified_lib").level == logging.NOTSET


@patch('config.logging.Config')
def test_setup_logging_invalid_log_level(mock_config, tmp_path):
    """Test that an invalid log level defaults to INFO."""
    # Arrange
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    
    mock_config.LOG_PATH = str(log_dir)
    mock_config.LOG_PREFIX = "invalid_level_test"
    mock_config.MAX_BYTES = 1024
    mock_config.LOG_LEVEL = "INVALID_LEVEL"
    mock_config.LIBRARY_LOG_LEVELS = {}

    # Act
    setup_logging(
        log_dir=mock_config.LOG_PATH,
        log_prefix=mock_config.LOG_PREFIX,
        max_bytes=mock_config.MAX_BYTES,
        log_level=mock_config.LOG_LEVEL
    )

    # Assert
    root_logger = logging.getLogger('')
    assert root_logger.level == logging.INFO
