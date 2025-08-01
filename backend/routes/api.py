from flask import Blueprint, jsonify, request
import os
import json
import threading
import uuid
import re
from backend.config import Config
from backend.scripts.scraping.scrape_for_email import scrape_emails
from config.job_functions import write_progress, check_stop_signal
from backend.scripts.google_api.google_places import call_google_places_api
from backend.database import get_job_execution
import logging

api_bp = Blueprint("api", __name__)

# Dictionary to track active scraping threads
active_jobs = {}

def start_job_thread(job_id, step_id, task):
    """
    Start a job in a separate thread and track it in active_jobs.

    Args:
        job_id (str): Unique job ID.
        step_id (str): Step ID for the job.
        task (callable): The task function to run in the thread.
    """
    thread = threading.Thread(target=task)
    active_jobs[job_id] = thread
    thread.start()

@api_bp.route("/scrape/website-emails", methods=["POST"])
def start_scrape():
    """
    Start an email scraping job for a given URL.

    Request Body:
        - url (str): The base URL to scrape (e.g., "https://example.com").
        - max_pages (int, optional): Maximum number of pages to scrape.
        - use_tor (bool, optional): Whether to use Tor for scraping.
        - headless (bool, optional): Whether to run WebDriver in headless mode.

    Returns:
        JSON response with job_id and status.
    """
    try:
        data = request.get_json()
        if not data or "url" not in data:
            return jsonify({"error": "Missing 'url' in request body"}), 400

        url = data["url"]
        # Validate URL format
        if not re.match(r"^https?://[\w\-]+(\.[\w\-]+)+[/\w\-]*$", url):
            if not url.startswith(("http://", "https://")):
                url = f"https://{url}"
            else:
                return jsonify({"error": "Invalid URL format"}), 400

        max_pages = data.get("max_pages")  # Allow None
        use_tor = data.get("use_tor")  # Allow None
        headless = data.get("headless")  # Allow None

        job_id = str(uuid.uuid4())
        step_id = "email_scrape"

        # Initialize progress in database
        # write_progress(job_id, step_id, input=url, max_pages=max_pages, use_tor=use_tor, headless=headless, status="running", current_row=None, total_rows=max_pages)

        # Start scraping in a separate thread
        def scrape_task():
            try:
                logging.info(f"Starting scrape job {job_id} for URL: {url}")
                emails = scrape_emails(job_id, step_id, url, max_pages=max_pages, use_tor=use_tor, headless=headless)

                # Save results to a file
                result_file = os.path.join(Config.TEMP_PATH, f"results_{job_id}.json")
                os.makedirs(Config.TEMP_PATH, exist_ok=True)
                with open(result_file, "w") as f:
                    json.dump({"job_id": job_id, "input": url, "emails": emails}, f, indent=2)

                logging.info(f"Scrape job {job_id} completed. Found {len(emails)} emails.")
            except Exception as e:
                logging.error(f"Scrape job {job_id} failed: {e}")
                write_progress(job_id, step_id, input=url, max_pages=max_pages, use_tor=use_tor, headless=headless, status="failed", stop_call=True, error_message=str(e), current_row=None, total_rows=max_pages)
            finally:
                active_jobs.pop(job_id, None)

        start_job_thread(job_id, step_id, scrape_task)
        return jsonify({"job_id": job_id, "status": "started", "input": url}), 202

    except Exception as e:
        logging.error(f"Error starting scrape job: {e}")
        job_id = job_id if 'job_id' in locals() else str(uuid.uuid4())
        step_id = "email_scrape"
        write_progress(job_id, step_id, input=url if 'url' in locals() else "unknown", max_pages=None, use_tor=None, headless=None, status="failed", stop_call=True, error_message=str(e), current_row=None, total_rows=None)
        return jsonify({"error": str(e)}), 500

