# config/utils.py
import time
import pandas as pd
import os
import logging
import re
import requests
import json
import time
from urllib.parse import urlparse


def load_csv(input_csv, output_csv, required_columns=None):
    """
    Loads a CSV file for processing, using the output CSV as input if it exists.
    Ensures the output directory exists and validates required columns.

    Parameters:
    -----------
    input_csv (str): Path to the input CSV file.
    output_csv (str): Path to save the updated CSV file.
    required_columns (list, optional): List of column names that must exist in the CSV.

    Returns:
    --------
    tuple: (pd.DataFrame, str) - The loaded DataFrame and the resolved input CSV path,
           or (None, None) if an error occurs.
    """
    try:
        # Ensure output directory exists
        os.makedirs(os.path.dirname(output_csv), exist_ok=True)

        # Check if output file exists and use it as input if available
        if os.path.exists(output_csv):
            logging.info(f"Output file '{output_csv}' exists, using it as input")
            resolved_input_csv = output_csv
        else:
            logging.info(f"No output file found, using input file '{input_csv}'")
            resolved_input_csv = input_csv

        # Read the CSV file
        logging.info(f"Reading CSV: {resolved_input_csv}")
        df = pd.read_csv(resolved_input_csv, dtype=str, keep_default_na=False)

        # Validate required columns if provided
        if required_columns:
            for col in required_columns:
                if col not in df.columns:
                    raise ValueError(f"Column '{col}' not found in CSV")

        return df, resolved_input_csv

    except FileNotFoundError:
        logging.error(f"Input CSV file '{resolved_input_csv}' not found.")
        print(f"Error: Input CSV file '{resolved_input_csv}' not found.")
        return None, None
    except Exception as e:
        logging.error(f"Error loading CSV: {e}")
        print(f"Error loading CSV: {e}")
        return None, None
    
def is_non_business_domain(domain):
    """
    Check if the domain is a common non-business website.
    
    Args:
        domain (str): Domain to check (e.g., 'facebook.com')
    
    Returns:
        bool: True if domain is a non-business website, False otherwise
    """
    non_business_domains = [
        'airbnb.co.uk', 'airbnb.co.za', 'airbnb.com', 'airbnb.mx', 'airbnb.net',
        'airbnbmail.com', 'booking.com', 'facebook.com', 'instagram.com', 'jscache.com',
        'linkedin.com', 'muscache.com', 'pinterest.com', 'snapchat.com', 'tacdn.com',
        'tamgrt.com', 'tiktok.com', 'tripadvisor.cn', 'tripadvisor.co.uk',
        'tripadvisor.com', 'tripadvisor.de', 'twitter.com', 'x.com', 'youtube.com'
    ]
    # Check if domain or any subdomain matches non-business domains
    domain = domain.lower()
    for non_business in non_business_domains:
        if domain == non_business or domain.endswith('.' + non_business):
            return True
    return False

def extract_base_url(url):
    """
    Extract the base URL (e.g., https://www.domain.com) from an email address or URL,
    removing paths and parameters.
    
    Args:
        email_or_url (str): Email address (e.g., 'user@sub.example.com') or URL
                           (e.g., 'https://www.example.com/contact?param=1')
    
    Returns:
        str: Base URL (e.g., 'https://www.example.com') or None if invalid
    """
    try:
        # Add scheme if missing
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        # Parse URL and extract scheme and netloc
        parsed = urlparse(url)
        domain = parsed.netloc
        # Check if domain is a non-business website
        if is_non_business_domain(domain):
            logging.info("Not a business domain.")
            return None
        base_url = f'{parsed.scheme}://{parsed.netloc}'
        
        # Ensure lowercase for consistency
        return base_url.lower()
    except Exception as e:
        logging.info(f'Error: {e}')
        return None

