import json
import os
import platform
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Config:
    """A central configuration class for the application.

    This class holds all the settings and paths required for the application to run.
    It includes API keys, file paths for logs and temporary data, driver
    configurations for Selenium, and other operational parameters. Settings can
    be overridden by environment variables.
    """
    GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", None)

    BASE_DIR = os.path.abspath(os.path.dirname(__file__))               # Base dir of the project (backend)
    ROOT_DIR = os.path.abspath(os.path.join(BASE_DIR, "..")) # , ".."   # Project root dir (n8n_scraping_backend)
    
    # Data and log paths
    LOG_PATH = os.path.join(BASE_DIR, "log_files")                      # Path to log files folder
    LOG_PREFIX = "Log_File"                                             # Log file prefix name (Currently logs are named: {Logs_prefix}_dd_mm_yyyy.log)
    MAX_BYTES = 100*1024*1024                                           # Maximum byte number per logfile before rotating it to a new file and appending time ("hh-mm-ss) in the end
    SCRIPTS_PATH = os.path.join(BASE_DIR, "scripts")                    # Path to the script folder
    TEMP_PATH = os.path.join(BASE_DIR, "temp")                          # Path to temp folder (There you can find some scraping results, scraping.db file etc.)
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")                          # Default log level (e.g., "DEBUG", "INFO", "WARNING")
    
    # Library-specific log levels
    _default_library_log_levels = {
        "urllib3": "WARNING", 
        "selenium": "WARNING",
        "bs4": "WARNING",              # for beautifulsoup4
        "fake_useragent": "WARNING",   # can log unnecessary warnings
        "flask": "WARNING",            # Flask app logs a lot at INFO
        "geopy": "WARNING",            # geopy can log retries/errors
        "pandas": "WARNING",           # pandas logs warnings often
        "psutil": "WARNING",           # suppress low-level system info logs
        "dotenv": "WARNING",           # for python-dotenv
        "requests": "WARNING",         # to silence urllib3-style logs
    }

    try:
        LIBRARY_LOG_LEVELS = json.loads(os.getenv("LIBRARY_LOG_LEVELS")) if os.getenv("LIBRARY_LOG_LEVELS") else _default_library_log_levels
    except json.JSONDecodeError:
        LIBRARY_LOG_LEVELS = _default_library_log_levels
    
    # Tor configuration
    TOR_BASE_PATH = os.path.join(ROOT_DIR, "config", "tor")
    OS_TYPE = platform.system().lower()
    if OS_TYPE == "windows":
        TOR_EXECUTABLE = os.path.join(TOR_BASE_PATH, "windows", "tor.exe")
        CHROMEDRIVER_PATH = os.path.join(ROOT_DIR, "config", "drivers", "chromedriver-win64", "chromedriver.exe")
        GECKODRIVER_PATH = os.path.join(ROOT_DIR, "config", "drivers", "geckodriver-win64", "geckodriver.exe")
    elif OS_TYPE == "linux":
        TOR_EXECUTABLE = os.path.join(TOR_BASE_PATH, "linux", "tor")
        CHROMEDRIVER_PATH = os.path.join(ROOT_DIR, "config", "drivers", "chromedriver-linux64", "chromedriver")
        GECKODRIVER_PATH = os.path.join(ROOT_DIR, "config", "drivers", "geckodriver-linux64", "geckodriver")
    elif OS_TYPE == "darwin":  # macOS
        TOR_EXECUTABLE = os.path.join(TOR_BASE_PATH, "macos", "tor")
        CHROMEDRIVER_PATH = os.path.join(ROOT_DIR, "config", "drivers", "chromedriver-mac64", "chromedriver")
        GECKODRIVER_PATH = os.path.join(ROOT_DIR, "config", "drivers", "geckodriver-mac64", "geckodriver")
    else:
        TOR_EXECUTABLE = None
        CHROMEDRIVER_PATH = None
        GECKODRIVER_PATH = None
    
    # LinkedIn Chrome profile configuration
    CHROME_PROFILE_BASE_PATH = os.path.join(ROOT_DIR, "config", "chrome_profiles", "Default")
    LINKEDIN_PROFILE_DIR = os.path.join(CHROME_PROFILE_BASE_PATH, "LinkedInProfile")
    CHROME_PROFILE_PATH = os.path.join(os.environ.get("USERPROFILE", ""), "AppData", "Local", "Google", "Chrome", "User Data", "Default")  # Fallback to system path
    
    # Environment variable overrides
    TOR_EXECUTABLE = os.getenv("TOR_EXECUTABLE", TOR_EXECUTABLE)
    LINKEDIN_PROFILE_DIR = os.getenv("LINKEDIN_PROFILE_DIR", LINKEDIN_PROFILE_DIR)
    CHROMEDRIVER_PATH = None # os.getenv("CHROMEDRIVER_PATH", CHROMEDRIVER_PATH)
    GECKODRIVER_PATH = None # os.getenv("GECKODRIVER_PATH", GECKODRIVER_PATH)
    
    # Flask settings
    SECRET_KEY = os.urandom(24)

    # Scraping settings
    MAX_THREADS = int(os.getenv("MAX_THREADS", 5))  # Max threads for concurrent scraping

    # Ensure directories exist
    @staticmethod
    def init_dirs():
        """Creates necessary directories for the application.

        This method ensures that all required directories for logging, temporary
        files, and browser profiles are created at startup.
        """
        for path in [
            Config.LOG_PATH,
            Config.TEMP_PATH,            
            Config.CHROME_PROFILE_BASE_PATH,

            os.path.join(Config.ROOT_DIR, "config", "drivers", "chromedriver-win64"),
            os.path.join(Config.ROOT_DIR, "config", "drivers", "geckodriver-win64")
        ]:
            os.makedirs(path, exist_ok=True)
    
    @staticmethod
    def verify_drivers():
        """Checks for the existence of required web driver executables.

        This method verifies that the paths for ChromeDriver, GeckoDriver, and the
        Tor executable point to existing files. It prints a warning if a driver
        is not found.
        """
        for driver_path in [Config.CHROMEDRIVER_PATH, Config.GECKODRIVER_PATH, Config.TOR_EXECUTABLE]:
            if driver_path and not os.path.exists(driver_path):
                print(f"Warning: Driver not found at {driver_path}")
            else:
                print(f"Driver found at {driver_path}")