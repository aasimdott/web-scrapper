import csv
import time
from bs4 import BeautifulSoup as bs
from playwright.sync_api import sync_playwright

def extract_price_and_currency(raw_price_string):
    if not raw_price_string or raw_price_string == "N/A":
        return 0.0, "UNKNOWN"
    currency_code = "USD"
    if "$" in raw_price_string:
        currency_code = "USD"
    elif "£" in raw_price_string:
        currency_code = "GBP"
    elif "pkr" in raw_price_string.lower():
        currency_code = "PKR"

    try:
        if "to" in raw_price_string.lower():
            raw_price_string = raw_price_string.lower().split("to")[0]
        cleaned = raw_price_string.replace("$", "").replace("£", "").replace(",", "").strip()
        return float(cleaned), currency_code
    except Exception:
        return 0.0, "UNKNOWN"
stealth_args = [
    "--disable-blink-features=AutomationControlled", # Deletes the navigator.webdriver = true flag
    "--no-sandbox",                                  # Helps run smoothly on secure Linux configurations
    "--disable-infobars"                            # Prevents Chrome from saying "Controlled by automated software"
]
searc = input("Enter search query: ")
filename = f"{searc.replace(' ', '_')}_sorted.csv"

# --- STEP 1: CHROMIUM BROWSER LAYER ---
with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, executable_path="/usr/bin/chromium", args=stealth_args)
    context = browser.new_context(
        viewport={"width": 1920, "height": 1080}, # Standard desktop screen size
        user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
    page = context.new_page()
    page.goto("https://amazon.com")

    search_bar = page.locator('[name="field-keywords"]')
    search_bar.fill(searc)
    page.keyboard.press("Enter")

    print("Waiting for page layouts...")
    page.wait_for_selector('div[data-component-type="s-search-result"]', timeout=15000)
    time.sleep(2)

    html = page.content()
    browser.close()

# --- STEP 2: PARSE MARKUP NODES ---
soup = bs(html, "html.parser")
search_titles = soup.find_all("div", {"data-component-type": "s-search-result"})

extracted_data_rows = []

for item in search_titles:
    try:
        title_element = item.find("h2")
        title = title_element.get_text(strip=True) if title_element else "No Title"

        price_element = item.find("span", class_="a-price-whole")
        raw_price = price_element.get_text(strip=True) if price_element else "N/A"

        numeric_price, currency_iso = extract_price_and_currency(raw_price)

        extracted_data_rows.append([title, raw_price, numeric_price, currency_iso])
    except Exception:
        continue

# ──────────────────────────────────────────────────────────────────┐
# NEW STEP: THE PYTHON SORTING ENGINE                               │
# Rearrange rows based on Index 2 (Numeric Float)                   │
# ──────────────────────────────────────────────────────────────────┘
print(f"Sorting {len(extracted_data_rows)} products from cheapest to dearest...")

extracted_data_rows.sort(key=lambda x: x[2])

# ──────────────────────────────────────────────────────────────────┘

# --- STEP 3: EXPORT SORTED REFINED DATA ---
with open(filename, mode="w", newline="", encoding="utf-8") as target_file:
    excel_writer = csv.writer(target_file)
    excel_writer.writerow(["Product Name", "Raw Price String", "Numeric Price (Float)", "Currency"])
    excel_writer.writerows(extracted_data_rows)

print(f"[SUCCESS] Open '{filename}' to see your sorted market analysis spreadsheet!")
