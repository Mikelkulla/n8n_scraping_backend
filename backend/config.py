import os
import platform

class Config:
    GOOGLE_API_KEY = 'AIzaSyDQNxV1M9fAvkLjP1qb_gIssxnfO-CpLHA'

    BASE_DIR = os.path.abspath(os.path.dirname(__file__))
    ROOT_DIR = os.path.abspath(os.path.join(BASE_DIR, "..")) # , ".."
    
    # Data and log paths
    LOG_PATH = os.path.join(BASE_DIR, "log_files")
    LOG_PREFIX = "Log_File"
    SCRIPTS_PATH = os.path.join(BASE_DIR, "scripts")
    TEMP_PATH = os.path.join(BASE_DIR, "temp")  # New temp folder
    
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
    
    # Ensure directories exist
    @staticmethod
    def init_dirs():
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
        """Verify that driver executables exist."""
        for driver_path in [Config.CHROMEDRIVER_PATH, Config.GECKODRIVER_PATH, Config.TOR_EXECUTABLE]:
            if driver_path and not os.path.exists(driver_path):
                print(f"Warning: Driver not found at {driver_path}")
            else:
                print(f"Driver found at {driver_path}")