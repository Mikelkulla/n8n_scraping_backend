from urllib.parse import urljoin, urlparse
from .sitemap_parser import get_robots_txt_urls, get_urls_from_sitemap
from .page_scraper import scrape_page
from ..selenium.webdriver_manager import WebDriverManager
from config.job_functions import write_progress, check_stop_signal
import logging

def sort_urls_by_email_likelihood(urls):
    """
    Sort URLs by likelihood of containing emails based on keywords and length.
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

class EmailScraper:
    """
    A class to orchestrate email scraping from a website.
    """
    def __init__(self, job_id, step_id, base_url, max_pages=10, use_tor=False, headless=False, sitemap_limit=10):
        self.job_id = job_id
        self.step_id = step_id
        self.base_url = base_url
        self.max_pages = max_pages
        self.use_tor = use_tor
        self.headless = headless
        self.sitemap_limit = sitemap_limit
        self.manager = None
        self.driver = None
        self.all_emails = set()
        self.visited_urls = set()
        self.urls_to_visit = [self.base_url]
        self.total_urls = 0

    def _setup_driver(self):
        """Initializes the Selenium WebDriver."""
        logging.info(f"Starting Chrome WebDriver for job {self.job_id}...")
        self.manager = WebDriverManager(use_tor=self.use_tor, headless=self.headless)
        self.driver = self.manager.get_driver()
        if not self.driver:
            logging.error(f"Failed to initialize WebDriver for job {self.job_id}.")
            raise RuntimeError("Failed to initialize WebDriver")

    def _discover_urls(self):
        """Discovers URLs from robots.txt and sitemaps."""
        logging.info(f"Starting URL for job {self.job_id}: {self.base_url}")
        sitemap_urls = get_robots_txt_urls(self.driver, self.base_url)
        sitemap_urls.extend([
            urljoin(self.base_url, "/sitemap_index.xml"),
            urljoin(self.base_url, "/sitemap.xml"),
            urljoin(self.base_url, "/sitemapindex.xml")
        ])
        logging.info(f"Sitemap URLs discovered for job {self.job_id}: {sitemap_urls}")

        for sitemap_url in sitemap_urls:
            urls_from_sitemap = get_urls_from_sitemap(self.driver, sitemap_url, sitemap_limit=self.sitemap_limit)
            logging.info(f"Discovered {len(urls_from_sitemap)} URLs from sitemap {sitemap_url}")
            self.urls_to_visit.extend(urls_from_sitemap)

    def _filter_and_sort_urls(self):
        """Filters URLs to the base domain and sorts them by email likelihood."""
        def get_base_domain(netloc):
            return netloc.lower().removeprefix("www.")

        base_domain = get_base_domain(urlparse(self.base_url).netloc)
        logging.info(f"Base domain for filtering URLs: {base_domain}")

        filtered_urls = [url for url in self.urls_to_visit if get_base_domain(urlparse(url).netloc) == base_domain]
        
        self.urls_to_visit = sort_urls_by_email_likelihood(filtered_urls)
        self.total_urls = min(len(self.urls_to_visit), self.max_pages)
        logging.info(f"Total URLs to visit after filtering and sorting for job {self.job_id}: {self.total_urls}")

    def _scrape_pages(self):
        """Iterates through URLs and scrapes them for emails."""
        write_progress(self.job_id, self.step_id, self.base_url, self.max_pages, self.use_tor, self.headless, status="running", current_row=0, total_rows=self.total_urls)

        for i, url in enumerate(self.urls_to_visit[:self.max_pages], 1):
            if check_stop_signal(self.step_id):
                logging.info(f"Stop signal detected for job {self.job_id}")
                write_progress(self.job_id, self.step_id, self.base_url, self.max_pages, self.use_tor, self.headless, status="stopped", stop_call=True, current_row=i-1, total_rows=self.total_urls)
                break
            
            scrape_page(self.driver, url, self.max_pages, self.visited_urls, self.all_emails)
            logging.info(f"Scraped page {i}/{self.total_urls} for job {self.job_id}: {url}")

            write_progress(self.job_id, self.step_id, self.base_url, self.max_pages, self.use_tor, self.headless, status="running", current_row=i, total_rows=self.total_urls)
        
        if not check_stop_signal(self.step_id):
            write_progress(self.job_id, self.step_id, self.base_url, self.max_pages, self.use_tor, self.headless, status="completed", total_rows=self.total_urls)

    def _cleanup(self):
        """Closes the WebDriver."""
        if self.manager:
            logging.info(f"Closing WebDriver for job {self.job_id}...")
            self.manager.close()

    def run(self):
        """
        Executes the entire email scraping process.
        """
        try:
            self._setup_driver()
            self._discover_urls()
            self._filter_and_sort_urls()
            self._scrape_pages()
            
            logging.info(f"Finished scraping for job {self.job_id}. Total unique emails found: {len(self.all_emails)}")
            logging.info(f"Emails: {self.all_emails}")
            return list(self.all_emails)
        except Exception as e:
            logging.error(f"Scraping failed for job {self.job_id}: {e}")
            write_progress(self.job_id, self.step_id, self.base_url, self.max_pages, self.use_tor, self.headless, status="failed", error_message=str(e), total_rows=self.total_urls)
            return list(self.all_emails)
        finally:
            self._cleanup()

def scrape_emails(job_id, step_id, base_url, max_pages=10, use_tor=False, headless=False, sitemap_limit=10):
    """
    Orchestrates email scraping by using the EmailScraper class.
    """
    scraper = EmailScraper(job_id, step_id, base_url, max_pages, use_tor, headless, sitemap_limit)
    return scraper.run()