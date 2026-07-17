import time
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup as bs
searc = input("Enter for Searching")
with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, executable_path="/usr/bin/chromium")
    page = browser.new_page()
    page.goto("https://www.duckduckgo.com/")
    page.wait_for_selector('[name="q"]')
    sbar = page.locator('[name="q"]')
    sbar.fill(searc)
    page.keyboard.press("Enter")
    time.sleep(10)
    page.evaluate("window.scrollTo(0, document.body.scrollHeight);")
    time.sleep(2)
    button = page.locator('[id="more-results"]')
    button.click()
    time.sleep(3)
    page.evaluate("window.scrollTo(0, document.body.scrollHeight);")
    time.sleep(6)
