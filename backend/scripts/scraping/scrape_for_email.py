from urllib.parse import urljoin, urlparse
from .sitemap_parser import get_robots_txt_urls, get_urls_from_sitemap
from .page_scraper import scrape_page
from ..selenium.driver_setup_for_scrape import setup_driver, setup_chrome_with_tor
from config.job_functions import write_progress, check_stop_signal
import logging

def sort_urls_by_email_likelihood(urls):
    """
    Sort URLs by likelihood of containing emails based on keywords and length.
    
    Args:
        urls (list): List of URLs to sort.
    
    Returns:
        list: Deduplicated URLs sorted by email likelihood (highest first).
    """
    # Keywords indicating high email likelihood
    email_keywords = [
        '/contact', '/contact-us', '/contactus', '/contacts',
        '/whoweare', '/who-we-are', '/who_we_are',
        '/aboutus', '/about', '/about-us', '/about_us'
    ]
    
    def get_url_score(url):
        """
        Calculate a score for a URL based on keywords and length.
        Higher score = higher email likelihood.
        """
        score = 0
        # Boost score for keyword matches
        for keyword in email_keywords:
            if keyword.lower() in url.lower():
                score += 10  # Significant boost for relevant keywords
                logging.debug(f"URL {url} matched keyword {keyword}, score += 10")
        
        # Slight boost for shorter URLs (inversely proportional to length)
        length = len(url)
        length_score = max(0, 100 - length) / 10  # Normalize to 0-10 range
        score += length_score
        logging.debug(f"URL {url} length {length}, length_score: {length_score}")
        
        return score
    
    # Remove duplicates while preserving order
    unique_urls = list(dict.fromkeys(urls))
    logging.info(f"Deduplicated URLs: {len(unique_urls)} from {len(urls)}")
    
    # Sort URLs by score (descending) and original length (ascending) as tiebreaker
    sorted_urls = sorted(
        unique_urls,
        key=lambda u: (-get_url_score(u), len(u))
    )
    
    logging.info(f"Sorted {len(sorted_urls)} URLs by email likelihood")
    return sorted_urls

def scrape_emails(job_id, step_id, base_url, max_pages=10, use_tor=False, headless=False):
    """
    Orchestrate email scraping from a website using sitemaps and WebDriver.
    
    Args:
        job_id (str): Unique identifier for the job (e.g., UUID).
        base_url (str): Base URL of the website to scrape.
        max_pages (int): Maximum number of pages to scrape.
        use_tor (bool): Whether to use Tor for WebDriver setup.
        headless (bool): Whether to run WebDriver in headless mode.
    
    Returns:
        list: List of unique email addresses found.
    """
    # Initialize WebDriver
    logging.info(f"Starting Chrome WebDriver for job {job_id}...")
    driver = setup_chrome_with_tor(headless=headless) if use_tor else setup_driver(headless=headless)
    if not driver:
        logging.error(f"Failed to initialize WebDriver for job {job_id}.")
        write_progress(job_id, step_id, base_url, max_pages, use_tor, headless, status="failed", error_message="Failed to initialize WebDriver", current_row=0, total_rows=max_pages)
        return []
    
    all_emails = set()
    visited_urls = set()
    urls_to_visit = [base_url]
    
    logging.info(f"Starting URL for job {job_id}: {base_url}")
    
    # Discover sitemap URLs from robots.txt
    sitemap_urls = get_robots_txt_urls(driver, base_url)
    sitemap_urls.append(urljoin(base_url, "/sitemap_index.xml"))
    sitemap_urls.append(urljoin(base_url, "/sitemap.xml"))
    sitemap_urls.append(urljoin(base_url, "/sitemapindex.xml"))
    logging.info(f"Sitemap URLs discovered for job {job_id}: {sitemap_urls}")
    
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
    
    # Sort URLs by email likelihood
    unique_sorted_urls = sort_urls_by_email_likelihood(filtered_urls)
    total_urls = min(len(unique_sorted_urls), max_pages)
    logging.info(f"Total URLs to visit after filtering and sorting for job {job_id}: {total_urls}")
    
    # Update initial progress with total_urls
    write_progress(job_id, step_id, base_url, max_pages, use_tor, headless, status="running", current_row=0, total_rows=total_urls)
    
    try:
        for i, url in enumerate(unique_sorted_urls[:max_pages], 1):
            if check_stop_signal(step_id):
                logging.info(f"Stop signal detected for job {job_id}")
                write_progress(job_id, step_id, base_url, max_pages, use_tor, headless, status="stopped", stop_call=True, current_row=i-1, total_rows=total_urls)
                break
            
            scrape_page(driver, url, max_pages, visited_urls, all_emails)
            logging.info(f"Scraped page {i}/{total_urls} for job {job_id}: {url}")

            # Update progress after each page
            write_progress(job_id, step_id, base_url, max_pages, use_tor, headless, status="running", current_row=i, total_rows=total_urls)
        
        if not check_stop_signal(step_id):
            # Update progress to completed if not stopped
            write_progress(job_id, step_id, base_url, max_pages, use_tor, headless, status="completed", total_rows=total_urls)
        
        logging.info(f"Finished scraping for job {job_id}. Total unique emails found: {len(all_emails)}")
        logging.info(f"Emails: {all_emails}")
        return list(all_emails)
    
    except Exception as e:
        logging.error(f"Scraping failed for job {job_id}: {e}")
        write_progress(job_id, step_id, base_url, max_pages, use_tor, headless, status="failed", error_message=str(e), total_rows=total_urls)
        return list(all_emails)
    
    finally:
        logging.info(f"Closing WebDriver for job {job_id}...")
        driver.quit()