@api_bp.route("/scrape/google-maps", methods=["POST"])
def google_maps_scrape():
    """
    Scrape Google Maps for places in a given location and store results in the leads table.

    Request Body:
        - location (str): Location to search (e.g., "Sarande, Albania").
        - radius (int, optional): Search radius in meters (default: 300).
        - place_type (str, optional): Google Place type (default: "lodging").
        - max_places (int, optional): Maximum number of places to fetch (default: 20).

    Returns:
        JSON response with job_id and status.
    """
    try:
        data = request.get_json()
        if not data or "location" not in data:
            return jsonify({"error": "Missing 'location' in request body"}), 400

        location = data["location"]
        # Validate location (basic check for non-empty string with letters)
        if not isinstance(location, str) or not re.match(r"^[a-zA-Z\s,]+$", location):
            return jsonify({"error": "Invalid location format"}), 400

        radius = data.get("radius", 300)
        place_type = data.get("place_type", "lodging")
        max_places = data.get("max_places", 20)

        job_id = str(uuid.uuid4())
        step_id = "google_maps_scrape"

        # Initialize progress in database
        write_progress(job_id, step_id, input=location, max_pages=None, use_tor=None, headless=None, status="running", current_row=None, total_rows=max_places)

        # Start Google Maps scraping in a separate thread
        def scrape_task():
            try:
                logging.info(f"Starting Google Maps scrape job {job_id} for location: {location}")
                leads = call_google_places_api(job_id, location, radius, place_type, max_places)

                # Save results to a file
                result_file = os.path.join(Config.TEMP_PATH, f"results_{job_id}.json")
                os.makedirs(Config.TEMP_PATH, exist_ok=True)
                with open(result_file, "w") as f:
                    json.dump({"job_id": job_id, "input": location, "leads": leads}, f, indent=2)

                # write_progress(job_id, step_id, input=location, max_pages=None, use_tor=None, headless=None, status="completed", current_row=len(leads), total_rows=max_places)
                logging.info(f"Google Maps scrape job {job_id} completed. Found {len(leads)} leads.")
            except Exception as e:
                logging.error(f"Google Maps scrape job {job_id} failed: {e}")
                write_progress(job_id, step_id, input=location, max_pages=None, use_tor=None, headless=None, status="failed", stop_call=True, error_message=str(e), current_row=None, total_rows=max_places)
            finally:
                active_jobs.pop(job_id, None)

        start_job_thread(job_id, step_id, scrape_task)
        return jsonify({"job_id": job_id, "status": "started", "input": location}), 202

    except Exception as e:
        logging.error(f"Error starting Google Maps scrape job: {e}")
        job_id = job_id if 'job_id' in locals() else str(uuid.uuid4())
        step_id = "google_maps_scrape"
        write_progress(job_id, step_id, input=location if 'location' in locals() else "unknown", max_pages=None, use_tor=None, headless=None, status="failed", stop_call=True, error_message=str(e), current_row=None, total_rows=None)
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
        # Try both possible step_ids
        for step_id in ["email_scrape", "google_maps_scrape"]:
            progress = get_job_execution(job_id, step_id)
            if progress:
                return jsonify({
                    "job_id": job_id,
                    "step_id": step_id,
                    "input": progress["input"],
                    "max_pages": progress["max_pages"],
                    "use_tor": progress["use_tor"],
                    "headless": progress["headless"],
                    "current_row": progress["current_row"],
                    "total_rows": progress["total_rows"],
                    "status": progress["status"],
                    "error_message": progress["error_message"]
                }), 200

        return jsonify({"error": f"Job {job_id} not found"}), 404

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

        # Try both possible step_ids
        step_id = None
        progress = None
        for possible_step_id in ["email_scrape", "google_maps_scrape"]:
            progress = get_job_execution(job_id, possible_step_id)
            if progress:
                step_id = possible_step_id
                break

        if not step_id or not progress:
            return jsonify({"error": f"Job {job_id} not found in database"}), 404

        # Create stop signal file
        stop_file = os.path.join(Config.TEMP_PATH, f"stop_{step_id}.txt")
        os.makedirs(Config.TEMP_PATH, exist_ok=True)
        with open(stop_file, "w") as f:
            f.write("stop")

        # Update progress to stopped
        progress = get_job_execution(job_id, step_id)
        if progress:
            write_progress(
                job_id=job_id,
                step_id=step_id,
                input=progress["input"],
                max_pages=progress["max_pages"],
                use_tor=progress["use_tor"],
                headless=progress["headless"],
                status="stopped",
                stop_call=True,
                current_row=progress["current_row"],
                total_rows=progress["total_rows"]
            )
        
        # Wait for the thread to finish
        active_jobs[job_id].join(timeout=10)
        active_jobs.pop(job_id, None)

        logging.info(f"Scrape job {job_id} stopped.")
        return jsonify({"job_id": job_id, "status": "stopped"}), 200

    except Exception as e:
        logging.error(f"Error stopping job {job_id}: {e}")
        return jsonify({"error": str(e)}), 500

# @api_bp.route("/scrape/google-maps", methods=["POST"])
# def google_maps_scrape():
#     """
#     Scrape Google Maps for places in a given location and store results in the leads table.
    
#     Request Body:
#         - location (str): Location to search (e.g., "Sarande, Albania").
#         - radius (int, optional): Search radius in meters (default: 300).
#         - place_type (str, optional): Google Place type (default: "lodging").
    
#     Returns:
#         JSON response with job_id and status.
#     """
#     try:
#         data = request.get_json()
#         if not data or "location" not in data:
#             return jsonify({"error": "Missing 'location' in request body"}), 400
        
#         location = data["location"]
#         radius = data.get("radius", 300)
#         place_type = data.get("place_type", "lodging")
        
#         job_id = str(uuid.uuid4())
#         step_id = "google_maps_scrape"
        
#         # Initialize progress in database
#         write_progress(job_id, step_id, location, max_pages=5, use_tor=False, headless=True, status="running", current_row=0, total_rows=5)
        
#         # Start Google Maps scraping in a separate thread
#         def scrape_task():
#             try:
#                 logging.info(f"Starting Google Maps scrape job {job_id} for location: {location}")
#                 leads = call_google_places_api(job_id, location, radius, place_type)
                
#                 # Update progress to completed
#                 write_progress(job_id, step_id, location, max_pages=5, use_tor=False, headless=True, status="completed", current_row=len(leads), total_rows=5)
#                 logging.info(f"Google Maps scrape job {job_id} completed. Found {len(leads)} leads.")
#             except Exception as e:
#                 logging.error(f"Google Maps scrape job {job_id} failed: {e}")
#                 write_progress(job_id, step_id, location, max_pages=5, use_tor=False, headless=True, status="failed", stop_call=True, error_message=str(e), current_row=0, total_rows=5)
#             finally:
#                 active_jobs.pop(job_id, None)
        
#         # Start the thread
#         thread = threading.Thread(target=scrape_task)
#         active_jobs[job_id] = thread
#         thread.start()
        
#         return jsonify({"job_id": job_id, "status": "started", "location": location}), 202
    
#     except Exception as e:
#         logging.error(f"Error starting Google Maps scrape job: {e}")
#         job_id = job_id if 'job_id' in locals() else str(uuid.uuid4())
#         step_id = "google_maps_scrape"
#         write_progress(job_id, step_id, location, max_pages=5, use_tor=False, headless=True, status="failed", error_message=str(e), current_row=0, total_rows=5)
#         return jsonify({"error": str(e)}), 500