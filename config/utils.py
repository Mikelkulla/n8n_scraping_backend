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
    """Loads a CSV file, prioritizing an existing output file over the input file.

    This function is designed to resume processing by loading a partially
    completed output file if it exists. It ensures the output directory is
    present and can validate that the CSV contains a specific set of columns.

    Args:
        input_csv (str): The path to the primary input CSV file.
        output_csv (str): The path where the output CSV is stored. If this file
            exists, it will be loaded instead of `input_csv`.
        required_columns (list[str], optional): A list of column names that must
            be present in the loaded CSV file. Defaults to None.

    Returns:
        tuple[pd.DataFrame, str] | tuple[None, None]: A tuple containing the
        loaded DataFrame and the path of the file that was read. Returns
        (None, None) if the file cannot be loaded or if a required column
        is missing.
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
    """Checks if a domain belongs to a list of common non-business websites.

    This function is used to filter out domains that are typically not associated
    with business entities, such as social media platforms and large consumer
    services.

    Args:
        domain (str): The domain name to check (e.g., 'facebook.com').

    Returns:
        bool: True if the domain is in the non-business list, False otherwise.
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
    """Extracts and normalizes the base URL from a given URL string.

    This function takes a URL, ensures it has a scheme (defaulting to 'https://'),
    and returns the base part of the URL (scheme and domain). It also checks if
    the domain is a known non-business domain and returns None in that case.

    Args:
        url (str): The URL to process.

    Returns:
        str | None: The normalized base URL (e.g., 'https://www.example.com')
        or None if the URL is invalid or belongs to a non-business domain.
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
    """Validates and normalizes a URL.

    This function checks if a URL is well-formed, normalizes it by adding a
    scheme if one is missing, and verifies that it does not belong to a known
    non-business domain.

    Args:
        url (str): The URL to validate.

    Returns:
        tuple[str, str] | tuple[None, str]: A tuple containing the normalized
        base URL and None if the URL is valid. Otherwise, a tuple of None
        and an error message.
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
    """Polls a job's progress endpoint until it reaches a terminal state.

    This function repeatedly checks the progress of a background job by calling
    its API endpoint. It continues until the job's status is 'completed',
    'failed', or 'stopped', or until the maximum number of retries is reached.

    Args:
        base_url (str): The base URL of the API.
        job_id (str): The unique identifier of the job to poll.
        max_retries (int, optional): The maximum number of times to poll the
            endpoint. Defaults to 720.
        retry_delay (int, optional): The number of seconds to wait between
            polling attempts. Defaults to 5.

    Returns:
        dict: A dictionary containing the final status of the job, the last
        known progress data, and any error message.
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
    """Reads the results of a specific job from a JSON file.

    This function attempts to read a JSON file that contains the results of one
    or more jobs. It searches for the results corresponding to the given `job_id`.
    It includes a retry mechanism to handle cases where the file might not be
    immediately available.

    Args:
        result_file (str): The path to the JSON file containing job results.
        job_id (str): The unique identifier of the job whose results are needed.
        max_retries (int, optional): The maximum number of times to attempt
            reading the file. Defaults to 3.
        retry_delay (int, optional): The number of seconds to wait between
            retries. Defaults to 2.

    Returns:
        dict: A dictionary containing the job's results (e.g., a list of emails)
        and an error message if the results could not be read.
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
    """Checks if an email address belongs to a common example domain.

    This function is used to filter out email addresses that use placeholder or
    test domains (e.g., 'example.com', 'test.com').

    Args:
        email (str): The email address to check.

    Returns:
        bool: True if the email's domain is an example domain, False otherwise.
    """
    EXAMPLE_DOMAINS = {"example.me","example.com", "example.org", "example.net", "test.com", "sample.com"}
    email = email.lower()
    domain = email.split('@')[-1]
    for example_domain in EXAMPLE_DOMAINS:
        if domain == example_domain or domain.endswith('.' + example_domain):
            return True
    return False

def validate_emails(emails):
    """Validates and filters a list of email addresses.

    This function takes a list of emails and returns a new list containing only
    the emails that are well-formed and do not belong to an example domain.

    Args:
        emails (list[str]): A list of email addresses to validate.

    Returns:
        list[str]: A list of valid and non-example email addresses.
    """
    email_regex = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")
    return [email for email in emails if email_regex.match(email) and not is_example_domain(email)]