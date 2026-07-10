import csv
import time
from bs4 import BeautifulSoup as bs
# Import your custom factory blueprint from the other file
from browser_engine import AutomatedBrowserEngine

# Configuration data inputs
PROFILE_DIR = "/home/asim/pinterest_profile"
target = input("Target keyword: ")
rotations = int(input("Scroll rotations: "))
output_dest = f"{target.replace(' ', '_')}_harvest.csv"

extracted_records = []

# 1. Initialize your factory blueprint using your profile path
engine = AutomatedBrowserEngine(profile_path=PROFILE_DIR)

# 2. Tell the engine to spawn a fully configured browser session context
session_context = engine.spawn_secure_context()

# Grab the active page tab from your persistent context profile layout
page = session_context.pages[0] if session_context.pages else session_context.new_page()

try:
    print(f"[NETWORK] Launching automated tracking grid via Tor proxy...")
    page.goto(f"https://pinterest.com/{target.replace(' ', '%20')}")
    time.sleep(8) # Breathing buffer for slower connection configurations

    for rotation in range(rotations):
        print(f"[LOG] Scanning viewport array iteration {rotation + 1}/{rotations}")

        soup = bs(page.content(), "html.parser")
        wrappers = soup.find_all("div", {"data-test-id": "pinWrapper"})

        for wrap in wrappers:
            imge = wrap.find("img")
            if not imge:
                continue

            img_src = imge.get("src")
            img_alt = imge.get("alt") or "No description"

            if img_src and "://://pinimg.com" in img_src:
                high_res = img_src.replace("/236x/", "/736x/")
                clean_desc = img_alt.replace("This may contain: ", "").strip()
                clean_desc = clean_desc if clean_desc else "No description text provided"

                payload = {"title": clean_desc, "url": high_res}

                # Check for duplicates before appending to master tracking array
                if not any(entry["url"] == high_res for entry in extracted_records):
                    extracted_records.append(payload)

        page.evaluate("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(5)

finally:
    # This block GUARANTEES your browser context closes safely even if the code crashes
    print("[SYSTEM] Releasing hardware resource locks cleanly...")
    engine.shutdown()

# 3. Save the results array straight to your spreadsheet
if extracted_records:
    with open(output_dest, mode="w", newline="", encoding="utf-8") as target_file:
        writer = csv.writer(target_file)
        writer.writerow(["Description", "High-Res Source URL"])
        for record in extracted_records:
            writer.writerow([record["title"], record["url"]])
    print(f"[SUCCESS] Exported {len(extracted_records)} unique items into '{output_dest}'")
