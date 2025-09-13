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
    """Starts a background job in a new thread.

    This function takes a task, which is a callable function, and runs it in a
    separate thread. The thread is stored in a global `active_jobs` dictionary,
    keyed by its `job_id`, to keep track of running jobs.

    Args:
        job_id (str): The unique identifier for the job.
        step_id (str): The identifier for the specific task or step.
        task (callable): The function to be executed in the new thread.
    """
    thread = threading.Thread(target=task)
    active_jobs[job_id] = thread
    thread.start()

@api_bp.route("/scrape/website-emails", methods=["POST"])
def start_scrape():
    """API endpoint to start a synchronous email scraping job.

    This endpoint initiates a scraping task for a given URL. The scraping is
    performed synchronously, and the results are returned directly in the
    HTTP response upon completion.

    Request JSON Body:
        url (str): The base URL of the website to scrape.
        max_pages (int, optional): The maximum number of pages to visit.
        use_tor (bool, optional): If True, routes traffic through the Tor network.
        headless (bool, optional): If True, runs the browser in headless mode.
        sitemap_limit (int, optional): The maximum number of sub-sitemaps to
            process.

    Returns:
        A JSON response containing the job details and the list of found emails,
        or an error message.
    """
    job_id = str(uuid.uuid4())
    step_id = "email_scrape"
    url = None  # Initialize url to None

    try:
        data = request.get_json()
        if not data or "url" not in data:
            return jsonify({"error": "Missing 'url' in request body"}), 400

        url, error = validate_url(data["url"])
        if error:
            return jsonify({"error": error}), 400

        max_pages = data.get("max_pages")
        use_tor = data.get("use_tor")
        headless = data.get("headless")
        sitemap_limit = data.get("sitemap_limit", 10)

        # Initialize progress in the database
        write_progress(job_id, step_id, input=url, status="running", use_tor=use_tor, headless=headless)

        logging.info(f"Starting synchronous scrape job {job_id} for URL: {url}")
        
        # Run scraping synchronously
        emails = scrape_emails(
            job_id,
            step_id,
            url,
            max_pages=max_pages,
            use_tor=use_tor,
            headless=headless,
            sitemap_limit=sitemap_limit
        )

        logging.info(f"Scrape job {job_id} completed. Found {len(emails)} emails.")
        
        # Return results directly in the response
        return jsonify({
            "job_id": job_id,
            "input": url,
            "emails": emails,
            "status": "completed"
        }), 200

    except Exception as e:
        logging.error(f"Scrape job {job_id} failed: {e}")
        # Ensure progress is updated to "failed"
        write_progress(
            job_id,
            step_id,
            input=url if url else "unknown",
            status="failed",
            error_message=str(e)
        )
        return jsonify({"error": str(e), "job_id": job_id}), 500

