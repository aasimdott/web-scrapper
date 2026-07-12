import csv
import time
from bs4 import BeautifulSoup as bs
from playwright.sync_api import sync_playwright
stealth_args = [
    "--disable-blink-features=AutomationControlled", # Deletes the navigator.webdriver = true flag
    "--no-sandbox",                                  # Helps run smoothly on secure Linux configurations
    "--disable-infobars"                            # Prevents Chrome from saying "Controlled by automated software"
]
# ─── THE DATA CLEANING WORKER ───
def clean_price_to_number(raw_price_string):
    if not raw_price_string or raw_price_string == "N/A":
        return 0.0

    try:
        # Handle range strings by splitting and taking the first item
        if "to" in raw_price_string.lower():
            raw_price_string = raw_price_string.lower().split("to")[0]

        cleaned = raw_price_string.replace("$", "").replace("£", "").replace(",", "").strip()
        return float(cleaned)
    except Exception:
        return 0.0
# ────────────────────────────────

searc = input("Enter search query for an elite export: ")
filename = f"{searc.replace(' ', '_')}_polished_dataset.csv"

# --- STEP 1: DOWNLOAD THE WEB DATA ---
with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, executable_path="/usr/bin/chromium", args=stealth_args)
    context = browser.new_context(
        viewport={"width": 1920, "height": 1080}, # Standard desktop screen size
        user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
    page = context.new_page()

    print("Opening target interface...")
    page.goto("https://www.ebay.com")

    sbar = page.locator('[name="_nkw"]')
    sbar.fill(searc)
    page.keyboard.press("Enter")

    try:
        page.wait_for_selector("#srp-river-results", timeout=12000)
    except Exception:
        print("Layout load delay detected.")
        time.sleep(3)

    html = page.content()
    browser.close()

# --- STEP 2: PARSE AND MUTATE DATA IN MEMORY ---
print("\n--- Processing and Cleaning Elements ---")
organise = bs(html, "html.parser")
main_river = organise.find("div", id="srp-river-results")

extracted_data_rows = []

if main_river:
    # Find all items matching card types on eBay's grid layout
    containers = main_river.find_all("li", class_=lambda c: c and ('s-card' in c or 's-item' in c))

    for container in containers:
        title_element = container.find("div", class_="s-card__title")
        if not title_element:
            title_element = container.find("div", class_="s-item__title")
            if not title_element:
                title_element = container.find("span", role="heading")

        raw_title = title_element.get_text(strip=True) if title_element else "N/A"
        clean_title = raw_title.replace("New Listing", "").strip()

        # Skip layout filler templates or empty elements
        if clean_title == "N/A" or "Shop on eBay" in clean_title:
            continue

        price_element = container.find("span", class_="s-card__price")
        if not price_element:
            price_element = container.find("span", class_="s-item__price")

        raw_price = price_element.get_text(strip=True) if price_element else "N/A"

        # Apply currency normalization calculations
        mathematical_price = clean_price_to_number(raw_price)

        link_element = container.find("a", class_="s-card__link")
        if not link_element:
            link_element = container.find("a", class_="s-item__link")

        raw_link = link_element.get('href') if link_element else "N/A"
        clean_link = "N/A"

        if raw_link != "N/A":
            if raw_link.startswith("/"):
                clean_link = f"https://ebay.com{raw_link}"
            else:
                # FIX: Ensure it extracts only the clean string segment before tracking parameters
                clean_link = raw_link.split("?")[0]

        # ────────────────────────────────────────────────────────┐
        # FIXED ROW DATA MAPPING ARRAY                            │
        # ────────────────────────────────────────────────────────┘
        row_data = [
            clean_title,
            mathematical_price,
            clean_link
        ]
        extracted_data_rows.append(row_data)

else:
    print("Main tracking block element was missing.")

# --- STEP 3: EXPORT REFINED DATASETS ---
print(f"Sorting {len(extracted_data_rows)} items...")
# Rearrange the list elements smoothly based on the numeric floating column (Index 2)
extracted_data_rows.sort(key=lambda x: x[1])

print(f"Exporting to spreadsheet...")
with open(filename, mode="w", newline="", encoding="utf-8") as target:
    excel = csv.writer(target)

    # Header list maps directly to rows
    excel.writerow(["Item Title", "Numeric Price (Float)", "Full Product Link"])
    excel.writerows(extracted_data_rows)

print(f"\n[SUCCESS] Compiled {len(extracted_data_rows)} data profiles cleanly.")
print(f"Saved layout as: {filename}")
