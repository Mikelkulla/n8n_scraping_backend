import logging

def scrape_page(driver, url):
    """
    Scrape a single page for emails.
    
    Args:
        driver (WebDriver): Selenium WebDriver instance.
        url (str): URL to scrape.
    
    Returns:
        set: A set of emails found on the page.
    """
    from .email_extractor import extract_emails_from_page
    
    logging.info(f"Visiting URL: {url}")
    try:
        emails = extract_emails_from_page(driver, url)
        return emails
    except Exception as e:
        logging.error(f"Error scraping {url}: {e}")
        return set()