def validate_url(url):
    """
    Validate a URL, normalize it by adding https:// if no scheme is provided.
    and check if the domain is a non-business domain.
    Args:
        url (str): URL to validate.
    
    Returns:
        tuple: (str, str) - (Normalized base URL, error message if invalid or non-business, else None)
    """
    # List of non-business domains
    non_business_domains = [
        'airbnb.co.uk', 'airbnb.co.za', 'airbnb.com', 'airbnb.mx', 'airbnb.net',
        'airbnbmail.com', 'booking.com', 'facebook.com', 'instagram.com', 'jscache.com',
        'linkedin.com', 'muscache.com', 'pinterest.com', 'snapchat.com', 'tacdn.com',
        'tamgrt.com', 'tiktok.com', 'tripadvisor.cn', 'tripadvisor.co.uk',
        'tripadvisor.com', 'tripadvisor.de', 'twitter.com', 'x.com', 'youtube.com', "ihg.com"
    ]

    try:
        # Validate URL format
        if not re.match(r"^https?://[\w\-]+(\.[\w\-]+)+[/\w\-\?\=\&\.\;\%]*$", url):
            if not url.startswith(("http://", "https://")):
                url = f"https://{url}"
                if not re.match(r"^https?://[\w\-]+(\.[\w\-]+)+[/\w\-\?\=\&\.\;\%]*$", url):
                    return None, "Invalid URL format"
            else:
                return None, "Invalid URL format"
        
        # Parse URL to extract domain
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        
        # Extract second-level domain (SLD) from input domain
        domain_parts = domain.split('.')
        sld = domain_parts[-2] if len(domain_parts) >= 2 else domain
        
        # Check if the SLD matches the SLD of any non-business domain
        for non_business in non_business_domains:
            non_business_parts = non_business.split('.')
            non_business_sld = non_business_parts[-2] if len(non_business_parts) >= 2 else non_business
            if sld == non_business_sld:
                logging.info(f"Non-business domain: {domain} (SLD: {sld})")
                return None, "Non-business domain"
        
        # Return normalized base URL
        base_url = f'{parsed.scheme}://{parsed.netloc}'.lower()
        return base_url, None

    except Exception as e:
        logging.error(f"Error validating URL {url}: {e}")
        return None, f"Error validating URL: {str(e)}"

def poll_job_progress(base_url, job_id, max_retries=720, retry_delay=5):
    """
    Poll the progress of a job until it completes, fails, or is stopped.
    
    Args:
        base_url (str): Base URL of the API (e.g., 'http://localhost:5000/api').
        job_id (str): Unique job ID to track.
        max_retries (int): Maximum number of retries for progress checks.
        retry_delay (int): Seconds to wait between retries.
    
    Returns:
        dict: Progress data with status, emails (if completed), and error (if any).
    """
    for attempt in range(max_retries):
        try:
            progress_response = requests.get(f"{base_url}/progress/{job_id}")
            if progress_response.status_code == 200:
                progress = progress_response.json()
                status = progress.get("status")
                if status in ["completed", "failed", "stopped"]:
                    return {
                        "status": status,
                        "progress": progress,
                        "emails": [],
                        "error": progress.get("error_message") if status != "completed" else None
                    }
                logging.info(f"Status: {status} - Attempt {attempt + 1}/{max_retries} succeded for job {job_id}: {progress_response.json()}")
                time.sleep(3)  # Wait before polling again
            else:
                logging.warning(f"Attempt {attempt + 1}/{max_retries} failed for job {job_id}: {progress_response.json()}")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
        except requests.RequestException as e:
            logging.warning(f"Attempt {attempt + 1}/{max_retries} failed for job {job_id}: {e}")
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
    return {
        "status": "failed",
        "progress": None,
        "emails": [],
        "error": f"Progress check failed after {max_retries} attempts"
    }

def read_job_results(result_file, job_id, max_retries=3, retry_delay=2):
    """
    Read job results from a JSON file, retrying if necessary.
    
    Args:
        result_file (str): Path to the JSON results file.
        job_id (str): Unique job ID to find results for.
        max_retries (int): Maximum number of retries for reading the file.
        retry_delay (int): Seconds to wait between retries.
    
    Returns:
        dict: Results containing emails and error (if any).
    """
    for attempt in range(max_retries):
        try:
            with open(result_file, "r") as f:
                job_results = json.load(f)
                if not isinstance(job_results, list):
                    job_results = [job_results]
                for job_result in job_results:
                    if job_result.get("job_id") == job_id:
                        return {
                            "emails": job_result.get("emails", []),
                            "error": None
                        }
                raise ValueError(f"Job ID {job_id} not found in result file")
        except (FileNotFoundError, json.JSONDecodeError, ValueError) as e:
            logging.warning(f"Attempt {attempt + 1}/{max_retries} failed reading results file for job {job_id}: {e}")
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
            continue
    return {
        "emails": [],
        "error": f"Failed to read results file after {max_retries} attempts"
    }

def is_example_domain(email):
    """
    Check if an email belongs to a common example domain.
    
    Args:
        email (str): Email address to check.
    
    Returns:
        bool: True if email uses an example domain, False otherwise.
    """
    EXAMPLE_DOMAINS = {"example.me","example.com", "example.org", "example.net", "test.com", "sample.com"}
    email = email.lower()
    domain = email.split('@')[-1]
    for example_domain in EXAMPLE_DOMAINS:
        if domain == example_domain or domain.endswith('.' + example_domain):
            return True
    return False

def validate_emails(emails):
    """
    Validate a list of emails and filter out invalid or example domain emails.
    
    Args:
        emails (list): List of email addresses to validate.
    
    Returns:
        list: Validated and filtered email addresses.
    """
    email_regex = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")
    return [email for email in emails if email_regex.match(email) and not is_example_domain(email)]