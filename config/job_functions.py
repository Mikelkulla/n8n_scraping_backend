import os
import json
import logging
import time
from backend.config import Config
from backend.database import Database

# Modifying the job processes in the Database. (New Logic)
def write_progress(job_id, step_id, input, max_pages=None, use_tor=None, headless=None, status=None, stop_call=False, current_row=None, total_rows=None, error_message=None, db_connection=None):
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
            issued for the job. Defaults to False.
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
        status = 'stopped' if stop_call else ("completed" if current_row is not None and total_rows is not None and current_row >= total_rows else "running")
    
    def _write_to_db(db):
        # Check if a record exists for this job_id and step_id
        if db.get_job_execution(job_id, step_id):
            # Update only specific fields
            db.update_job_execution(job_id, step_id, current_row=current_row, total_rows=total_rows, status=status, stop_call=stop_call, error_message=error_message)
        else:
            # Insert a new record with all fields
            db.insert_job_execution(job_id, step_id, input, max_pages, use_tor, headless, status, stop_call, error_message, current_row, total_rows)
    try:
        if db_connection:
            _write_to_db(db_connection)
        else:
            with Database() as db:
                _write_to_db(db)
                
        update_job_status(step_id, job_id, status)
        logging.info(f"Progress updated for job {job_id} ({step_id}): input {input}, row {current_row}/{total_rows}, status: {status}")
    except Exception as e:
        logging.error(f"Failed to write progress for job {job_id} ({step_id}): {e}")

# This function is for JSON files tracking (Old logic to be deprecated)
def update_job_status(step_id, job_id, status):
    """Updates the status of a job in a JSON tracking file.

    Note:
        This function is part of an older system for tracking jobs and is planned
        for deprecation. Job status is primarily managed in the database.

    Args:
        step_id (str): The identifier for the step (e.g., 'email_scrape').
        job_id (str): The unique identifier of the job.
        status (str): The new status to set (e.g., 'running', 'completed',
            'stopped').
    """
    jobs_file = os.path.join(Config.TEMP_PATH, f"jobs_{step_id}.json")
    try:
        os.makedirs(Config.TEMP_PATH, exist_ok=True)
        if os.path.exists(jobs_file):
            with open(jobs_file, "r") as f:
                jobs = json.load(f)
        else:
            jobs = []
        job_updated = False
        for job in jobs:
            if job["job_id"] == job_id:
                job["status"] = status
                job_updated = True
                break
        if not job_updated:
            # Optionally add new job if it doesn't exist
            jobs.append({'step_id': step_id, "job_id": job_id, "status": status})
        # Write back to file
        with open(jobs_file, "w") as f:
            json.dump(jobs, f, indent=2)
    except Exception as e:
        print(f"Error updating job status for step {step_id}, job {job_id}: {e}")

def check_stop_signal(step_id):
    """Checks for the existence of a stop signal file for a given step.

    The scraping process can be interrupted gracefully by placing a specific file
    in the temporary directory. This function checks if that file exists.

    Args:
        step_id (str): The identifier for the processing step (e.g.,
            'email_scrape').

    Returns:
        bool: True if the stop signal file exists, False otherwise.
    """
    stop_file = os.path.join(Config.TEMP_PATH, f"stop_{step_id}.txt")
    return os.path.exists(stop_file)