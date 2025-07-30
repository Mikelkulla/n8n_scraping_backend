from flask import Blueprint, jsonify, request
import os
import json
import threading
import uuid
from backend.config import Config
from backend.scripts.scraping.scrape_for_email import scrape_emails
from config.job_functions import write_progress, check_stop_signal
from config.logging import setup_logging
import logging

api_bp = Blueprint("api", __name__)

# Dictionary to track active scraping threads
active_jobs = {}

@api_bp.route("/scrape", methods=["POST"])
def start_scrape():
    """
    Start an email scraping job for a given URL.
    
    Request Body:
        - url (str): The base URL to scrape (e.g., "https://example.com").
        - max_pages (int, optional): Maximum number of pages to scrape (default: 10).
        - use_tor (bool, optional): Whether to use Tor for scraping (default: False).
        - headless (bool, optional): Whether to run WebDriver in headless mode (default: True).
    
    Returns:
        JSON response with job_id and status.
    """
    try:
        data = request.get_json()
        if not data or "url" not in data:
            return jsonify({"error": "Missing 'url' in request body"}), 400
        
        url = data["url"]
        max_pages = data.get("max_pages", 10)
        use_tor = data.get("use_tor", False)
        headless = data.get("headless", True)
        
        if not url.startswith(("http://", "https://")):
            url = f"https://{url}"
        
        job_id = str(uuid.uuid4())
        step_id = "email_scrape"
        
        # Initialize progress file
        write_progress(0, 1, job_id, step_id)
        
        # Start scraping in a separate thread
        def scrape_task():
            try:
                logging.info(f"Starting scrape job {job_id} for URL: {url}")
                emails = scrape_emails(url, max_pages=max_pages, use_tor=use_tor, headless=headless)
                
                # Save results to a file
                result_file = os.path.join(Config.TEMP_PATH, f"results_{job_id}.json")
                with open(result_file, "w") as f:
                    json.dump({"job_id": job_id, "url": url, "emails": emails}, f, indent=2)
                
                # Update progress to completed
                write_progress(1, 1, job_id, step_id)
                logging.info(f"Scrape job {job_id} completed. Found {len(emails)} emails.")
            except Exception as e:
                logging.error(f"Scrape job {job_id} failed: {e}")
                write_progress(0, 1, job_id, step_id, stop_call=True)
            finally:
                active_jobs.pop(job_id, None)
        
        # Start the thread
        thread = threading.Thread(target=scrape_task)
        active_jobs[job_id] = thread
        thread.start()
        
        return jsonify({"job_id": job_id, "status": "started", "url": url}), 202
    
    except Exception as e:
        logging.error(f"Error starting scrape job: {e}")
        return jsonify({"error": str(e)}), 500

@api_bp.route("/progress/<job_id>", methods=["GET"])
def get_progress(job_id):
    """
    Get the progress of a scraping job.
    
    Args:
        job_id (str): The unique job ID.
    
    Returns:
        JSON response with job progress details.
    """
    try:
        progress_file = os.path.join(Config.TEMP_PATH, f"progress_email_scrape_{job_id}.json")
        if not os.path.exists(progress_file):
            return jsonify({"error": f"Job {job_id} not found"}), 404
        
        with open(progress_file, "r") as f:
            progress = json.load(f)
        
        return jsonify({
            "job_id": job_id,
            "current_row": progress.get("current_row", 0),
            "total_rows": progress.get("total_rows", 1),
            "status": progress.get("status", "unknown")
        }), 200
    
    except Exception as e:
        logging.error(f"Error fetching progress for job {job_id}: {e}")
        return jsonify({"error": str(e)}), 500

@api_bp.route("/stop/<job_id>", methods=["POST"])
def stop_scrape(job_id):
    """
    Stop a running scraping job.
    
    Args:
        job_id (str): The unique job ID.
    
    Returns:
        JSON response indicating success or failure.
    """
    try:
        if job_id not in active_jobs:
            return jsonify({"error": f"Job {job_id} not found or already stopped"}), 404
        
        # Create stop signal file
        stop_file = os.path.join(Config.TEMP_PATH, f"stop_email_scrape.txt")
        with open(stop_file, "w") as f:
            f.write("stop")
        
        # Update progress to stopped
        write_progress(0, 1, job_id, "email_scrape", stop_call=True)
        
        # Wait for the thread to finish (optional, depending on your needs)
        active_jobs[job_id].join(timeout=10)
        active_jobs.pop(job_id, None)
        
        logging.info(f"Scrape job {job_id} stopped.")
        return jsonify({"job_id": job_id, "status": "stopped"}), 200
    
    except Exception as e:
        logging.error(f"Error stopping job {job_id}: {e}")
        return jsonify({"error": str(e)}), 500