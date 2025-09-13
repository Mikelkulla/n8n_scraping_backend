from urllib.parse import urljoin, urlparse
from .sitemap_parser import get_robots_txt_urls, get_urls_from_sitemap
from .page_scraper import scrape_page
from ..selenium.webdriver_manager import WebDriverManager
from config.job_functions import write_progress, check_stop_signal
from backend.config import Config
import logging
import concurrent.futures
import threading
from itertools import repeat

def sort_urls_by_email_likelihood(urls):
    """Sorts a list of URLs based on their likelihood of containing contact information.

    This function scores URLs based on the presence of keywords like 'contact'
    or 'about', and also considers the URL's length. Shorter URLs and those
    with relevant keywords are ranked higher.

    Args:
        urls (list[str]): A list of URLs to be sorted.

    Returns:
        list[str]: The list of URLs sorted in descending order of likelihood.
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
    """Orchestrates the process of scraping a website for email addresses.

    This class manages the entire lifecycle of an email scraping job, including
    setting up the web driver, discovering URLs through sitemaps, filtering and
    sorting them, scraping pages concurrently, and handling cleanup.
    """
    def __init__(self, job_id, step_id, base_url, max_pages=10, use_tor=False, headless=False, sitemap_limit=10, max_threads=Config.MAX_THREADS):
        """Initializes the EmailScraper instance.

        Args:
            job_id (str): The unique identifier for the scraping job.
            step_id (str): The identifier for the scraping step.
            base_url (str): The starting URL for the website to be scraped.
            max_pages (int, optional): The maximum number of pages to scrape.
                Defaults to 10.
            use_tor (bool, optional): If True, use the Tor network for scraping.
                Defaults to False.
            headless (bool, optional): If True, run the browser in headless mode.
                Defaults to False.
            sitemap_limit (int, optional): The max number of sitemaps to process.
                Defaults to 10.
            max_threads (int, optional): The max number of concurrent threads to use.
                Defaults to `Config.MAX_THREADS`.
        """
        self.job_id = job_id
        self.step_id = step_id
        self.base_url = base_url
        self.max_pages = max_pages
        self.use_tor = use_tor
        self.headless = headless
        self.sitemap_limit = sitemap_limit
        self.max_threads = max_threads
        self.manager = None
        self.driver = None
        self.all_emails = set()
        self.visited_urls = set()
        self.urls_to_visit = [self.base_url]
        self.total_urls = 0
        self.lock = threading.Lock()
        self.progress_counter = 0

    def _setup_driver(self):
        """Initializes the Selenium WebDriver.

        Raises:
            RuntimeError: If the WebDriver fails to initialize.
        """
        logging.info(f"Starting Chrome WebDriver for job {self.job_id}...")
        self.manager = WebDriverManager(use_tor=self.use_tor, headless=self.headless)
        self.driver = self.manager.get_driver()
        if not self.driver:
            logging.error(f"Failed to initialize WebDriver for job {self.job_id}.")
            raise RuntimeError("Failed to initialize WebDriver")

    def _discover_urls(self):
        """Discovers URLs to scrape from the website's robots.txt and sitemaps."""
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
        """Filters discovered URLs to the base domain and sorts them by likelihood."""
        def get_base_domain(netloc):
            return netloc.lower().removeprefix("www.")

        base_domain = get_base_domain(urlparse(self.base_url).netloc)
        logging.info(f"Base domain for filtering URLs: {base_domain}")

        filtered_urls = [url for url in self.urls_to_visit if get_base_domain(urlparse(url).netloc) == base_domain]
        
        self.urls_to_visit = sort_urls_by_email_likelihood(filtered_urls)
        self.total_urls = min(len(self.urls_to_visit), self.max_pages)
        logging.info(f"Total URLs to visit after filtering and sorting for job {self.job_id}: {self.total_urls}")

    def _scrape_worker(self, url):
        """The target function for each scraping thread.

        This function scrapes a single URL for emails. It manages its own WebDriver
        instance and updates shared state (visited URLs, found emails) using a lock.

        Args:
            url (str): The URL to be scraped by the worker.
        """
        if check_stop_signal(self.step_id):
            return
        
        with self.lock:
            if url in self.visited_urls or len(self.visited_urls) >= self.max_pages:
                return

        thread_manager = WebDriverManager(use_tor=self.use_tor, headless=self.headless)
        driver = thread_manager.get_driver()
        if not driver:
            logging.error(f"Failed to get driver for thread on job {self.job_id}")
            return

        try:
            emails = scrape_page(driver, url)
            with self.lock:
                if len(self.visited_urls) < self.max_pages:
                    self.visited_urls.add(url)
                    self.all_emails.update(emails)
                    self.progress_counter += 1
                    logging.info(f"Scraped page {self.progress_counter}/{self.total_urls} for job {self.job_id}: {url}")
                    write_progress(self.job_id, self.step_id, self.base_url, self.max_pages, self.use_tor, self.headless, status="running", current_row=self.progress_counter, total_rows=self.total_urls)
        finally:
            thread_manager.close()

    def _scrape_pages(self):
        """Manages the concurrent scraping of URLs using a thread pool."""
        write_progress(self.job_id, self.step_id, self.base_url, self.max_pages, self.use_tor, self.headless, status="running", current_row=0, total_rows=self.total_urls)

        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_threads) as executor:
            # Use list to ensure all futures are created before waiting
            futures = list(executor.map(self._scrape_worker, self.urls_to_visit[:self.max_pages]))

        if not check_stop_signal(self.step_id):
            write_progress(self.job_id, self.step_id, self.base_url, self.max_pages, self.use_tor, self.headless, status="completed", total_rows=self.total_urls)

    def _cleanup(self):
        """Closes the main WebDriver instance."""
        if self.manager:
            logging.info(f"Closing WebDriver for job {self.job_id}...")
            self.manager.close()

    def run(self):
        """Executes the complete email scraping process.

        This method orchestrates the entire scraping workflow, from setup to
        cleanup, and returns the list of found emails.

        Returns:
            list[str]: A list of unique email addresses found during the scrape.
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

def scrape_emails(job_id, step_id, base_url, max_pages=10, use_tor=False, headless=False, sitemap_limit=10, max_threads=Config.MAX_THREADS):
    """A convenience function to initiate an email scraping job.

    This function creates an instance of the `EmailScraper` class and calls its
    `run` method, providing a simple interface to start a scraping task.

    Args:
        job_id (str): The unique identifier for the scraping job.
        step_id (str): The identifier for the scraping step.
        base_url (str): The starting URL for the website to be scraped.
        max_pages (int, optional): The maximum number of pages to scrape.
            Defaults to 10.
        use_tor (bool, optional): If True, use the Tor network. Defaults to False.
        headless (bool, optional): If True, run in headless mode. Defaults to False.
        sitemap_limit (int, optional): The max number of sitemaps to process.
            Defaults to 10.
        max_threads (int, optional): The max number of concurrent threads.
            Defaults to `Config.MAX_THREADS`.

    Returns:
        list[str]: A list of unique email addresses found.
    """
    scraper = EmailScraper(job_id, step_id, base_url, max_pages, use_tor, headless, sitemap_limit, max_threads)
    return scraper.run()