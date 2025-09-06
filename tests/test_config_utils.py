import sys
import os
import pytest
import pandas as pd
from unittest.mock import patch, mock_open, MagicMock
import json

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import requests
from unittest.mock import MagicMock

from config.utils import (
    load_csv,
    is_non_business_domain,
    extract_base_url,
    validate_url,
    is_example_domain,
    validate_emails,
    poll_job_progress,
    read_job_results,
)

@pytest.mark.parametrize("domain, expected", [
    ("facebook.com", True),
    ("sub.facebook.com", True),
    ("twitter.com", True),
    ("x.com", True),
    ("google.com", False),
    ("mybusiness.com", False),
    ("airbnb.co.uk", True),
    ("example.com", False),
    ("linkedin.com", True),
    ("instagram.com", True),
    ("youtube.com", True),
    ("pinterest.com", True),
    ("snapchat.com", True),
    ("tiktok.com", True),
])
def test_is_non_business_domain(domain, expected):
    assert is_non_business_domain(domain) == expected

@pytest.mark.parametrize("url, expected", [
    ("http://example.com/path", "http://example.com"),
    ("https://www.example.com/path?query=1", "https://www.example.com"),
    ("example.com", "https://example.com"),
    ("www.example.com", "https://www.example.com"),
    ("facebook.com", None),
    ("https://twitter.com/user", None),
    ("http://127.0.0.1", "http://127.0.0.1"),
    ("invalid-url", "https://invalid-url"),
])
def test_extract_base_url(url, expected):
    assert extract_base_url(url) == expected

@pytest.mark.parametrize("url, expected_base_url, expected_error", [
    ("https://www.example.com", "https://www.example.com", None),
    ("http://example.com/path", "http://example.com", None),
    ("example.com", "https://example.com", None),
    ("facebook.com", None, "Non-business domain"),
    ("https://twitter.com/user", None, "Non-business domain"),
    ("invalid-url", None, "Invalid URL format"),
    ("http://", None, "Invalid URL format"),
    ("http://invalid_", None, "Invalid URL format"),
    ("http://.com", None, "Invalid URL format"),
])
def test_validate_url(url, expected_base_url, expected_error):
    base_url, error = validate_url(url)
    assert base_url == expected_base_url
    assert error == expected_error

def test_validate_url_invalid_with_scheme():
    base_url, error = validate_url("http://invalid_")
    assert base_url is None
    assert error == "Invalid URL format"

@pytest.mark.parametrize("email, expected", [
    ("test@example.com", True),
    ("test@example.org", True),
    ("test@example.net", True),
    ("test@test.com", True),
    ("test@sample.com", True),
    ("test@business.com", False),
    ("test@sub.example.com", True),
])
def test_is_example_domain(email, expected):
    assert is_example_domain(email) == expected

@pytest.mark.parametrize("emails, expected", [
    (
        ["test@example.com", "valid@business.com", "invalid-email", "test@test.com"],
        ["valid@business.com"]
    ),
    (
        ["one@business.com", "two@business.com"],
        ["one@business.com", "two@business.com"]
    ),
    (
        ["invalid", "test@example.org"],
        []
    ),
    (
        [],
        []
    )
])
def test_validate_emails(emails, expected):
    assert validate_emails(emails) == expected

def test_load_csv_uses_output_if_exists(tmp_path):
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    output_csv = output_dir / "output.csv"
    input_csv = tmp_path / "input.csv"

    df_output = pd.DataFrame({"col1": ["d", "e"], "col2": ["f", "g"]})
    df_output.to_csv(output_csv, index=False)

    df, resolved_path = load_csv(str(input_csv), str(output_csv))

    assert resolved_path == str(output_csv)
    pd.testing.assert_frame_equal(df, df_output)

def test_load_csv_uses_input_if_output_does_not_exist(tmp_path):
    input_csv = tmp_path / "input.csv"
    output_csv = tmp_path / "output" / "output.csv"

    df_input = pd.DataFrame({"col1": ["a", "b"], "col2": ["c", "d"]})
    df_input.to_csv(input_csv, index=False)

    df, resolved_path = load_csv(str(input_csv), str(output_csv))

    assert resolved_path == str(input_csv)
    pd.testing.assert_frame_equal(df, df_input)

