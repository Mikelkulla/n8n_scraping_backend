import xml.etree.ElementTree as ET
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
import logging
import re

def fetch_content_with_driver(driver, url):
    """
    Fetch content of a URL using WebDriver to avoid 403 errors.
    
    Args:
        driver (WebDriver): Selenium WebDriver instance.
        url (str): URL to fetch.
    
    Returns:
        str: Content of the page, or empty string if fetch fails.
    """
    try:
        driver.get(url)
        driver.add_human_behavior()  # Add human-like behavior
        content = driver.page_source
        logging.info(f"Fetched content from: {url} (length: {len(content)})")
        return content
    except Exception as e:
        logging.error(f"Error fetching {url} with WebDriver: {e}")
        return ""

def get_robots_txt_urls(driver, base_url):
    """
    Fetch robots.txt and extract sitemap URLs using WebDriver.
    
    Args:
        driver (WebDriver): Selenium WebDriver instance.
        base_url (str): Base URL of the website.
    
    Returns:
        list: List of sitemap URLs found in robots.txt.
    """
    robots_url = urljoin(base_url, "/robots.txt")
    logging.info(f"Fetching robots.txt from: {robots_url}")
    
    content = fetch_content_with_driver(driver, robots_url)
    if not content:
        logging.info("robots.txt not found or inaccessible.")
        return []
    
    # Clean HTML tags if present
    if content.strip().startswith(('<!DOCTYPE', '<html', '<body')):
        soup = BeautifulSoup(content, 'html.parser')
        content = soup.get_text()
        logging.info(f"Cleaned HTML from robots.txt, new length: {len(content)}")
    
    # Split into lines and clean further
    lines = content.splitlines()
    sitemap_urls = []
    for line in lines:
        line = line.strip()
        if line.lower().startswith("sitemap:"):
            sitemap_url = line.split(":", 1)[1].strip()
            # Validate URL
            if sitemap_url.startswith(('http://', 'https://')) and not re.search(r'[<>\'"]', sitemap_url):
                logging.info(f"Found sitemap URL in robots.txt: {sitemap_url}")
                sitemap_urls.append(sitemap_url)
            else:
                logging.warning(f"Invalid sitemap URL in robots.txt: {sitemap_url}")
    
    logging.info(f"Total sitemap URLs found: {len(sitemap_urls)}")
    return sitemap_urls

def parse_embedded_xml_sitemap(content, sitemap_url, driver, depth, max_depth, visited_sitemaps, sitemap_limit=10):
    """
    Parse embedded XML content within HTML (e.g., inside <div id="webkit-xml-viewer-source-xml">).
    
    Args:
        content (str): HTML content containing embedded XML.
        sitemap_url (str): URL of the sitemap page.
        driver (WebDriver): Selenium WebDriver instance.
        depth (int): Current recursion depth.
        max_depth (int): Maximum recursion depth.
        visited_sitemaps (set): Set of sitemap URLs already processed.
        sitemap_limit (int): Maximum number of sitemaps to process per depth.
    
    Returns:
        list: List of page URLs extracted from the embedded XML.
    """
    try:
        soup = BeautifulSoup(content, 'html.parser')
        xml_div = soup.find('div', id='webkit-xml-viewer-source-xml')
        if not xml_div:
            logging.info(f"No embedded XML found in <div id='webkit-xml-viewer-source-xml'> for: {sitemap_url}")
            return []
        
        xml_content = str(xml_div)
        # Extract content between <div> tags, removing comments
        xml_content = re.sub(r'<!--.*?-->', '', xml_content, flags=re.DOTALL)
        xml_content = xml_content.replace('<div id="webkit-xml-viewer-source-xml">', '').replace('</div>', '').strip()
        
        # Parse as XML
        root = ET.fromstring(xml_content)
        namespace = ''
        if root.tag.startswith("{"):
            namespace = root.tag.split("}")[0] + "}"
        
        urls = []
        # Sitemap index (list of sitemaps)
        if root.tag == f"{namespace}sitemapindex":
            logging.info(f"Detected embedded XML sitemap index: {sitemap_url}")
            for sitemap in root.findall(f"{namespace}sitemap")[:sitemap_limit]:
                loc = sitemap.find(f"{namespace}loc")
                if loc is not None and loc.text and loc.text.strip():
                    child_url = loc.text.strip()
                    logging.info(f"Found child sitemap in embedded XML: {child_url}")
                    child_urls = get_urls_from_sitemap(driver, child_url, depth=depth+1, max_depth=max_depth, visited_sitemaps=visited_sitemaps, sitemap_limit=sitemap_limit)
                    urls.extend(child_urls)
                else:
                    logging.warning(f"Skipping invalid or empty <loc> in embedded sitemap: {sitemap_url}")
        
        # Regular sitemap (list of page URLs)
        elif root.tag == f"{namespace}urlset":
            logging.info(f"Detected embedded XML URL set: {sitemap_url}")
            for url_tag in root.findall(f"{namespace}url"):
                loc = url_tag.find(f"{namespace}loc")
                if loc is not None and loc.text and loc.text.strip():
                    page_url = loc.text.strip()
                    logging.info(f"Found page URL in embedded XML sitemap: {page_url}")
                    urls.append(page_url)
                else:
                    logging.warning(f"Skipping invalid or empty <loc> in embedded URL set: {sitemap_url}")
        
        logging.info(f"Extracted {len(urls)} page URLs from embedded XML sitemap: {sitemap_url}")
        return urls
    except ET.ParseError:
        logging.error(f"Failed to parse embedded XML for sitemap: {sitemap_url}")
        return []
    except Exception as e:
        logging.error(f"Error parsing embedded XML sitemap {sitemap_url}: {e}")
        return []

