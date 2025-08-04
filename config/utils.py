# config/utils.py
import pandas as pd
import os
import logging

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
    
# FUNCTION TO EXTRACT BASE URL
from urllib.parse import urlparse
def is_non_business_domain(domain):
    """
    Check if the domain is a common non-business website.
    
    Args:
        domain (str): Domain to check (e.g., 'facebook.com')
    
    Returns:
        bool: True if domain is a non-business website, False otherwise
    """
    non_business_domains = [
        'airbnb.co.uk',
        'airbnb.co.za',
        'airbnb.com',
        'airbnb.mx',
        'airbnb.net',
        'airbnbmail.com',
        'booking.com',
        'facebook.com',
        'instagram.com',
        'jscache.com',
        'linkedin.com',
        'muscache.com',
        'pinterest.com',
        'snapchat.com',
        'tacdn.com',
        'tamgrt.com',
        'tiktok.com',
        'tripadvisor.cn',
        'tripadvisor.co.uk',
        'tripadvisor.com',
        'tripadvisor.de',
        'twitter.com',
        'x.com',
        'youtube.com',
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

print(extract_base_url('https://www.wyndhamhotels.com/laquinta/new-york-city-new-york/la-quinta-new-york-city-central-park/overview?CID=LC:6ysy27krtpcrqev:52979&iata=00093796'))