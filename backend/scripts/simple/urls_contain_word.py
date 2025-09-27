from backend.scripts.scraping.scrape_for_email import EmailScraper
from config.logging import setup_logging
url_to_scrape = "https://www.cdata.com"
contain_word = 'mcp'
scraper = EmailScraper(job_id="123123123123123123", step_id="scrape_website", base_url=url_to_scrape, max_pages=100, use_tor=False, headless=True, sitemap_limit=30)
setup_logging(log_prefix="CData_Scrape", log_level="DEBUG")

try: 
    scraper._setup_driver()
    scraper._discover_urls()
    scraper._filter_and_sort_urls()
    mcp_links = [url for url in scraper.urls_to_visit if contain_word in url]
    with open(r"C:\Users\MikelKulla\Mikel Documents\AI Automation Agency\n8n_scraping_backend\mcp_links.txt", "w") as file:
        file.write("\n".join(mcp_links))
    with open(r"C:\Users\MikelKulla\Mikel Documents\AI Automation Agency\n8n_scraping_backend\mcp_links2.txt", "w") as file:
        file.write("\n".join(scraper.urls_to_visit))    
except:
    pass
finally:
    scraper._cleanup()