def get_urls_from_sitemap(driver, sitemap_url, depth=0, max_depth=2, visited_sitemaps=None, sitemap_limit=10):
    """
    Parse sitemap XML or HTML using WebDriver and extract URLs, supporting sitemap indexes.
    
    Args:
        driver (WebDriver): Selenium WebDriver instance.
        sitemap_url (str): URL of the sitemap.
        depth (int): Current recursion depth.
        max_depth (int): Maximum recursion depth.
        visited_sitemaps (set): Set of sitemap URLs already processed.
        sitemap_limit (int): Maximum number of sitemaps to process per depth.
    
    Returns:
        list: List of page URLs extracted from the sitemap.
    """
    if visited_sitemaps is None:
        visited_sitemaps = set()
    
    if depth > max_depth:
        logging.info(f"Reached max depth ({max_depth}) for sitemap: {sitemap_url}")
        return []
    
    if sitemap_url in visited_sitemaps:
        logging.info(f"Already processed sitemap, skipping: {sitemap_url}")
        return []
    
    visited_sitemaps.add(sitemap_url)
    logging.info(f"Processing sitemap: {sitemap_url} (depth: {depth})")
    
    try:
        content = fetch_content_with_driver(driver, sitemap_url)
        if not content or len(content.strip()) < 10:  # Arbitrary minimum length
            logging.info(f"Empty or invalid content for sitemap: {sitemap_url}")
            return []
        
        # Check if content is HTML (starts with <!DOCTYPE or <html)
        if content.strip().startswith(('<!DOCTYPE', '<html')):
            logging.info(f"Detected HTML content for sitemap: {sitemap_url}")
            # Check for embedded XML in <div id="webkit-xml-viewer-source-xml">
            if '<div id="webkit-xml-viewer-source-xml">' in content:
                logging.info(f"Found embedded XML in HTML for sitemap: {sitemap_url}")
                return parse_embedded_xml_sitemap(content, sitemap_url, driver, depth, max_depth, visited_sitemaps, sitemap_limit)
            return parse_html_sitemap(content, sitemap_url, driver, depth, max_depth, visited_sitemaps, sitemap_limit)
        
        # Strip XML comments to avoid parsing issues
        content = re.sub(r'<!--.*?-->', '', content, flags=re.DOTALL)
        
        # Validate XML content
        if not content.strip().startswith('<'):
            logging.error(f"Content does not appear to be valid XML for sitemap: {sitemap_url}")
            return parse_html_sitemap(content, sitemap_url, driver, depth, max_depth, visited_sitemaps)
        
        # Parse as XML
        root = ET.fromstring(content)
        namespace = ''
        if root.tag.startswith("{"):
            namespace = root.tag.split("}")[0] + "}"
        
        urls = []
        # Sitemap index (list of sitemaps)
        if root.tag == f"{namespace}sitemapindex":
            logging.info(f"Detected sitemap index: {sitemap_url}")
            for sitemap in root.findall(f"{namespace}sitemap")[:sitemap_limit]:
                loc = sitemap.find(f"{namespace}loc")
                if loc is not None and loc.text and loc.text.strip():
                    child_url = loc.text.strip()
                    logging.info(f"Found child sitemap in XML: {child_url}")
                    child_urls = get_urls_from_sitemap(driver, child_url, depth=depth+1, max_depth=max_depth, visited_sitemaps=visited_sitemaps, sitemap_limit=sitemap_limit)
                    urls.extend(child_urls)
                else:
                    logging.warning(f"Skipping invalid or empty <loc> in sitemap: {sitemap_url}")
        
        # Regular sitemap (list of page URLs)
        elif root.tag == f"{namespace}urlset":
            logging.info(f"Detected URL set: {sitemap_url}")
            for url_tag in root.findall(f"{namespace}url"):
                loc = url_tag.find(f"{namespace}loc")
                if loc is not None and loc.text and loc.text.strip():
                    page_url = loc.text.strip()
                    logging.debug(f"Found page URL in XML sitemap: {page_url}")
                    urls.append(page_url)
                else:
                    logging.warning(f"Skipping invalid or empty <loc> in URL set: {sitemap_url}")
        
        logging.info(f"Extracted {len(urls)} page URLs from XML sitemap: {sitemap_url}")
        return urls
    except ET.ParseError:
        logging.error(f"Failed to parse sitemap as XML, attempting HTML parsing: {sitemap_url}")
        return parse_html_sitemap(content, sitemap_url, driver, depth, max_depth, visited_sitemaps, sitemap_limit)
    except Exception as e:
        logging.error(f"Error parsing sitemap {sitemap_url}: {e}")
        return []