def test_load_csv_file_not_found(tmp_path):
    input_csv = tmp_path / "non_existent_input.csv"
    output_csv = tmp_path / "output" / "output.csv"

    df, resolved_path = load_csv(str(input_csv), str(output_csv))

    assert df is None
    assert resolved_path is None

def test_load_csv_missing_required_column(tmp_path):
    input_csv = tmp_path / "input.csv"
    output_csv = tmp_path / "output" / "output.csv"

    df_input = pd.DataFrame({"col1": ["a", "b"]})
    df_input.to_csv(input_csv, index=False)

    df, resolved_path = load_csv(str(input_csv), str(output_csv), required_columns=["col1", "col2"])

    assert df is None
    assert resolved_path is None

def test_load_csv_generic_exception(tmp_path):
    input_csv = tmp_path / "input.csv"
    output_csv = tmp_path / "output" / "output.csv"

    with open(input_csv, "w") as f:
        f.write("col1,col2\na,b")

    with patch('pandas.read_csv', side_effect=Exception("mocked error")):
        df, resolved_path = load_csv(str(input_csv), str(output_csv))
        assert df is None
        assert resolved_path is None

@patch('config.utils.time.sleep', return_value=None)
@patch('requests.get')
def test_poll_job_progress_completed(mock_get, mock_sleep):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"status": "completed", "progress": 100}
    mock_get.return_value = mock_response

    result = poll_job_progress("http://fake-url.com", "job-123")

    assert result["status"] == "completed"
    assert result["progress"]["status"] == "completed"
    mock_get.assert_called_once_with("http://fake-url.com/progress/job-123")

@patch('config.utils.time.sleep', return_value=None)
@patch('requests.get')
def test_poll_job_progress_failed(mock_get, mock_sleep):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"status": "failed", "error_message": "Job failed"}
    mock_get.return_value = mock_response

    result = poll_job_progress("http://fake-url.com", "job-123")

    assert result["status"] == "failed"
    assert result["error"] == "Job failed"

@patch('config.utils.time.sleep', return_value=None)
@patch('requests.get')
def test_poll_job_progress_stopped(mock_get, mock_sleep):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"status": "stopped"}
    mock_get.return_value = mock_response

    result = poll_job_progress("http://fake-url.com", "job-123")

    assert result["status"] == "stopped"

@patch('config.utils.time.sleep', return_value=None)
@patch('requests.get')
def test_poll_job_progress_completes_after_retries(mock_get, mock_sleep):
    mock_running_response = MagicMock()
    mock_running_response.status_code = 200
    mock_running_response.json.return_value = {"status": "running"}

    mock_completed_response = MagicMock()
    mock_completed_response.status_code = 200
    mock_completed_response.json.return_value = {"status": "completed"}

    mock_get.side_effect = [mock_running_response, mock_running_response, mock_completed_response]

    result = poll_job_progress("http://fake-url.com", "job-123")

    assert result["status"] == "completed"
    assert mock_get.call_count == 3

@patch('config.utils.time.sleep', return_value=None)
@patch('requests.get')
def test_poll_job_progress_recovers_from_exception(mock_get, mock_sleep):
    mock_success_response = MagicMock()
    mock_success_response.status_code = 200
    mock_success_response.json.return_value = {"status": "completed"}

    mock_get.side_effect = [requests.RequestException("mocked error"), mock_success_response]

    result = poll_job_progress("http://fake-url.com", "job-123", max_retries=3)

    assert result["status"] == "completed"
    assert mock_get.call_count == 2

@patch('config.utils.time.sleep', return_value=None)
@patch('requests.get')
def test_poll_job_progress_recovers_from_non_200(mock_get, mock_sleep):
    mock_fail_response = MagicMock()
    mock_fail_response.status_code = 500
    mock_fail_response.json.return_value = {"error": "server error"}

    mock_success_response = MagicMock()
    mock_success_response.status_code = 200
    mock_success_response.json.return_value = {"status": "completed"}
    
    mock_get.side_effect = [mock_fail_response, mock_success_response]

    result = poll_job_progress("http://fake-url.com", "job-123", max_retries=3)

    assert result["status"] == "completed"
    assert mock_get.call_count == 2

