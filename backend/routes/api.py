from flask import Blueprint, jsonify, request
import os
import json
import threading
import uuid
import requests
from backend.config import Config
from backend.scripts.scraping.scrape_for_email import scrape_emails
from config.job_functions import write_progress
from backend.scripts.google_api.google_places import call_google_places_api
from backend.database import Database
import logging
from config.utils import validate_emails, validate_url, poll_job_progress, read_job_results

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

        url, error = validate_url(data["url"])
        if error:
            return jsonify({"error": error}), 400

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

                # Prepare the result dictionary
                result = {"job_id": job_id, "input": url, "emails": emails}

                # Save results to a single file
                result_file = os.path.join(Config.TEMP_PATH, f"results_{step_id}.json")
                os.makedirs(Config.TEMP_PATH, exist_ok=True)
                
                # Read existing results, append new result, and write back
                try:
                    with open(result_file, "r") as f:
                        data = json.load(f)
                        if not isinstance(data, list):
                            data = [data]  # Convert to list if it's a single dict
                except (FileNotFoundError, json.JSONDecodeError):
                    data = []  # Initialize as empty list if file doesn't exist or is empty

                # Append new result
                data.append(result)

                # Write the updated list back to the file
                with open(result_file, "w") as f:
                    json.dump(data, f, indent=2)
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
        if not isinstance(location, str): # or not re.match(r"^[a-zA-Z\s,]+$", location):
            return jsonify({"error": "Invalid location format"}), 400

        radius = data.get("radius", 300)
        place_type = data.get("place_type", "lodging")
        max_places = data.get("max_places", 20)

        job_id = str(uuid.uuid4())
        step_id = "google_maps_scrape"

        # Initialize progress in database
        write_progress(job_id, step_id, input=f"{place_type}:{location}", status="running", total_rows=max_places)

        # Start Google Maps scraping in a separate thread
        def scrape_task(max_places):
            try:
                logging.info(f"Starting Google Maps scrape job {job_id} for location: {location}")
                leads = call_google_places_api(job_id, step_id, location, radius, place_type, max_places)

                # Save results to a file
                result_file = os.path.join(Config.TEMP_PATH, f"results_{step_id}_{job_id}.json")
                os.makedirs(Config.TEMP_PATH, exist_ok=True)
                with open(result_file, "w") as f:
                    json.dump({"job_id": job_id, "input": f"{place_type}:{location}", "leads": leads}, f, indent=2)

                max_places = min(len(leads), max_places)
                write_progress(job_id, step_id, input=None, status="completed", total_rows=max_places)
                logging.info(f"Google Maps scrape job {job_id} completed. Found {len(leads)} leads.")
            except Exception as e:
                logging.error(f"Google Maps scrape job {job_id} failed: {e}")
                write_progress(job_id, step_id, input=f"{place_type}:{location}", status="failed", stop_call=True, error_message=str(e))
            finally:
                active_jobs.pop(job_id, None)

        start_job_thread(job_id, step_id, scrape_task(max_places))
        return jsonify({"job_id": job_id, "status": "started", "input": location}), 202

    except Exception as e:
        logging.error(f"Error starting Google Maps scrape job: {e}")
        job_id = job_id if 'job_id' in locals() else str(uuid.uuid4())
        step_id = "google_maps_scrape"
        write_progress(job_id, step_id, input=f"{place_type}:{location}" if 'location' in locals() and 'place_type' in locals() else "unknown", status="failed", stop_call=True, error_message=str(e))
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
        with Database() as db:
            # Try both possible step_ids
            for step_id in ["email_scrape", "google_maps_scrape"]:
                progress = db.get_job_execution(job_id, step_id)
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

        with Database() as db:
            # Try both possible step_ids
            step_id = None
            progress = None
            for possible_step_id in ["email_scrape", "google_maps_scrape"]:
                progress = db.get_job_execution(job_id, possible_step_id)
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
            progress = db.get_job_execution(job_id, step_id)
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

