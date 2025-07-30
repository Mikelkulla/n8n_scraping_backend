from urllib.parse import urlparse
from .sitemap_parser import get_robots_txt_urls, get_urls_from_sitemap
from .page_scraper import scrape_page
from ..selenium.driver_setup_for_scrape import setup_driver, setup_chrome_with_tor
from config.logging import setup_logging
import logging

def scrape_emails(base_url, max_pages=10, use_tor=False, headless=False):
    """
    Orchestrate email scraping from a website using sitemaps and WebDriver.
    
    Args:
        base_url (str): Base URL of the website to scrape.
        max_pages (int): Maximum number of pages to scrape.
        use_tor (bool): Whether to use Tor for WebDriver setup.
        headless (bool): Whether to run WebDriver in headless mode.
    
    Returns:
        list: List of unique email addresses found.
    """
    # # Initialize logging
    # setup_logging()
    
    # Initialize WebDriver
    logging.info("Starting Chrome WebDriver...")
    driver = setup_chrome_with_tor(headless=headless) if use_tor else setup_driver(headless=headless)
    if not driver:
        logging.error("Failed to initialize WebDriver.")
        return []
    
    all_emails = set()
    visited_urls = set()
    urls_to_visit = [base_url]
    
    logging.info(f"Starting URL: {base_url}")
    
    # Discover sitemap URLs from robots.txt
    sitemap_urls = get_robots_txt_urls(driver, base_url)
    sitemap_urls.append(f"{base_url}/sitemap_index.xml")
    logging.info(f"Sitemap URLs discovered: {sitemap_urls}")
    
    # Discover URLs from sitemap files
    for sitemap_url in sitemap_urls:
        urls_from_sitemap = get_urls_from_sitemap(driver, sitemap_url)
        logging.info(f"URLs from sitemap {sitemap_url}: {urls_from_sitemap}")
        urls_to_visit.extend(urls_from_sitemap)
    
    # Normalize domain
    def get_base_domain(netloc):
        return netloc.lower().removeprefix("www.")
    
    base_domain = get_base_domain(urlparse(base_url).netloc)
    logging.info(f"Base domain for filtering URLs: {base_domain}")
    
    # Deduplicate and filter to base domain only
    filtered_urls = []
    for url in urls_to_visit:
        parsed = urlparse(url)
        if get_base_domain(parsed.netloc) == base_domain:
            filtered_urls.append(url)
        else:
            logging.info(f"Ignoring URL from different domain: {url}")
    
    # Remove duplicates and sort by character length (shortest first)
    unique_sorted_urls = sorted(
        list(dict.fromkeys(filtered_urls)),
        key=lambda u: len(u)
    )
    
    logging.info(f"Total URLs to visit after filtering and sorting: {len(unique_sorted_urls)}")
    
    try:
        for url in unique_sorted_urls:
            scrape_page(driver, url, max_pages, visited_urls, all_emails)
        
        logging.info(f"Finished scraping. Total unique emails found: {len(all_emails)}")
        logging.info(f"{all_emails}")
        return list(all_emails)
    
    finally:
        logging.info("Closing WebDriver...")
        driver.quit()