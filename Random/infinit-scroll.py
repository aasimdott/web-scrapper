import time
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup as bs
search_query = input("Enter an infinite scroll search query: ")
with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, executable_path="/usr/bin/chromium")
    page = browser.new_page()
    print("Navigating to search engine...")
    page.goto("https://duckduckgo.com")
    page.wait_for_selector('[name="q"]')
    sbar = page.locator('[name="q"]')
    sbar.fill(search_query)
    page.keyboard.press("Enter")
    print("Waiting for primary layout elements to render...")
    page.wait_for_selector('article[data-testid="result"]', timeout=15000)
    print("\n[START] Executing automated continuous scrolling engine...")
    scroll_count = 0
    max_scrolls = 5
    while scroll_count < max_scrolls:
        old_height = page.evaluate("document.body.scrollHeight")
        page.evaluate("window.scrollTo(0, document.body.scrollHeight);")
        scroll_count += 1
        print(f"Triggered scroll level {scroll_count}...")
        button = page.locator('[id="more-results"]')
        button.click()
        time.sleep(4)
        new_height = page.evaluate("document.body.scrollHeight")
        if new_height == old_height:
            print("[STOP] Webpage frame height stabilized. No extra items to load.")
            break
    print("\nCapturing total aggregated source markup...")
    fully_loaded_html = page.content()
    browser.close()
soup = bs(fully_loaded_html, "html.parser")
results = soup.find_all("article", {"data-testid": "result"})
print(f"\n[SUCCESS] Extracted a grand total of {len(results)} search results via dynamic scrolling!")
