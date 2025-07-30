import logging
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.firefox.service import Service as FirefoxService
from fake_useragent import UserAgent
import random
import time
import subprocess
import psutil
from backend.config import Config

def restart_driver_and_tor(driver, tor_process, use_tor=False, linkedin=False, chromedriver_path=Config.CHROMEDRIVER_PATH, tor_path=Config.TOR_EXECUTABLE, headless=False):
    """
    Restarts both the WebDriver and Tor process (if applicable) with proper cleanup and reinitialization.
    
    Parameters:
        driver (WebDriver): Current WebDriver instance to close.
        tor_process (subprocess.Popen): Current Tor process to stop (if use_tor is True).
        use_tor (bool): Whether to use Tor proxy for the WebDriver.
        linkedin (bool): Whether to use LinkedIn profile settings for the WebDriver.
        chromedriver_path (str): Path to chromedriver executable.
        tor_path (str): Path to tor.exe.
        headless (bool): Run WebDriver in headless mode.
    
    Returns:
        tuple: (new_driver, new_tor_process) where new_driver is the new WebDriver instance
               and new_tor_process is the new Tor process (or None if use_tor is False).
    """
    # --- Step 1: Close the existing WebDriver ---
    if driver is not None:
        try:
            logging.info("Attempting to close existing WebDriver...")
            driver.quit()
            time.sleep(2) # Adding a small delay to ensure resources are freed
            logging.info("WebDriver closed successfully.")
        except WebDriverException as e:
            logging.warning(f"Encountered an issue while closing WebDriver: {e}")
        except Exception as e: # Catch any other potential exceptions during quit
            logging.error(f"Unexpected error while closing WebDriver: {e}")
    
    # --- Step 2: Handle Tor Process (Stop if running, then restart if use_tor is True) ---
    new_tor_process = tor_process # Assume we might reuse the existing process if not using Tor or if it's None

    if use_tor:
        if tor_process is not None:
            logging.info("Attempting to stop existing Tor process...")
            stop_tor(tor_process)
            # Consider adding a check here to confirm Tor has stopped before proceeding
            time.sleep(5)  # Wait for Tor to shut down completely
            logging.info("Existing Tor process stopped.")
        else:
            logging.info("No existing Tor process to stop.")
            
        logging.info("Attempting to start a new Tor process...")
        new_tor_process = start_tor(tor_path)
        if new_tor_process:
            # Consider adding a check here to confirm Tor has started successfully
            time.sleep(5)  # Wait for new Tor process to initialize
            logging.info("New Tor process started successfully.")
        else:
            logging.error("Failed to start a new Tor process. WebDriver will be initialized without Tor.")
            # Decide if you want to proceed without Tor or return an error
            # For now, it will proceed and try to start WebDriver without Tor if setup_chrome_with_tor handles it,
            # or rely on the subsequent driver setup logic.
    else:
        # If not using Tor, ensure any existing Tor process is stopped if it was managed by this scope.
        # However, the current logic implies tor_process is only passed if use_tor was true for its creation.
        # If new_tor_process was from a previous run that used Tor, and now use_tor is False,
        # it should ideally be stopped.
        # For simplicity, we'll assume tor_process is managed consistently with use_tor.
        # If tor_process is not None here, it means it was passed in but use_tor is now False.
        # It's safer to stop it if it's running.
        if tor_process is not None:
            logging.info("use_tor is False, ensuring any existing managed Tor process is stopped.")
            stop_tor(tor_process)
            new_tor_process = None # Tor is not used, so no process to return
            logging.info("Existing Tor process stopped as use_tor is False.")

    # --- Step 3: Initialize new WebDriver ---
    new_driver = None
    try:
        logging.info(f"Initializing new WebDriver. use_tor: {use_tor}, linkedin: {linkedin}")
        if use_tor and new_tor_process: # Only use Tor setup if Tor actually started
            new_driver = setup_chrome_with_tor(chromedriver_path, headless=headless)
            logging.info("WebDriver initialized with Tor configuration.")
        elif linkedin:
            new_driver = setup_driver_linkedin_singin(chromedriver_path, headless=headless)
            logging.info("WebDriver initialized with LinkedIn profile configuration.")
        else:
            new_driver = setup_driver(chromedriver_path, headless=headless)
            logging.info("WebDriver initialized with standard configuration.")
        
        if new_driver:
            logging.info("New WebDriver initialized successfully.")
        else:
            # This case might occur if setup functions return None without raising an exception
            logging.error("WebDriver initialization returned None, but no exception was raised.")
            # new_tor_process is returned as is, which is correct.
            return None, new_tor_process
        
    except Exception as e:
        logging.error(f"Failed to initialize new WebDriver: {e}")
        # If driver initialization fails, we return None for the driver.
        # The new_tor_process (which could be None or a running process) is returned.
        # This allows the caller to manage the Tor process if needed, even if driver setup failed.
        return None, new_tor_process

    return new_driver, new_tor_process

