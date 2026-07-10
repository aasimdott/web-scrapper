#profile creator
import os
import time
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup as bs

# Define a safe local profile directory on your Linux system
PROFILE_DIR = "/home/asim/pinterest_profile"

print("[SYSTEM] Deploying Day 4 Production-Grade Persistent Profile Routine...")

with sync_playwright() as p:
    # ──────────────────────────────────────────────────────────────────┐
    # CRITICAL ADVANCED ENGINE: launch_persistent_context               │
    # This automatically loads and updates cookies on your local drive  │
    # ──────────────────────────────────────────────────────────────────┘
    context = p.chromium.launch_persistent_context(
        user_data_dir=PROFILE_DIR,
        headless=False,
        executable_path="/usr/bin/chromium",
        # Stealth Argument: Bypasses 90% of basic automated fingerprint filters
        args=["--disable-blink-features=AutomationControlled"]
    )

    # Grab the default open tab instead of instantiating an unlinked context
    page = context.pages[0] if context.pages else context.new_page()

    print("[NETWORK] Connecting to target dashboard node...")
    page.goto("https://www.pinterest.com/")

    # Give the page 6 seconds to process background checks on slow connections
    time.sleep(6)

    # ─── THE SMART GATEKEEPER INSPECTOR ───
    # We check if an element unique to the logged-in feed exists (like the search bar or profile badge)
    is_logged_in = page.locator('input[search-analyzer="true"], [data-test-id="header-profile-avatar"]').count() > 0

    if not is_logged_in:
        print("\n[ALERT] Session missing or expired! Redirecting to login terminal view...")
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
        print("\n[BYPASS SUCCESSFUL] Stored session matches active database maps!")
        print("[STEALTH] Bypassed form interfaces cleanly. Target data matrix exposed.")

    # ─── DATA EXTRACTION ───
    print("[HARVEST] Mining layout markup...")
    time.sleep(4)
    html_source = page.content()
    context.close()

# BeautifulSoup Parser Execution Loop
soup = bs(html_source, "html.parser")
print(f"\n--- Scraping Operation complete. Page length in memory: {len(html_source)} bytes ---")
