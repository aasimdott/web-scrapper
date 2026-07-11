#profile creator
import os
import time
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup as bs
from ..browser_engine import AutomatedBrowserEngine

# Define a safe local profile directory on your Linux system
PROFILE_DIR = "~/pinterest_profile"
engine = AutomatedBrowserEngine(profile_path=PROFILE_DIR)
print("[SYSTEM] Deploying Production-Grade Persistent Profile Routine...")
context = engine.spawn_secure_context()

    # Grab the default open tab instead of instantiating an unlinked context
page = context.pages[0] if context.pages else context.new_page()
print("[NETWORK] Connecting to target dashboard node...")
page.goto("https://www.pinterest.com/")
# Give the page 6 seconds to process background checks on slow connections
time.sleep(6)
is_logged_in = page.locator('input[search-analyzer="true"], [data-test-id="header-profile-avatar"]').count() > 0
if not is_logged_in:
    print("\n[ALERT] Redirecting to login terminal view...")
    page.goto("https://pinterest.com/login")
    # STOP MACHINE: Do not try to type machine values instantly.
    # Enter your username and password manually into the open browser window!
    print("[ACTION REQUIRED] Enter your actual credentials into the open Chromium interface now.")
    print("[SYSTEM] Standing by... Waiting for manual dashboard authentication to settle...")
    # The script will wait indefinitely until it visually detects a profile badge or search bar component
    page.wait_for_selector('[data-test-id="header-profile-avatar"], input[type="text"]', timeout=0)
    print("[SUCCESS] Manual verification intercepted! Session permanently tied to your profile drive.")
    time.sleep(3) # Let all structural tokens write down fully
else:
    print("\n[ALREADY] Stored session matches active database maps!")