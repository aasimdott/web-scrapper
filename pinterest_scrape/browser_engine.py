import logging
from playwright.sync_api import sync_playwright
logging.basicConfig(level= logging.INFO,
    format= "%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler("engine.log", encoding="utf-8"),
        logging.StreamHandler()])
class AutomatedBrowserEngine:
    def __init__(self, profile_path):
        self.profile_path = profile_path
        self.playwright = None
        self.context = None
        self.log = logging.getLogger("BrowserEngine")
        self.log.info("init success")
    def spawn_secure_context(self):
        try:
            self.log.info("core run safely")
            self.playwright = sync_playwright().start()
            self.log.info("Browser launched")
            self.context = self.playwright.chromium.launch_persistent_context(
                headless = False, executable_path = "/usr/bin/chromium",
                user_data_dir = self.profile_path,
                args = ["--disable-blink-features=AutomationControlled",
                 "--no-sandbox", "--disable-infobars"])
            self.log.info("returning the opened browser")
            return self.context
        except Exception as error:
            self.log.critical(f"Exception encountered {str(error)}")
            self.shutdown()
            raise error
    def shutdown(self):
        self.log.warning("closing and terminating process")
        if self.context:
            try:
                self.context.close()
                self.log.info("context closed")
            except Exception as e:
                self.log.error(f"Fatal: {str(e)}")
        if self.playwright:
            try: 
                self.playwright.stop()
                self.log.info("terminated!")
            except Exception as e:
                self.log.error(f"Fatal: {str(e)}")

"""
# 1. THE CLASS KEYWORD (The Blueprint)
# Purpose: This defines a new OOP "Class". Think of it as a master blueprint or layout.
# It doesn't open a browser yet. It just defines the rules, variables, and functions
# that our future browser objects must follow.
class AutomatedBrowserEngine:
    A reusable factory blueprint that creates secure, profile-persistent browsers.

    # 2. THE INITIALIZER METHOD (__init__)
    # Purpose: This is the constructor. It runs AUTOMATICALLY the exact millisecond
    # you create a new instance of this class in your other file.
    # It acts like an intake valve to accept external data when building the object.
    #
    # 3. THE "self" PARAMETER
    # Purpose: "self" represents the specific unique object we are building right now.
    # It allows different functions inside this blueprint to share variables with each other.
    def __init__(self, profile_path):

        # 4. INSTANCE VARIABLES (Attributes)
        # Purpose: By prefixing variables with "self.", we glue them permanently to the object.
        # This keeps the profile path, playwright core, and browser tab safely saved in memory.
        self.profile_path = profile_path  # Saves your specific /home/asim/pinterest_profile path
        self.playwright = None            # Placeholder for the Playwright core process
        self.context = None               # Placeholder for the active persistent browser window

    # 5. CLASS METHOD (A function belonging to the blueprint)
    # Purpose: This is a specialized action our object can perform. Any script that uses
    # this blueprint can call ".spawn_secure_context()" to automatically spin up a browser.
        Builds and returns a fully running, secure browser instance.

        # 6. ENCAPSULATION IN ACTION
        # Purpose: We start the playwright framework and attach it to "self.playwright".
        # Because it's attached to "self", our other function (shutdown) can see it and close it later.

        # 7. EXECUTING COMPLEX BEHAVIOR INSIDE THE BLUEPRINT
        # Purpose: This launches your native Arch Chromium binary using your specific proxy,
        # anti-bot arguments, and user profile data dir, then stores it inside "self.context".

        # 8. RETURN VALUE
        # Purpose: This hands the fully configured, open browser window back to whatever
        # external script called this method (like your run_harvest.py script).

    # 9. DESTRUCTOR / CLEANUP METHOD
    # Purpose: This is another method tied to the object. It handles safely closing down
    # hardware hooks and clearing memory sub-processes from your BlackArch Linux RAM banks.
        Cleans up memory and safely closes background processes on BlackArch.

        # If an active browser context exists, close its window safely

        # If the underlying Playwright core driver is still running, stop it completely
"""