def parse_html_sitemap(content, sitemap_url, driver, depth, max_depth, visited_sitemaps, sitemap_limit=10):
    """
    Parse HTML sitemap page to extract sitemap URLs and page URLs.
    
    Args:
        content (str): HTML content of the sitemap page.
        sitemap_url (str): URL of the sitemap page.
        driver (WebDriver): Selenium WebDriver instance.
        depth (int): Current recursion depth.
        max_depth (int): Maximum recursion depth.
        visited_sitemaps (set): Set of sitemap URLs already processed.
        sitemap_limit (int): Maximum number of sitemaps to process per depth.
    
    Returns:
        list: List of page URLs extracted from the HTML sitemap.
    """
    try:
        soup = BeautifulSoup(content, 'html.parser')
        sitemap_urls = []
        page_urls = []
        
        # Find all tables in the HTML
        tables = soup.find_all('table')
        selected_table = None
        
        # Try specific known structures first (Yoast or Auctollo)
        for table in tables:
            # Check for Yoast-style table with id="sitemap"
            if table.get('id') == 'sitemap':
                selected_table = table
                logging.info(f"Found Yoast-style table with id='sitemap' for sitemap: {sitemap_url}")
                break
            # Check for Auctollo/WordPress-style table inside <div id="content">
            if table.find_parent('div', id='content'):
                selected_table = table
                logging.info(f"Found Auctollo-style table in <div id='content'> for sitemap: {sitemap_url}")
                break
        
        # Fallback to any table with valid sitemap or page URLs
        if not selected_table:
            for table in tables:
                # Check if table contains valid sitemap or page URLs
                links = table.find_all('a', href=True)
                if any(link['href'].endswith('.xml') or urlparse(link['href']).path for link in links):
                    selected_table = table
                    logging.info(f"Found generic table with valid URLs for sitemap: {sitemap_url}")
                    break
        
        if selected_table:
            for row in selected_table.find('tbody').find_all('tr') if selected_table.find('tbody') else selected_table.find_all('tr'):
                link = row.find('a')
                if link and link.get('href'):
                    url = link.get('href')
                    # Ensure URL is absolute
                    url = urljoin(sitemap_url, url)
                    if url.endswith('.xml'):
                        sitemap_urls.append(url)
                        logging.info(f"Found sitemap URL in HTML: {url}")
                    else:
                        page_urls.append(url)
                        logging.info(f"Found page URL in HTML: {url}")
        else:
            logging.warning(f"No suitable table found in HTML sitemap: {sitemap_url}")
        
        # Recursively process sitemap URLs
        urls = page_urls  # Start with page URLs found in HTML
        for url in sitemap_urls[:sitemap_limit]:
            logging.info(f"Processing HTML-derived sitemap: {url}")
            child_urls = get_urls_from_sitemap(driver, url, depth=depth+1, max_depth=max_depth, visited_sitemaps=visited_sitemaps, sitemap_limit=sitemap_limit)
            urls.extend(child_urls)
        
        logging.info(f"Extracted {len(urls)} page URLs from HTML sitemap: {sitemap_url} (sitemaps: {len(sitemap_urls)}, pages: {len(page_urls)})")
        return urls
    except Exception as e:
        logging.error(f"Error parsing HTML sitemap {sitemap_url}: {e}")
        return []