@patch('config.utils.time.sleep', return_value=None)
@patch('builtins.open', new_callable=mock_open, read_data='[{"job_id": "job-123", "emails": ["test1@example.com", "test2@example.com"]}]')
@patch('json.load')
def test_read_job_results_success(mock_json_load, mock_file, mock_sleep):
    mock_json_load.return_value = [{"job_id": "job-123", "emails": ["test1@example.com", "test2@example.com"]}]
    result = read_job_results("fake_file.json", "job-123")

    assert result["emails"] == ["test1@example.com", "test2@example.com"]
    assert result["error"] is None
    mock_file.assert_called_once_with("fake_file.json", "r")

@patch('config.utils.time.sleep', return_value=None)
@patch('builtins.open', new_callable=mock_open, read_data='[{"job_id": "job-456", "emails": []}]')
@patch('json.load')
def test_read_job_results_job_id_not_found(mock_json_load, mock_file, mock_sleep):
    mock_json_load.return_value = [{"job_id": "job-456", "emails": []}]
    result = read_job_results("fake_file.json", "job-123", max_retries=1)
    
    assert result["emails"] == []
    assert "Failed to read results file" in result["error"]

@patch('config.utils.time.sleep', return_value=None)
@patch('builtins.open', side_effect=FileNotFoundError)
def test_read_job_results_file_not_found(mock_file, mock_sleep):
    result = read_job_results("fake_file.json", "job-123", max_retries=3)

    assert result["emails"] == []
    assert "Failed to read results file" in result["error"]
    assert mock_file.call_count == 3

@patch('config.utils.time.sleep', return_value=None)
@patch('builtins.open', new_callable=mock_open, read_data='{"invalid-json"}')
@patch('json.load', side_effect=json.JSONDecodeError("mocked error", "doc", 0))
def test_read_job_results_json_decode_error(mock_json_load, mock_file, mock_sleep):
    result = read_job_results("fake_file.json", "job-123", max_retries=3)

    assert result["emails"] == []
    assert "Failed to read results file" in result["error"]
    assert mock_file.call_count == 3

@patch('config.utils.time.sleep', return_value=None)
@patch('builtins.open')
@patch('json.load')
def test_read_job_results_retry_and_succeed(mock_json_load, mock_open_func, mock_sleep):
    mock_open_func.side_effect = [
        FileNotFoundError,
        mock_open(read_data='[{"job_id": "job-123", "emails": ["a@b.com"]}]').return_value
    ]
    mock_json_load.return_value = [{"job_id": "job-123", "emails": ["a@b.com"]}]
    
    result = read_job_results("fake_file.json", "job-123", max_retries=3)

    assert result["emails"] == ["a@b.com"]
    assert result["error"] is None
    assert mock_open_func.call_count == 2

@patch('config.utils.time.sleep', return_value=None)
@patch('builtins.open', new_callable=mock_open, read_data='{"job_id": "job-123", "emails": ["test@example.com"]}')
@patch('json.load')
def test_read_job_results_single_json_object(mock_json_load, mock_file, mock_sleep):
    mock_json_load.return_value = {"job_id": "job-123", "emails": ["test@example.com"]}
    result = read_job_results("fake_file.json", "job-123")

    assert result["emails"] == ["test@example.com"]
    assert result["error"] is None

@patch('config.utils.time.sleep', return_value=None)
@patch('requests.get')
def test_poll_job_progress_fails_after_non_200_retries(mock_get, mock_sleep):
    mock_fail_response = MagicMock()
    mock_fail_response.status_code = 500
    mock_fail_response.json.return_value = {"error": "server error"}
    mock_get.return_value = mock_fail_response

    result = poll_job_progress("http://fake-url.com", "job-123", max_retries=3)

    assert result["status"] == "failed"
    assert "Progress check failed" in result["error"]
    assert mock_get.call_count == 3

@patch('config.utils.time.sleep', return_value=None)
@patch('requests.get', side_effect=requests.RequestException("mocked error"))
def test_poll_job_progress_fails_after_exception_retries(mock_get, mock_sleep):
    result = poll_job_progress("http://fake-url.com", "job-123", max_retries=3)

    assert result["status"] == "failed"
    assert "Progress check failed" in result["error"]
    assert mock_get.call_count == 3
