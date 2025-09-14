import os
import json
import pytest
from unittest.mock import patch, MagicMock

from config.job_functions import write_progress, update_job_status, check_stop_signal
from backend.config import Config

@pytest.fixture
def temp_dir(tmp_path):
    """Create a temporary directory for tests."""
    # Mock Config.TEMP_PATH to use the temporary directory
    with patch('config.job_functions.Config.TEMP_PATH', str(tmp_path)):
        yield str(tmp_path)

class TestJobFunctions:
    @patch('config.job_functions.Database')
    def test_write_progress_insert_new_job(self, mock_db_class, temp_dir):
        """Test that a new job is inserted when no record exists."""
        mock_db_instance = MagicMock()
        mock_db_instance.get_job_execution.return_value = None
        mock_db_class.return_value.__enter__.return_value = mock_db_instance

        write_progress(
            job_id="job1",
            step_id="step1",
            input="test_input",
            max_pages=10,
            use_tor=True,
            headless=False,
            current_row=5,
            total_rows=100
        )

        mock_db_instance.get_job_execution.assert_called_once_with("job1", "step1")
        mock_db_instance.insert_job_execution.assert_called_once_with(
            "job1", "step1", "test_input", 10, True, False, "running", False, None, 5, 100
        )
        mock_db_instance.update_job_execution.assert_not_called()

    @patch('config.job_functions.Database')
    def test_write_progress_update_existing_job(self, mock_db_class, temp_dir):
        """Test that an existing job is updated."""
        mock_db_instance = MagicMock()
        mock_db_instance.get_job_execution.return_value = {"job_id": "job1", "step_id": "step1"}
        mock_db_class.return_value.__enter__.return_value = mock_db_instance

        write_progress(
            job_id="job1",
            step_id="step1",
            input="test_input",
            current_row=50,
            total_rows=100,
            status="running"
        )

        mock_db_instance.get_job_execution.assert_called_once_with("job1", "step1")
        mock_db_instance.update_job_execution.assert_called_once_with(
            "job1", "step1", current_row=50, total_rows=100, status="running", stop_call=False, error_message=None
        )
        mock_db_instance.insert_job_execution.assert_not_called()

    @patch('config.job_functions.Database')
    def test_write_progress_status_completed(self, mock_db_class, temp_dir):
        """Test that status is 'completed' when current_row >= total_rows."""
        mock_db_instance = MagicMock()
        mock_db_instance.get_job_execution.return_value = {"job_id": "job1", "step_id": "step1"}
        mock_db_class.return_value.__enter__.return_value = mock_db_instance

        write_progress(
            job_id="job1",
            step_id="step1",
            input="test_input",
            current_row=100,
            total_rows=100
        )

        mock_db_instance.update_job_execution.assert_called_once_with(
            "job1", "step1", current_row=100, total_rows=100, status="completed", stop_call=False, error_message=None
        )

    @patch('config.job_functions.Database')
    def test_write_progress_status_stopped(self, mock_db_class, temp_dir):
        """Test that status is 'stopped' when stop_call is True."""
        mock_db_instance = MagicMock()
        mock_db_instance.get_job_execution.return_value = {"job_id": "job1", "step_id": "step1"}
        mock_db_class.return_value.__enter__.return_value = mock_db_instance

        write_progress(
            job_id="job1",
            step_id="step1",
            input="test_input",
            stop_call=True
        )

        mock_db_instance.update_job_execution.assert_called_once_with(
            "job1", "step1", current_row=None, total_rows=None, status="stopped", stop_call=True, error_message=None
        )

    def test_write_progress_with_db_connection(self, temp_dir):
        """Test that an existing db_connection is used."""
        mock_db_connection = MagicMock()
        mock_db_connection.get_job_execution.return_value = None

        write_progress(
            job_id="job1",
            step_id="step1",
            input="test_input",
            db_connection=mock_db_connection
        )

        mock_db_connection.get_job_execution.assert_called_once_with("job1", "step1")
        mock_db_connection.insert_job_execution.assert_called_once()

    @patch('config.job_functions.Database')
    @patch('config.job_functions.logging')
    def test_write_progress_exception(self, mock_logging, mock_db_class, temp_dir):
        """Test exception handling during database operation."""
        mock_db_instance = MagicMock()
        mock_db_instance.get_job_execution.side_effect = Exception("DB error")
        mock_db_class.return_value.__enter__.return_value = mock_db_instance

        write_progress(job_id="job1", step_id="step1", input="test")

        mock_logging.error.assert_called_with("Failed to write progress for job job1 (step1): DB error")

    def test_update_job_status_create_new_file(self, temp_dir):
        """Test that a new jobs file is created."""
        jobs_file = os.path.join(temp_dir, "jobs_step1.json")
        update_job_status("step1", "job1", "running")

        assert os.path.exists(jobs_file)
        with open(jobs_file, "r") as f:
            jobs = json.load(f)
        assert jobs == [{"step_id": "step1", "job_id": "job1", "status": "running"}]

    def test_update_job_status_update_existing_job(self, temp_dir):
        """Test that an existing job's status is updated."""
        jobs_file = os.path.join(temp_dir, "jobs_step1.json")
        with open(jobs_file, "w") as f:
            json.dump([{"step_id": "step1", "job_id": "job1", "status": "running"}], f)

        update_job_status("step1", "job1", "completed")

        with open(jobs_file, "r") as f:
            jobs = json.load(f)
        assert jobs == [{"step_id": "step1", "job_id": "job1", "status": "completed"}]

    def test_update_job_status_add_new_job(self, temp_dir):
        """Test that a new job is added to an existing file."""
        jobs_file = os.path.join(temp_dir, "jobs_step1.json")
        with open(jobs_file, "w") as f:
            json.dump([{"step_id": "step1", "job_id": "job1", "status": "running"}], f)

        update_job_status("step1", "job2", "running")

        with open(jobs_file, "r") as f:
            jobs = json.load(f)
        assert len(jobs) == 2
        assert {"step_id": "step1", "job_id": "job2", "status": "running"} in jobs

    @patch('builtins.open', side_effect=Exception('File error'))
    @patch('builtins.print')
    def test_update_job_status_exception(self, mock_print, mock_open, temp_dir):
        """Test exception handling during file operation."""
        update_job_status("step1", "job1", "running")
        mock_print.assert_called_with("Error updating job status for step step1, job job1: File error")

    def test_check_stop_signal_file_exists(self, temp_dir):
        """Test that check_stop_signal returns True if the stop file exists."""
        stop_file = os.path.join(temp_dir, "stop_step1.txt")
        with open(stop_file, "w") as f:
            f.write("stop")

        assert check_stop_signal("step1") is True

    def test_check_stop_signal_file_not_exists(self, temp_dir):
        """Test that check_stop_signal returns False if the stop file does not exist."""
        assert check_stop_signal("step1") is False