def setup_driver(chromedriver_path=Config.CHROMEDRIVER_PATH, browser="chrome", headless=False):
    """
    Sets up a WebDriver (Chrome or Firefox) with anti-detection measures to appear less like a bot.
    
    Parameters:
        chromedriver_path (str, optional): Path to the WebDriver executable (Chrome or Gecko).
        browser (str, optional): Browser type ("chrome" or "firefox"). Defaults to "chrome".
        headless (bool, optional): Run in headless mode. Defaults to False.
    
    Returns:
        WebDriver: Configured WebDriver instance.
    """
    # Initialize a random user agent to mimic different browsers/devices
    ua = UserAgent()
    user_agent = ua.random

    if browser.lower() == "firefox":
        options = webdriver.FirefoxOptions()
        options.set_preference("general.useragent.override", user_agent)
        if headless:
            options.add_argument("--headless")
        if chromedriver_path:
            service = FirefoxService(chromedriver_path)
            driver = webdriver.Firefox(service=service, options=options)
        else:
            driver = webdriver.Firefox(options=options)
    else:  # Default to Chrome
        options = webdriver.ChromeOptions()
        options.add_argument(f"user-agent={user_agent}")
        options.add_argument("--start-maximized")
        if headless:
            options.add_argument("--headless=new")  # New headless mode for Chrome
        # Disable automation flags to avoid detection
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)
        if chromedriver_path:
            service = Service(chromedriver_path)
            driver = webdriver.Chrome(service=service, options=options)
        else:
            driver = webdriver.Chrome(options=options)

    # Remove 'webdriver' property to avoid detection
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

    # Optional: Add human-like behavior (random mouse movements or scrolling)
    def add_human_behavior():
        try:
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight * Math.random());")
            time.sleep(random.uniform(0.5, 2.0))  # Random delay to mimic human pause
        except:
            pass  # Ignore if page isn't loaded yet

    # Attach the human behavior function to the driver for optional use
    driver.add_human_behavior = add_human_behavior

    return driver

def setup_driver_linkedin_singin(chromedriver_path=Config.CHROMEDRIVER_PATH, browser="chrome", headless=False):
    """
    Sets up a WebDriver with LinkedIn Chrome profile for authentication.
    
    Parameters:
        chromedriver_path (str, optional): Path to the WebDriver executable.
        browser (str, optional): Browser type ("chrome" or "firefox"). Defaults to "chrome".
        headless (bool, optional): Run in headless mode. Defaults to False.
    
    Returns:
        WebDriver: Configured WebDriver instance.
    """
    ua = UserAgent()
    user_agent = ua.random

    if browser.lower() == "firefox":
        options = webdriver.FirefoxOptions()
        options.set_preference("general.useragent.override", user_agent)
        if headless:
            options.add_argument("--headless")
        if chromedriver_path:
            service = FirefoxService(chromedriver_path)
            driver = webdriver.Firefox(service=service, options=options)
        else:
            driver = webdriver.Firefox(options=options)
    else:  # Default to Chrome
        options = webdriver.ChromeOptions()
        options.add_argument(f"user-agent={UserAgent}") # Changed from options.add_argument(f"user-agent={user_agent}"), this produced login or mobile website view

        options.add_argument("--start-maximized")
        
        if headless:
            options.add_argument("--headless=new")
        
        # Add these two lines to reuse your Chrome profile
        # user_data_dir = Config.CHROME_PROFILE_PATH
        user_data_dir = Config.CHROME_PROFILE_BASE_PATH
        profile_directory = "LinkedInProfile"

        options.add_argument(f"--user-data-dir={user_data_dir}")
        options.add_argument(f"--profile-directory={profile_directory}")
        
        # Disable automation flags
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)
        
        if chromedriver_path:
            service = Service(chromedriver_path)
            driver = webdriver.Chrome(service=service, options=options)
        else:
            driver = webdriver.Chrome(options=options)

    # Remove 'webdriver' property to avoid detection
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

    # Optional: Add human-like behavior
    def add_human_behavior():
        try:
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight * Math.random());")
            time.sleep(random.uniform(0.5, 2.0))
        except:
            pass

    driver.add_human_behavior = add_human_behavior

    return driver