# This endpoint use scraping.db database's leads table to fill the email fields by scraping emails using website-emails endpoint
@api_bp.route("/scrape/leads-emails", methods=["POST"])
def scrape_leads_emails():
    """
    Start email scraping for websites in the leads table, monitor progress, and update emails in the database.

    Request Body:
        - max_pages (int, optional): Maximum number of pages to scrape per website.
        - use_tor (bool, optional): Whether to use Tor for scraping.
        - headless (bool, optional): Whether to run WebDriver in headless mode.

    Returns:
        JSON response with job IDs, their statuses, and collected emails.
    """
    try:
        data = request.get_json() or {}
        max_pages = data.get("max_pages", 30)  # Default to 30 pages
        use_tor = data.get("use_tor", False)   # Default to False
        headless = data.get("headless", True)  # Default to True

        # Fetch leads from the database by default
        with Database() as db:
            leads = db.get_leads(status_filter="NOT scraped")

        # For testing only (override with hardcoded leads if TEST_MODE is set)
        if os.getenv("TEST_MODE") == "true":
            leads = [
                {
                    'lead_id': 543, 
                    'job_id': 'a88b3c6b-023a-4e63-b690-0e16e3cd5f2e', 
                    'place_id': 'ChIJg5a-uVXAwoARXHDwQRVHnh4', 
                    'location': 'dental_clinic:North Los Angeles', 
                    'name': 'ProDent Care: Tereza Hambarchian, DDS', 
                    'address': '213 N Orange St F, Glendale, CA 91203, USA', 
                    'phone': '+1 818-296-0916', 
                    'website': 'http://www.prodentcare.com', 
                    'emails': None, 
                    'created_at': '2025-08-11 20:51:52', 
                    'updated_at': '2025-08-11 20:51:52', 
                    'status': 'scraped'
                },
                {
                    'lead_id': 386, 
                    'job_id': '36d59700-c05a-4955-a94e-7b7af9ac65c9', 
                    'place_id': 'ChIJlxusK0-3woARG9AAHdBJhpE', 
                    'location': 'dental_clinic:North Los Angeles', 
                    'name': 'Smile L.A. Downtown Modern Dentistry',
                    'address': '523 W 6th St #202, Los Angeles, CA 90014, USA', 
                    'phone': '+1 213-286-0020', 
                    'website': 'https://smilela.com', 
                    'emails': None, 
                    'created_at': '2025-08-11 20:51:45', 
                    'updated_at': '2025-08-04 12:24:46', 
                    'status': None
                }
            ]
        if not leads:
            return jsonify({"error": "No leads found in the database"}), 404

        # Initialize results
        results = []
        base_url = os.getenv("BASE_URL")  # Adjust if your API runs elsewhere

        for lead in leads:
            website = lead.get("website")
            if not website:
                logging.warning(f"Lead {lead.get('lead_id', 'unknown')} has no website, skipping.")
                try:
                    with Database() as db:
                        db.update_lead(
                            job_id=lead.get("job_id"),
                            place_id=lead.get("place_id"),
                            status="skipped"
                        )
                    logging.info(f"Updated lead {lead.get('lead_id')} status to 'skipped' in DB.")
                except Exception as e:
                    logging.error(f"Failed to update status for lead {lead.get('lead_id')} to 'skipped': {e}")

                results.append({
                    "lead_id": lead.get("lead_id", "unknown"),
                    "website": None,
                    "job_id": None,
                    "status": "skipped",
                    "emails": [],
                    "error": "No website provided"
                })
                continue

            # Validate and normalize website URL
            website, error = validate_url(website)
            if error:
                logging.error(f"Invalid website URL for lead {lead.get('lead_id', 'unknown')}: {error}")
                try:
                    with Database() as db:
                        db.update_lead(
                            job_id=lead.get("job_id"),
                            place_id=lead.get("place_id"),
                            status="failed"
                        )
                    logging.info(f"Updated lead {lead.get('lead_id')} status to 'failed' in DB.")
                except Exception as e:
                    logging.error(f"Failed to update status for lead {lead.get('lead_id')} to 'failed': {e}")

                results.append({
                    "lead_id": lead.get("lead_id", "unknown"),
                    "website": website,
                    "job_id": None,
                    "status": "failed",
                    "emails": [],
                    "error": error
                })
                continue

            # Start scraping job for the lead's website
            scrape_payload = {
                "url": website,
                "max_pages": max_pages,
                "use_tor": use_tor,
                "headless": headless
            }
            try:
                response = requests.post(f"{base_url}/scrape/website-emails", json=scrape_payload)
                if response.status_code != 202:
                    logging.error(f"Failed to start scrape job for {website}: {response.json()}")
                    results.append({
                        "lead_id": lead.get("lead_id", "unknown"),
                        "website": website,
                        "job_id": None,
                        "status": "failed",
                        "emails": [],
                        "error": f"Scrape job initiation failed: {response.json().get('error')}"
                    })
                    continue

                job_data = response.json()
                job_id = job_data["job_id"]
                logging.info(f"Started scrape job {job_id} for {website}")

                # Poll job progress
                progress_result = poll_job_progress(base_url, job_id)
                status = progress_result["status"]
                error = progress_result["error"]

                if status != "completed":
                    results.append({
                        "lead_id": lead.get("lead_id", "unknown"),
                        "website": website,
                        "job_id": job_id,
                        "status": status,
                        "emails": [],
                        "error": error or "Job did not complete successfully"
                    })
                    continue

                # Read job results
                result_file = os.path.join(Config.TEMP_PATH, "results_email_scrape.json")
                job_result = read_job_results(result_file, job_id)
                emails = job_result["emails"]
                if job_result["error"]:
                    results.append({
                        "lead_id": lead.get("lead_id", "unknown"),
                        "website": website,
                        "job_id": job_id,
                        "status": status,
                        "emails": [],
                        "error": job_result["error"]
                    })
                    continue
                # Validate emails
                emails = validate_emails(emails)

                # Update the database with the emails
                try:
                    with Database() as db:
                        emails_str = ','.join(emails) if emails else None  # Convert to string or None
                        db.update_lead(
                            job_id=lead['job_id'], 
                            place_id=lead['place_id'], 
                            emails=emails_str, 
                            status='scraped'
                            )

                        logging.info(f"Updated emails in DB for lead {lead['lead_id']} (place_id: {lead['place_id']})")
                        results.append(
                            {
                            "lead_id": lead.get("lead_id", "unknown"),
                            "website": website,
                            "job_id": job_id,
                            "status": status,
                            "emails": emails,
                            "error": None if emails else "No valid emails found"
                            }
                        )
                except Exception as db_err:
                    logging.error(f"Failed to update DB for lead {lead['lead_id']}: {db_err}")
                    results.append({
                        "lead_id": lead.get("lead_id", "unknown"),
                        "website": website,
                        "job_id": job_id,
                        "status": status,
                        "emails": emails,
                        "error": f"Database update failed: {str(db_err)}"
                    })

            except requests.RequestException as e:
                logging.error(f"Error initiating scrape job for {website}: {e}")
                results.append({
                    "lead_id": lead.get("lead_id", "unknown"),
                    "website": website,
                    "job_id": None,
                    "status": "failed",
                    "emails": [],
                    "error": f"Failed to initiate scrape job: {str(e)}"
                })

        return jsonify({
            "status": "completed",
            "results": results
        }), 200

    except Exception as e:
        logging.error(f"Error in scrape_leads_emails: {e}")
        return jsonify({"error": str(e)}), 500