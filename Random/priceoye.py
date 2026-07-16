import csv
import time
from urllib.parse import quote
from bs4 import BeautifulSoup as bs
from playwright.sync_api import sync_playwright
from playwright_stealth import Stealth

searc = input("Enter for search in priceoye: ")
encoded_search = quote(searc)
url = f"https://priceoye.pk/search?q={encoded_search}"
filename = f"{searc.replace(' ', '_')}_priceoye.csv"

with Stealth().use_sync(sync_playwright()) as p:
    browser = p.chromium.launch(headless=False, executable_path="/usr/bin/chromium")
    context = browser.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    )
    page = context.new_page()

    print(f"\n Heading straight to: {url}")
    page.goto(url, timeout=40000)

    page.wait_for_load_state("networkidle")
    time.sleep(4)

    html = page.content()
    browser.close()

# --- Parsing Logic ---
organize = bs(html, "html.parser")
product_boxes = organize.find_all("div", class_="productBox")

with open(filename, mode="w", newline="", encoding="utf-8") as target:
    writer = csv.writer(target)
    writer.writerow(["Title", "Price", "Link"])

    count = 0
    for box in product_boxes:
        card = box.find("a", class_="product-card")
        if card:
            # 1. Title comes from the data attribute as expected
            title = card.get('data-product-name') or "N/A"
            link = card.get('href') or "N/A"

            # 2. FIX: Find the price-box div element visible in the screenshot
            price_el = box.find("div", class_="price-box")
            if price_el:
                # .text collects all inner strings (e.g., 'Rs' and '899')
                # .replace("\n", "").strip() cleans up the structural linebreaks
                price = price_el.text.replace("\n", "").strip()
            else:
                price = "N/A"

            print(f" Found: {title} | Price: {price}")
            writer.writerow([title, price, link])
            count += 1

print(f"\nDone! Successfully scraped {count} items with their prices into {filename}")
