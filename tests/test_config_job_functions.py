from unittest.mock import patch, MagicMock

from config.job_functions import write_progress, check_stop_signal

class TestJobFunctions:
    @patch('config.job_functions.Database')
    def test_write_progress_insert_new_job(self, mock_db_class):
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
    def test_write_progress_update_existing_job(self, mock_db_class):
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
            "job1", "step1", current_row=50, total_rows=100, status="running", stop_call=None, error_message=None
        )
        mock_db_instance.insert_job_execution.assert_not_called()

    @patch('config.job_functions.Database')
    def test_write_progress_status_completed(self, mock_db_class):
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
            "job1", "step1", current_row=100, total_rows=100, status="completed", stop_call=None, error_message=None
        )

    @patch('config.job_functions.Database')
    def test_write_progress_status_stopped(self, mock_db_class):
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

    def test_write_progress_with_db_connection(self):
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
    def test_write_progress_exception(self, mock_logging, mock_db_class):
        """Test exception handling during database operation."""
        mock_db_instance = MagicMock()
        mock_db_instance.get_job_execution.side_effect = Exception("DB error")
        mock_db_class.return_value.__enter__.return_value = mock_db_instance

        write_progress(job_id="job1", step_id="step1", input="test")

        mock_logging.error.assert_called_with("Failed to write progress for job job1 (step1): DB error")

    @patch('builtins.open')
    @patch('config.job_functions.Database')
    def test_write_progress_does_not_create_json_progress_file(self, mock_db_class, mock_open):
        """Test that progress writes only use the database, not jobs_*.json files."""
        mock_db_instance = MagicMock()
        mock_db_instance.get_job_execution.return_value = None
        mock_db_class.return_value.__enter__.return_value = mock_db_instance

        write_progress(
            job_id="job1",
            step_id="step1",
            input="test_input",
            status="running",
        )

        mock_open.assert_not_called()

    @patch('config.job_functions.Database')
    def test_check_stop_signal_true_for_matching_job(self, mock_db_class):
        """Test that check_stop_signal reads the job-scoped DB stop flag."""
        mock_db_instance = MagicMock()
        mock_db_instance.get_job_execution.return_value = {
            "job_id": "job1",
            "step_id": "step1",
            "stop_call": True,
        }
        mock_db_class.return_value.__enter__.return_value = mock_db_instance

        assert check_stop_signal("job1", "step1") is True
        mock_db_instance.get_job_execution.assert_called_once_with("job1", "step1")

    @patch('config.job_functions.Database')
    def test_check_stop_signal_false_for_other_job(self, mock_db_class):
        """Test that another job with the same step does not stop this job."""
        mock_db_instance = MagicMock()
        mock_db_instance.get_job_execution.return_value = {
            "job_id": "job1",
            "step_id": "step1",
            "stop_call": False,
        }
        mock_db_class.return_value.__enter__.return_value = mock_db_instance

        assert check_stop_signal("job1", "step1") is False
        mock_db_instance.get_job_execution.assert_called_once_with("job1", "step1")

    def test_check_stop_signal_with_db_connection(self):
        """Test that an existing DB connection can be reused."""
        mock_db_connection = MagicMock()
        mock_db_connection.get_job_execution.return_value = {"stop_call": 1}

        assert check_stop_signal("job1", "step1", db_connection=mock_db_connection) is True
        mock_db_connection.get_job_execution.assert_called_once_with("job1", "step1")
