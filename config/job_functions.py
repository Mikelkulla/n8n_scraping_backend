import os
import json
import logging
from backend.config import Config
from backend.database import insert_job_execution

from backend.database import insert_job_execution, update_job_execution, get_job_execution

def write_progress(job_id, step_id, input, max_pages, use_tor, headless, status=None, stop_call=False, current_row=None, total_rows=None):
    """
    Write processing progress to the SQLite database for a specific step and job.

    Args:
        job_id (str): Unique identifier for the job (e.g., UUID).
        step_id (str): Identifier for the processing step (e.g., 'email_scrape').
        input (str): The base URL being scraped.
        max_pages (int): Maximum number of pages to scrape.
        use_tor (bool): Whether to use Tor for scraping.
        headless (bool): Whether to run WebDriver in headless mode.
        status (str, optional): Explicit status to set (e.g., 'running', 'completed').
        stop_call (bool): Whether this is a stop signal.
        current_row (int): Current row or page being processed (1-based index).
        total_rows (int): Total number of rows or pages to process.

    Returns:
        None
    """
    if status is None:
        status = 'stopped' if stop_call else ("completed" if current_row >= total_rows else "running")
    
    try:
        # Check if a record exists for this job_id and step_id
        if get_job_execution(job_id, step_id):
            # Update only specific fields
            update_job_execution(job_id, step_id, current_row=current_row, total_rows=total_rows, status=status, stop_call=stop_call)
        else:
            # Insert a new record with all fields
            insert_job_execution(job_id, step_id, input, max_pages, use_tor, headless, status, stop_call, None, current_row, total_rows)
        
        update_job_status(step_id, job_id, status)
        logging.info(f"Progress updated for job {job_id} ({step_id}): input {input}, row {current_row}/{total_rows}, status: {status}")
    except Exception as e:
        logging.error(f"Failed to write progress for job {job_id} ({step_id}): {e}")


def update_job_status(step_id, job_id, status):
    """
    Updates the status of a job in the jobs_{step_id}.json file.
    
    Parameters:
        step_id (int): Step number (5, 6, or 7).
        job_id (str): UUID of the job.
        status (str): New status ('running', 'completed', or 'stopped').
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
    """
    Check if a stop signal file exists for the specified step.

    Parameters:
        step_id (str): Identifier for the processing step (e.g., 'step7', 'step8').

    Returns:
        bool: True if stop signal file exists, False otherwise.
    """
    stop_file = os.path.join(Config.TEMP_PATH, f"stop_{step_id}.txt")
    return os.path.exists(stop_file)