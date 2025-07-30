import re
from selenium.webdriver.common.by import By
from config.logging import setup_logging
import logging

EMAIL_REGEX = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")

def extract_emails_from_text(text):
    """
    Extract email addresses from a given text string using regex.
    
    Args:
        text (str): Text to search for email addresses.
    
    Returns:
        set: Set of unique email addresses found.
    """
    emails = set(EMAIL_REGEX.findall(text))
    logging.info(f"Extracted emails from text: {emails}")
    return emails

def extract_emails_from_page(driver, url):
    """
    Extract email addresses from a webpage, including visible text and mailto links.
    
    Args:
        driver (WebDriver): Selenium WebDriver instance.
        url (str): URL of the page to scrape.
    
    Returns:
        set: Set of unique email addresses found on the page.
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
                        emails.add(email)
        except Exception as e:
            logging.error(f"Error extracting mailto links: {e}")
        
        logging.info(f"Emails found on {url}: {emails}")
    except Exception as e:
        logging.error(f"Error scraping page {url}: {e}")
    
    return emails