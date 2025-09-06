import logging
import random
import subprocess
import time
import psutil
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.firefox.service import Service as FirefoxService
from fake_useragent import UserAgent
from backend.config import Config

class WebDriverManager:
    def __init__(self, browser="chrome", headless=False, use_tor=False, linkedin=False, chromedriver_path=Config.CHROMEDRIVER_PATH, tor_path=Config.TOR_EXECUTABLE):
        logging.info(f"Initializing WebDriverManager with browser={browser}, headless={headless}, use_tor={use_tor}, linkedin={linkedin}")
        self.driver = None
        self.tor_process = None
        self.browser = browser.lower()
        self.headless = headless
        self.use_tor = use_tor
        self.linkedin = linkedin
        self.chromedriver_path = chromedriver_path
        self.tor_path = tor_path
        self.setup_driver()

    def setup_driver(self):
        logging.info("Setting up WebDriver...")
        if self.use_tor:
            self.tor_process = self._start_tor()
            time.sleep(5)
            self.driver = self._setup_tor()
        elif self.linkedin:
            self.driver = self._setup_linkedin()
        else:
            self.driver = self._setup_standard()
        if self.driver:
            logging.info("WebDriver setup successful.")
        else:
            logging.error("WebDriver setup failed.")

    def _setup_standard(self):
        logging.info("Configuring standard WebDriver.")
        ua = UserAgent()
        user_agent = ua.random
        if self.browser == "firefox":
            options = webdriver.FirefoxOptions()
            options.set_preference("general.useragent.override", user_agent)
            if self.headless:
                options.add_argument("--headless")
            service = FirefoxService(self.chromedriver_path) if self.chromedriver_path else None
            driver = webdriver.Firefox(service=service, options=options)
        else:
            options = webdriver.ChromeOptions()
            options.add_argument(f"user-agent={user_agent}")
            options.add_argument("--start-maximized")
            if self.headless:
                options.add_argument("--headless=new")
            options.add_argument("--disable-blink-features=AutomationControlled")
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.add_experimental_option("useAutomationExtension", False)
            service = Service(self.chromedriver_path) if self.chromedriver_path else None
            driver = webdriver.Chrome(service=service, options=options)
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        self._add_human_behavior(driver)
        return driver

    def _setup_linkedin(self):
        logging.info("Configuring LinkedIn WebDriver.")
        ua = UserAgent()
        user_agent = ua.random
        if self.browser == "firefox":
            options = webdriver.FirefoxOptions()
            options.set_preference("general.useragent.override", user_agent)
            if self.headless:
                options.add_argument("--headless")
            service = FirefoxService(self.chromedriver_path) if self.chromedriver_path else None
            driver = webdriver.Firefox(service=service, options=options)
        else:
            options = webdriver.ChromeOptions()
            options.add_argument(f"user-agent={user_agent}")
            options.add_argument("--start-maximized")
            if self.headless:
                options.add_argument("--headless=new")
            user_data_dir = Config.CHROME_PROFILE_BASE_PATH
            profile_directory = "LinkedInProfile"
            options.add_argument(f"--user-data-dir={user_data_dir}")
            options.add_argument(f"--profile-directory={profile_directory}")
            options.add_argument("--disable-blink-features=AutomationControlled")
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.add_experimental_option("useAutomationExtension", False)
            service = Service(self.chromedriver_path) if self.chromedriver_path else None
            driver = webdriver.Chrome(service=service, options=options)
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        self._add_human_behavior(driver)
        return driver

    def _setup_tor(self):
        logging.info("Configuring WebDriver with Tor.")
        ua = UserAgent()
        user_agent = ua.random
        if self.browser == "firefox":
            options = webdriver.FirefoxOptions()
            options.set_preference("general.useragent.override", user_agent)
            options.set_preference("network.proxy.type", 1)
            options.set_preference("network.proxy.socks", "127.0.0.1")
            options.set_preference("network.proxy.socks_port", 9050)
            options.set_preference("network.proxy.socks_remote_dns", True)
            if self.headless:
                options.add_argument("--headless")
            service = FirefoxService(self.chromedriver_path) if self.chromedriver_path else None
            driver = webdriver.Firefox(service=service, options=options)
        else:
            options = webdriver.ChromeOptions()
            options.add_argument(f"user-agent={user_agent}")
            options.add_argument("--start-maximized")
            if self.headless:
                options.add_argument("--headless=new")
            options.add_argument("--proxy-server=socks5://127.0.0.1:9050")
            options.add_argument("--host-resolver-rules=MAP * ~NOTFOUND , EXCLUDE 127.0.0.1")
            options.add_argument("--disable-blink-features=AutomationControlled")
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.add_experimental_option("useAutomationExtension", False)
            service = Service(self.chromedriver_path) if self.chromedriver_path else None
            driver = webdriver.Chrome(service=service, options=options)
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        self._add_human_behavior(driver)
        return driver

    def _add_human_behavior(self, driver):
        def add_human_behavior():
            try:
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight * Math.random());")
                time.sleep(random.uniform(0.5, 2.0))
            except:
                pass
        driver.add_human_behavior = add_human_behavior

    def restart_driver(self):
        logging.info("Restarting WebDriver...")
        self.close()
        self.setup_driver()
        logging.info("WebDriver restarted.")

    def get_driver(self):
        return self.driver

    def close(self):
        logging.info("Closing WebDriver resources...")
        if self.driver:
            try:
                self.driver.quit()
                logging.info("WebDriver quit successfully.")
            except WebDriverException as e:
                logging.warning(f"Encountered an issue while closing WebDriver: {e}")
        if self.tor_process:
            self._stop_tor(self.tor_process)
        logging.info("WebDriver resources closed.")

    def _start_tor(self):
        logging.info("Starting Tor process...")
        try:
            process = subprocess.Popen(self.tor_path, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            logging.info("Tor process started successfully.")
            return process
        except Exception as e:
            logging.error(f"Error starting Tor: {e}")
            return None

    @staticmethod
    def _stop_tor(tor_process):
        logging.info("Stopping Tor process...")
        if tor_process:
            try:
                parent = psutil.Process(tor_process.pid)
                for child in parent.children(recursive=True):
                    child.kill()
                parent.kill()
                logging.info("Tor process stopped successfully.")
            except Exception as e:
                logging.error(f"Error stopping Tor: {e}")

    @staticmethod
    def kill_chrome_processes():
        for proc in psutil.process_iter(['name']):
            if proc.info['name'].lower() in ['chrome.exe', 'chromedriver.exe']:
                try:
                    proc.kill()
                    logging.info(f"Killed process {proc.info['name']} (PID: {proc.pid})")
                except psutil.NoSuchProcess:
                    pass
