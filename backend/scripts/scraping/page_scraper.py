import logging

def scrape_page(driver, url, max_pages, visited_urls, all_emails):
    """
    Scrape a single page for emails, respecting max_pages and visited_urls.
    
    Args:
        driver (WebDriver): Selenium WebDriver instance.
        url (str): URL to scrape.
        max_pages (int): Maximum number of pages to scrape.
        visited_urls (set): Set of URLs already visited.
        all_emails (set): Set to store all collected emails.
    
    Returns:
        bool: True if page was scraped, False if skipped or error occurred.
    """
    from .email_extractor import extract_emails_from_page
    
    if len(visited_urls) >= max_pages:
        logging.info(f"Reached max pages limit ({max_pages}), stopping.")
        return False
    
    if url in visited_urls:
        logging.info(f"Already visited URL, skipping: {url}")
        return False
    
    logging.info(f"Visiting URL: {url}")
    try:
        emails = extract_emails_from_page(driver, url)
        all_emails.update(emails)
        visited_urls.add(url)
        logging.info(f"Total unique emails collected so far: {len(all_emails)}")
        return True
    except Exception as e:
        logging.error(f"Error scraping {url}: {e}")
        return False