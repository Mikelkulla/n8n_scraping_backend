from flask import Blueprint, jsonify, request, Response
import csv
import io
import os
import json
import threading
import uuid
import requests
from backend.app_settings import Config
from backend.scripts.scraping.scrape_for_email import scrape_emails
from config.job_functions import write_progress, check_stop_signal
from backend.scripts.google_api.google_places import call_google_places_api
from backend.database import Database
import logging
from config.logging import log_function_call
from config.utils import validate_emails, validate_url

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
@log_function_call
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
@log_function_call
def google_maps_scrape():
    """API endpoint to start a synchronous Google Maps scraping job.

    Searches for places on Google Maps by location and type, stores results in
    the database, and returns the leads directly in the response.

    Request JSON Body:
        location (str): The location to search (e.g., "Sarande, Albania").
        radius (int, optional): Search radius in metres. Defaults to 300.
        place_type (str, optional): Google place type (e.g., "lodging"). Defaults to "lodging".
        max_places (int, optional): Maximum number of places to retrieve. Defaults to 20.

    Returns:
        200 JSON with job_id, status "completed", and leads list, or 400/500 on error.
    """
    try:
        data = request.get_json()
        if not data or "location" not in data:
            return jsonify({"error": "Missing 'location' in request body"}), 400

        location = data["location"]
        if not isinstance(location, str) or not location.strip():
            return jsonify({"error": "Invalid location format"}), 400

        radius = data.get("radius", 300)
        place_type = data.get("place_type", "lodging")
        max_places = data.get("max_places", 20)

        job_id = str(uuid.uuid4())
        step_id = "google_maps_scrape"
        job_input = f"{place_type}:{location}"

        write_progress(job_id, step_id, input=job_input, status="running", total_rows=max_places)
        logging.info(f"Starting Google Maps scrape job {job_id} for '{job_input}'")

        leads = call_google_places_api(job_id, step_id, location, radius, place_type, max_places)

        final_count = len(leads)
        write_progress(job_id, step_id, input=job_input, status="completed",
                       current_row=final_count, total_rows=final_count)
        logging.info(f"Google Maps job {job_id} completed — {final_count} leads found.")

        return jsonify({
            "job_id": job_id,
            "input": job_input,
            "status": "completed",
            "leads": leads
        }), 200

    except Exception as e:
        logging.error(f"Google Maps scrape job failed: {e}")
        return jsonify({"error": str(e)}), 500

@api_bp.route("/progress/<job_id>", methods=["GET"])
@log_function_call
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
            # Try all known step_ids
            for step_id in ["email_scrape", "google_maps_scrape", "leads_email_scrape"]:
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
@log_function_call
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
            for possible_step_id in ["email_scrape", "google_maps_scrape", "leads_email_scrape"]:
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