def start_tor(tor_path=Config.TOR_EXECUTABLE):
    """
    Starts the Tor process.
    
    Parameters:
        tor_path (str): Path to tor.exe.
    
    Returns:
        subprocess.Popen: Tor process.
    """
    try:
        return subprocess.Popen(tor_path, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception as e:
        print(f"Error starting Tor: {e}")
        return None

def stop_tor(tor_process):
    """
    Stops the Tor process and its children.
    
    Parameters:
        tor_process (subprocess.Popen): Tor process to stop.
    
    Returns:
        None
    """
    if tor_process:
        try:
            parent = psutil.Process(tor_process.pid)
            for child in parent.children(recursive=True):
                child.kill()
            parent.kill()
        except Exception as e:
            logging.error(f"Error stopping Tor: {e}")

def restart_tor(tor_process, tor_path=Config.TOR_EXECUTABLE):
    """
    Restarts the Tor process.
    
    Parameters:
        tor_process (subprocess.Popen): Tor process to restart.
        tor_path (str): Path to tor.exe.
    
    Returns:
        subprocess.Popen: New Tor process.
    """
    stop_tor(tor_process)
    time.sleep(5)  # Wait for Tor to shut down
    return start_tor(tor_path)

def setup_chrome_with_tor(chromedriver_path=Config.CHROMEDRIVER_PATH, headless=False):
    """
    Setup Chrome WebDriver routed through Tor SOCKS5 proxy (127.0.0.1:9050).
    Assumes Tor is running locally on port 9050.
    
    Parameters:
        chromedriver_path (str, optional): Path to chromedriver executable.
        headless (bool, optional): Run in headless mode. Defaults to False.
    
    Returns:
        WebDriver: Configured WebDriver instance.
    """
    options = webdriver.ChromeOptions()
    ua = UserAgent()
    user_agent = ua.random

    options.add_argument(f"user-agent={user_agent}")
    options.add_argument("--start-maximized")
    if headless:
        options.add_argument("--headless=new")

    # Use Tor SOCKS5 proxy
    options.add_argument("--proxy-server=socks5://127.0.0.1:9050")

    # Optional DNS leak protection (not perfect)
    options.add_argument("--host-resolver-rules=MAP * ~NOTFOUND , EXCLUDE 127.0.0.1")

    # Anti-detection options
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)

    if chromedriver_path:
        service = Service(chromedriver_path)
        driver = webdriver.Chrome(service=service, options=options)
    else:
        driver = webdriver.Chrome(options=options)

    # Remove 'webdriver' property to avoid detection
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

    def add_human_behavior():
        try:
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight * Math.random());")
            time.sleep(random.uniform(0.5, 2.0))
        except:
            pass

    driver.add_human_behavior = add_human_behavior

    return driver

def setup_firefox_with_tor(geckodriver_path=Config.GECKODRIVER_PATH, headless=False):
    """
    Setup Firefox WebDriver routed through Tor SOCKS5 proxy (127.0.0.1:9050).
    Assumes Tor is running locally on port 9050.
    
    Parameters:
        geckodriver_path (str, optional): Path to geckodriver executable.
        headless (bool, optional): Run in headless mode. Defaults to False.
    
    Returns:
        WebDriver: Configured WebDriver instance.
    """
    options = webdriver.FirefoxOptions()
    ua = UserAgent()
    user_agent = ua.random

    options.set_preference("general.useragent.override", user_agent)
    options.set_preference("network.proxy.type", 1)  # manual proxy configuration
    options.set_preference("network.proxy.socks", "127.0.0.1")
    options.set_preference("network.proxy.socks_port", 9050)
    options.set_preference("network.proxy.socks_remote_dns", True)  # route DNS via SOCKS proxy

    if headless:
        options.add_argument("--headless")

    if geckodriver_path:
        service = FirefoxService(geckodriver_path)
        driver = webdriver.Firefox(service=service, options=options)
    else:
        driver = webdriver.Firefox(options=options)

    # Remove 'webdriver' property to avoid detection
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

    def add_human_behavior():
        try:
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight * Math.random());")
            time.sleep(random.uniform(0.5, 2.0))
        except:
            pass

    driver.add_human_behavior = add_human_behavior

    return driver

def kill_chrome_processes():
    """Kill all Chrome processes that might be locking the user data directory."""
    for proc in psutil.process_iter(['name']):
        if proc.info['name'].lower() in ['chrome.exe', 'chromedriver.exe']:
            try:
                proc.kill()
                logging.info(f"Killed process {proc.info['name']} (PID: {proc.pid})")
            except psutil.NoSuchProcess:
                pass