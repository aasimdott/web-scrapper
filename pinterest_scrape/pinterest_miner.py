import csv
import os
import time
from bs4 import BeautifulSoup as bs
from playwright.sync_api import sync_playwright

# Link directly to the exact profile directory you created in your previous step
PROFILE_DIR = "~/pinterest_profile"

search_target = input("Enter what you want to harvest from Pinterest (e.g., 'cyberpunk art'): ")
number = int(input("Enter Number of scrolls: "))
clean_filename = f"{search_target.replace(' ', '_')}_pins.csv"
rows = []
pg = 1
saved_count = 0
engine = AutomatedBrowserEngine(profile_path=PROFILE_DIR)

context = engine.spawn_secure_context()
page = context.pages[0] if context.pages else context.new_page()

# 2. Construct the direct query URL string format
query_url = f"https://pinterest.com/search?q={search_target.replace(' ', '%20')}"
print(f"[NETWORK] Navigating to query grid target...")
page.goto(query_url)
# Wait for the network grid elements to physically assemble on screen
print("[SLOW INTERNET] Allowing 8 seconds for layout initialization...")
time.sleep(8)
# 3. Dynamic Expansion: Scroll down twice to trigger extra hidden pin layouts
print("[INTERACTION] Triggering lazy-loaded masonry blocks...")
for i in range(number):
    html_source = page.content()
    print("\n--- Processing HTML Structure Matrix ---")
    soup = bs(html_source, "html.parser")
    pin_images = soup.find("div", role="list")
    for img in pin_images:
        imge = img.find("img")
        if imge:
            image_url = imge.get("src")
            description = imge.get("alt")
        if image_url and "://i.pinimg.com" in image_url:
        # Upgrade image resolution: Convert small thumbnails to standard high-res assets
            high_res_url = image_url.replace("/236x/", "/736x/")
            cleaned_text = description.replace("This may contain: ", "").replace("This contains an image of: ", "").strip()
            clean_desc = cleaned_text if cleaned_text else "No description text provided"
            rows.append([clean_desc, high_res_url])
            saved_count += 1
    print(f"[EXTRACTED] Located {len(pin_images)} structural grid image files from page ---> {pg}.")
    pg += 1
    page.evaluate("window.scrollTo(0, document.body.scrollHeight);")
    time.sleep(4) # Breathing space for slow connection downlinks

with open(clean_filename, mode="w", newline="", encoding="utf-8") as file:
    excel_writer = csv.writer(file)
    excel_writer.writerow(["Pin Description Title", "Image Link URL"])
    excel_writer.writerows(rows)
print(f"\n[VICTORY] Data pipeline successfully closed.")
print(f"[DATA] {saved_count} clean high-resolution pins saved inside: '{clean_filename}'")
