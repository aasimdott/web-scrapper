import time
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    # FORCE PATH: Tell Playwright exactly where your native Arch browser is hiding
    browser = p.chromium.launch(
        headless=False,
        executable_path="/usr/bin/chromium"
    )

    page = browser.new_page()

    print("Opening the website using the exact path to Chromium...")
    page.goto("http://toscrape.com")

    time.sleep(3)

    page.screenshot(path="native_chromium.png")
    print("Success! Picture taken.")
    #closing
    browser.close()