@api_bp.route("/scrape/leads-emails", methods=["POST"])
@log_function_call
def scrape_leads_emails():
    """API endpoint to asynchronously scrape emails for all unscraped leads.

    Fetches leads that have a website but no scraped emails, spawns a background
    thread to process them, and returns immediately with a job_id.
    Poll GET /api/progress/<job_id> to track progress and completion.

    Request JSON Body:
        max_pages (int, optional): Max pages to scrape per website. Defaults to 30.
        use_tor (bool, optional): Whether to use Tor. Defaults to False.
        headless (bool, optional): Whether to run in headless mode. Defaults to True.

    Returns:
        202 JSON with job_id, status "started", and total_leads count.
        200 JSON with message if no unscraped leads are found.
        500 on unexpected error.
    """
    try:
        data = request.get_json() or {}
        max_pages = data.get("max_pages", 30)
        use_tor = data.get("use_tor", False)
        headless = data.get("headless", True)

        # Fetch unscraped leads before spawning the thread
        with Database() as db:
            leads = db.get_leads(status_filter="NOT scraped")

        if not leads:
            return jsonify({"message": "No unscraped leads found.", "count": 0}), 200

        job_id = str(uuid.uuid4())
        step_id = "leads_email_scrape"
        total = len(leads)
        job_input = f"{total} leads"

        # Register job immediately so /progress returns a result right away
        write_progress(job_id, step_id, input=job_input, status="running", total_rows=total)

        def scrape_task():
            processed = 0
            try:
                for lead in leads:
                    # Check stop signal before each lead
                    if check_stop_signal(step_id):
                        logging.info(f"Stop signal received for job {job_id} after {processed}/{total} leads.")
                        write_progress(job_id, step_id, input=job_input, status="stopped",
                                       current_row=processed, total_rows=total)
                        return

                    lead_id = lead.get("lead_id", "unknown")
                    place_id = lead.get("place_id")
                    execution_id = lead.get("execution_id")
                    website = lead.get("website")

                    if not website:
                        logging.warning(f"Lead {lead_id} has no website — skipping.")
                        try:
                            with Database() as db:
                                db.update_lead(place_id=place_id, execution_id=execution_id, status="skipped")
                        except Exception as e:
                            logging.error(f"Failed to mark lead {lead_id} as skipped: {e}")
                        processed += 1
                        write_progress(job_id, step_id, input=job_input,
                                       current_row=processed, total_rows=total)
                        continue

                    validated_url, url_error = validate_url(website)
                    if url_error:
                        logging.warning(f"Lead {lead_id} has invalid URL ({website}): {url_error}")
                        try:
                            with Database() as db:
                                db.update_lead(place_id=place_id, execution_id=execution_id, status="failed")
                        except Exception as e:
                            logging.error(f"Failed to mark lead {lead_id} as failed: {e}")
                        processed += 1
                        write_progress(job_id, step_id, input=job_input,
                                       current_row=processed, total_rows=total)
                        continue

                    # Scrape emails directly — avoids internal HTTP overhead and BASE_URL dependency
                    sub_job_id = str(uuid.uuid4())
                    try:
                        logging.info(f"Scraping emails for lead {lead_id} ({validated_url})")
                        emails = scrape_emails(
                            sub_job_id,
                            "email_scrape",
                            validated_url,
                            max_pages=max_pages,
                            use_tor=use_tor,
                            headless=headless,
                            sitemap_limit=10
                        )
                        valid_emails = validate_emails(emails)
                        emails_str = ','.join(valid_emails) if valid_emails else None
                        with Database() as db:
                            db.update_lead(place_id=place_id, execution_id=execution_id,
                                           emails=emails_str, status="scraped")
                        logging.info(f"Lead {lead_id}: stored {len(valid_emails)} email(s).")
                    except Exception as e:
                        logging.error(f"Failed to scrape lead {lead_id} ({validated_url}): {e}")
                        try:
                            with Database() as db:
                                db.update_lead(place_id=place_id, execution_id=execution_id, status="failed")
                        except Exception as db_err:
                            logging.error(f"Failed to mark lead {lead_id} as failed in DB: {db_err}")

                    processed += 1
                    write_progress(job_id, step_id, input=job_input,
                                   current_row=processed, total_rows=total)

                write_progress(job_id, step_id, input=job_input, status="completed",
                               current_row=total, total_rows=total)
                logging.info(f"Leads email scrape job {job_id} completed — {total} leads processed.")

            except Exception as e:
                logging.error(f"Leads email scrape job {job_id} failed: {e}")
                write_progress(job_id, step_id, input=job_input, status="failed",
                               current_row=processed, total_rows=total, error_message=str(e))
            finally:
                active_jobs.pop(job_id, None)

        start_job_thread(job_id, step_id, scrape_task)
        logging.info(f"Leads email scrape job {job_id} started — {total} leads queued.")
        return jsonify({"job_id": job_id, "status": "started", "total_leads": total}), 202

    except Exception as e:
        logging.error(f"Error starting leads email scrape: {e}")
        return jsonify({"error": str(e)}), 500


@api_bp.route("/leads/export", methods=["GET"])
@log_function_call
def export_leads():
    """Exports fully scraped leads that have at least a phone number or email as CSV.

    Query Parameters:
        format (str, optional): Response format — "csv" (default) or "json".

    Returns:
        A CSV file download or a JSON array of leads.
    """
    try:
        with Database() as db:
            leads = db.get_export_leads()

        if not leads:
            return jsonify({"message": "No leads available for export.", "count": 0}), 200

        fmt = request.args.get("format", "csv").lower()

        if fmt == "json":
            return jsonify({"count": len(leads), "leads": leads}), 200

        # CSV export
        fields = ["lead_id", "name", "location", "address", "phone", "website", "emails", "status", "created_at"]
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(leads)

        logging.info(f"Exported {len(leads)} leads as CSV")
        return Response(
            output.getvalue(),
            mimetype="text/csv",
            headers={"Content-Disposition": "attachment; filename=leads_export.csv"}
        )

    except Exception as e:
        logging.error(f"Error exporting leads: {e}")
        return jsonify({"error": str(e)}), 500