@api_bp.route("/scrape/google-maps", methods=["POST"])
def google_maps_scrape():
    """API endpoint to start a Google Maps scraping job.

    This endpoint initiates a background job to search for places on Google Maps
    based on a location and place type. The job runs asynchronously, and the
    results are stored in the database.

    Request JSON Body:
        location (str): The location to search for (e.g., "Sarande, Albania").
        radius (int, optional): The search radius in meters. Defaults to 300.
        place_type (str, optional): The type of place to search for (e.g.,
            "lodging", "restaurant"). Defaults to "lodging".
        max_places (int, optional): The maximum number of places to retrieve.
            Defaults to 20.

    Returns:
        A JSON response with the job_id and a "started" status, or an error
        message.
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
        def scrape_task():
            try:
                logging.info(f"Starting Google Maps scrape job {job_id} for location: {location}")
                leads = call_google_places_api(job_id, step_id, location, radius, place_type, max_places)

                # Save results to a file
                result_file = os.path.join(Config.TEMP_PATH, f"results_{step_id}_{job_id}.json")
                os.makedirs(Config.TEMP_PATH, exist_ok=True)
                with open(result_file, "w") as f:
                    json.dump({"job_id": job_id, "input": f"{place_type}:{location}", "leads": leads}, f, indent=2)

                # Use the actual number of leads found for progress update
                final_lead_count = len(leads)
                write_progress(job_id, step_id, input=None, status="completed", total_rows=final_lead_count)
                logging.info(f"Google Maps scrape job {job_id} completed. Found {final_lead_count} leads.")
            except Exception as e:
                logging.error(f"Google Maps scrape job {job_id} failed: {e}")
                write_progress(job_id, step_id, input=f"{place_type}:{location}", status="failed", stop_call=True, error_message=str(e))
            finally:
                active_jobs.pop(job_id, None)

        start_job_thread(job_id, step_id, scrape_task)
        return jsonify({"job_id": job_id, "status": "started", "input": location}), 202

    except Exception as e:
        logging.error(f"Error starting Google Maps scrape job: {e}")
        job_id = job_id if 'job_id' in locals() else str(uuid.uuid4())
        step_id = "google_maps_scrape"
        write_progress(job_id, step_id, input=f"{place_type}:{location}" if 'location' in locals() and 'place_type' in locals() else "unknown", status="failed", stop_call=True, error_message=str(e))
        return jsonify({"error": str(e)}), 500

@api_bp.route("/progress/<job_id>", methods=["GET"])
def get_progress(job_id):
    """API endpoint to retrieve the progress of a scraping job.

    This endpoint queries the database for the status and progress of a job
    identified by its `job_id`.

    Args:
        job_id (str): The unique identifier of the job to check.

    Returns:
        A JSON response containing the detailed progress of the job, or an
        error message if the job is not found.
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
    """API endpoint to stop a running scraping job.

    This endpoint signals a running job to terminate gracefully. It works for
    both synchronous and asynchronous jobs by creating a stop signal file that
    the scraping loops check for.

    Args:
        job_id (str): The unique identifier of the job to be stopped.

    Returns:
        A JSON response indicating whether the stop signal was successfully
        sent, or an error message if the job cannot be stopped.
    """
    try:
        step_id = None
        with Database() as db:
            # Check which type of job this is by looking it up in the database
            for possible_step_id in ["email_scrape", "google_maps_scrape"]:
                if db.get_job_execution(job_id, possible_step_id):
                    step_id = possible_step_id
                    break
        
        if not step_id:
            # If job is not in the database, it cannot be stopped.
            # Also check active_jobs for async jobs that might not have hit the DB yet.
            if job_id not in active_jobs:
                return jsonify({"error": f"Job {job_id} not found or not running"}), 404
            # If it's in active_jobs, we can infer the step_id, but this is less robust.
            # For now, we rely on the DB record.
        
        # Async jobs (google_maps_scrape) must be in active_jobs to be running.
        # Sync jobs (email_scrape) will not be in active_jobs.
        if step_id == "google_maps_scrape" and job_id not in active_jobs:
            return jsonify({"error": f"Job {job_id} is not running or already stopped"}), 404

        # Create the stop signal file. The scraping loops check for this file.
        stop_file = os.path.join(Config.TEMP_PATH, f"stop_{step_id}.txt")
        os.makedirs(Config.TEMP_PATH, exist_ok=True)
        with open(stop_file, "w") as f:
            f.write("stop")
        logging.info(f"Stop signal file created for job {job_id} (step: {step_id}).")

        # Update job status in the database to "stopped"
        with Database() as db:
            progress = db.get_job_execution(job_id, step_id)
            if progress and progress["status"] == "running":
                write_progress(
                    job_id=job_id,
                    step_id=step_id,
                    status="stopped",
                    stop_call=True,
                    # Carry over existing details
                    input=progress["input"],
                    max_pages=progress["max_pages"],
                    use_tor=progress["use_tor"],
                    headless=progress["headless"],
                    current_row=progress["current_row"],
                    total_rows=progress["total_rows"]
                )

        # For async jobs, which are in active_jobs, wait for the thread to terminate.
        if job_id in active_jobs:
            thread = active_jobs.get(job_id)
            if thread:
                thread.join(timeout=10)
                active_jobs.pop(job_id, None)
                logging.info(f"Asynchronous job {job_id} thread joined and removed.")

        return jsonify({"job_id": job_id, "status": "stopped"}), 200

    except Exception as e:
        logging.error(f"Error stopping job {job_id}: {e}")
        return jsonify({"error": str(e)}), 500

# This endpoint use scraping.db database's leads table to fill the email fields by scraping emails using website-emails endpoint
@api_bp.route("/scrape/leads-emails", methods=["POST"])
def scrape_leads_emails():
    """API endpoint to scrape emails for all unscraped leads in the database.

    This endpoint retrieves all leads from the database that have a website but
    have not yet been scraped for emails. It then iterates through each lead,
    calling the `/scrape/website-emails` endpoint for each one, and updates the
    lead's record with the found emails.

    Request JSON Body:
        max_pages (int, optional): Max pages to scrape per website. Defaults to 30.
        use_tor (bool, optional): Whether to use Tor. Defaults to False.
        headless (bool, optional): Whether to run in headless mode. Defaults to True.

    Returns:
        A JSON response summarizing the results of the scraping jobs for each lead.
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
                logging.info(f"Invalid website URL for lead {lead.get('lead_id', 'unknown')}: {error}")
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
                # The /scrape/website-emails endpoint is now synchronous and returns results directly
                response = requests.post(f"{base_url}/scrape/website-emails", json=scrape_payload, timeout=300) # 5-minute timeout
                
                job_data = response.json()
                job_id = job_data.get("job_id")
                status = job_data.get("status")

                if response.status_code != 200 or status != "completed":
                    error_message = job_data.get("error", "Scrape job did not complete successfully")
                    logging.error(f"Failed to scrape emails for {website}: {error_message}")
                    results.append({
                        "lead_id": lead.get("lead_id", "unknown"),
                        "website": website,
                        "job_id": job_id,
                        "status": status or "failed",
                        "emails": [],
                        "error": error_message
                    })
                    continue

                logging.info(f"Scrape job {job_id} for {website} completed.")
                
                # Get emails from the response and validate them
                emails = validate_emails(job_data.get("emails", []))

                # Update the database with the emails
                try:
                    with Database() as db:
                        emails_str = ','.join(emails) if emails else None
                        db.update_lead(
                            job_id=lead['job_id'],
                            place_id=lead['place_id'],
                            emails=emails_str,
                            status='scraped'
                        )
                        logging.info(f"Updated emails in DB for lead {lead['lead_id']}")
                        results.append({
                            "lead_id": lead.get("lead_id", "unknown"),
                            "website": website,
                            "job_id": job_id,
                            "status": "completed",
                            "emails": emails,
                            "error": None if emails else "No valid emails found"
                        })
                except Exception as db_err:
                    logging.error(f"Failed to update DB for lead {lead['lead_id']}: {db_err}")
                    results.append({
                        "lead_id": lead.get("lead_id", "unknown"),
                        "website": website,
                        "job_id": job_id,
                        "status": "completed",
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