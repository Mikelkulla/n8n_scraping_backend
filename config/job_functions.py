import logging
from backend.database import Database

# Modifying the job processes in the Database. (New Logic)
def write_progress(job_id, step_id, input, max_pages=None, use_tor=None, headless=None, status=None, stop_call=None, current_row=None, total_rows=None, error_message=None, db_connection=None):
    """Writes or updates the progress of a scraping job in the database.

    This function records the state of a job, including its status (e.g., "running",
    "completed"), progress counters, and any errors. It can handle both new and
    existing job entries.

    Args:
        job_id (str): The unique identifier for the job.
        step_id (str): The identifier for the specific task or step (e.g.,
            'email_scrape').
        input (str): The primary input for the job, such as a URL or search query.
        max_pages (int, optional): The maximum number of pages to be scraped.
            Defaults to None.
        use_tor (bool, optional): Flag indicating if the Tor network was used.
            Defaults to None.
        headless (bool, optional): Flag indicating if the browser ran in headless
            mode. Defaults to None.
        status (str, optional): The current status of the job. If None, it's
            auto-determined based on other arguments. Defaults to None.
        stop_call (bool, optional): Flag indicating if a stop signal has been
            issued for the job. Defaults to None so progress updates do not
            clear an existing stop request.
        current_row (int, optional): The number of items processed so far.
            Defaults to None.
        total_rows (int, optional): The total number of items to process.
            Defaults to None.
        error_message (str, optional): A message describing an error if the job
            failed. Defaults to None.
        db_connection (Database, optional): An existing database connection to
            use. If None, a new connection is created. Defaults to None.
    """
    if status is None:
        status = 'stopped' if stop_call is True else ("completed" if current_row is not None and total_rows is not None and current_row >= total_rows else "running")
    
    def _write_to_db(db):
        # Check if a record exists for this job_id and step_id
        if db.get_job_execution(job_id, step_id):
            # Update only specific fields
            db.update_job_execution(job_id, step_id, current_row=current_row, total_rows=total_rows, status=status, stop_call=stop_call, error_message=error_message)
        else:
            # Insert a new record with all fields
            db.insert_job_execution(job_id, step_id, input, max_pages, use_tor, headless, status, bool(stop_call), error_message, current_row, total_rows)
    try:
        if db_connection:
            _write_to_db(db_connection)
        else:
            with Database() as db:
                _write_to_db(db)
        logging.info(f"Progress updated for job {job_id} ({step_id}): input {input}, row {current_row}/{total_rows}, status: {status}")
    except Exception as e:
        logging.error(f"Failed to write progress for job {job_id} ({step_id}): {e}")

def check_stop_signal(job_id, step_id, db_connection=None):
    """Checks whether a specific job has received a stop signal.

    The scraping process can be interrupted gracefully by setting the
    job_executions.stop_call flag for the exact job_id and step_id pair.

    Args:
        job_id (str): The unique identifier for the job.
        step_id (str): The identifier for the processing step (e.g.,
            'email_scrape').
        db_connection (Database, optional): An existing database connection to
            use. If None, a new connection is created.

    Returns:
        bool: True if the job has been asked to stop, False otherwise.
    """
    def _check_db(db):
        progress = db.get_job_execution(job_id, step_id)
        return bool(progress and progress.get("stop_call"))

    try:
        if db_connection:
            return _check_db(db_connection)
        with Database() as db:
            return _check_db(db)
    except Exception as e:
        logging.error(f"Failed to check stop signal for job {job_id} ({step_id}): {e}")
        return False
