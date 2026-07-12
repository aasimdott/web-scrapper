import time
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    #1. Fire up your native secure BlackArch Chromium engine
    browser = p.chromium.launch(headless=False, executable_path="/usr/bin/chromium")
    page = browser.new_page()

    #2.Go to a website that actually has a search bar!
    print("Opening DuckDuckGo...")
    page.goto("https://google.com")

    # 3. Target the search bar using its HTML name property -> [name="q"]
    # We use square brackets in Playwright to find attributes like name, placeholder, etc.
    search_bar = page.locator('[name="q"]')

    # 4. Type the phrase into the search input box
    print("Typing search query...")
    search_bar.fill("Linux terminal shortcuts")

    time.sleep(2) # Pause for 2 seconds so you can watch Python type it!

    # 5. Press the physical Enter key on the keyboard layout
    print("Pressing Enter to search...")
    page.keyboard.press("Enter")

    # 6. Wait 4 seconds to let the search results page fully load its new HTML
    print("Waiting for results to load...")
    time.sleep(4)

    # 7. Take a picture of the results page to prove it worked
    page.screenshot(path="duckduckgo_results.png")
    print("Success! Screenshot saved as 'duckduckgo_results.png'")

    browser.close()
#close
