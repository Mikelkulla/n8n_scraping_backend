import re
from selenium.webdriver.common.by import By
import logging

EMAIL_REGEX = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
EXAMPLE_DOMAINS = {"example.com", "example.org", "example.net", "test.com", "sample.com"}

def extract_emails_from_text(text):
    """Extracts email addresses from a string of text.

    This function uses a regular expression to find all substrings that match
    the format of an email address. It filters out emails from common example
    domains.

    Args:
        text (str): The text to search for email addresses.

    Returns:
        set[str]: A set of unique email addresses found in the text.
    """
    emails = set(EMAIL_REGEX.findall(text))
    # Filter out example domains
    filtered_emails = {email for email in emails if not any(email.lower().endswith("@" + domain) for domain in EXAMPLE_DOMAINS)}
    logging.info(f"Extracted emails from text: {filtered_emails}")
    return filtered_emails

def extract_emails_from_page(driver, url):
    """Extracts email addresses from a given web page.

    This function navigates to a URL using a Selenium WebDriver and scans the
    page for email addresses. It checks both the visible text content and any
    `mailto:` links.

    Args:
        driver: The Selenium WebDriver instance to use for browsing.
        url (str): The URL of the web page to scrape.

    Returns:
        set[str]: A set of unique email addresses found on the page.
    """
    logging.info(f"Scraping page for emails: {url}")
    emails = set()
    
    try:
        driver.get(url)
        driver.add_human_behavior()  # Add human-like behavior from driver_setup_for_scrape
        # 1. Extract from visible text
        try:
            body = driver.find_element(By.TAG_NAME, "body").text
            emails_from_text = extract_emails_from_text(body)
            emails.update(emails_from_text)
        except Exception as e:
            logging.error(f"Error getting page body text: {e}")
        
        # 2. Extract from mailto links
        try:
            mailto_links = driver.find_elements(By.XPATH, "//a[starts-with(@href, 'mailto:')]")
            for link in mailto_links:
                href = link.get_attribute("href")
                if href:
                    email = href.replace("mailto:", "").split("?")[0]
                    if EMAIL_REGEX.fullmatch(email):
                        # Only add if not an example domain
                        if not any(email.lower().endswith("@" + domain) for domain in EXAMPLE_DOMAINS):
                            emails.add(email)
        except Exception as e:
            logging.error(f"Error extracting mailto links: {e}")
        
        logging.info(f"Emails found on {url}: {emails}")
    except Exception as e:
        logging.error(f"Error scraping page {url}: {e}")
    
    return emails