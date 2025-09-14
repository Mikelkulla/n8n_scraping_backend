import logging
from .email_extractor import extract_emails_from_page

logger = logging.getLogger(__name__)

def scrape_page(driver, url):
    """Scrapes a single web page to find email addresses.

    This function serves as a wrapper around `extract_emails_from_page`,
    handling the process of visiting a URL and extracting emails from it.

    Args:
        driver: The Selenium WebDriver instance to use.
        url (str): The URL of the page to scrape.

    Returns:
        set[str]: A set of unique email addresses found on the page. Returns an
        empty set if an error occurs.
    """
    logger.info(f"Visiting URL: {url}")
    try:
        emails = extract_emails_from_page(driver, url)
        return emails
    except Exception as e:
        logger.error(f"Error scraping {url}: {e}")
        return set()