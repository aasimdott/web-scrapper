import time
import csv
from bs4 import BeautifulSoup as bs
from playwright.sync_api import sync_playwright
from ..browser_engine import AutomatedBrowserEngine
def remove_duplicates_by_key(matrix: list, key_index: int) -> list:

    seen = set()
    unique_list = []

    for sublist in matrix:
        # Extract the value at the specified key index
        key_value = sublist[key_index]

        # If we haven't seen this key value yet, save the sublist
        if key_value not in seen:
            unique_list.append(sublist)
            seen.add(key_value) # Track the key as seen

    return unique_list

def price_cleaner(price):
    if price == "N/A" or (not price):
        return 0.0
    try:
        if price:
            price =  price.replace("$","").replace("Rs","").replace(",","")
    except Exception:
        return 0.0
    return float(price)

path =  "~"
search = input("Enter for search: ")
encoded = search.replace(" ", "+")
number = int(input("Enter number of pages to crawl: "))
i = 1
int(i)
file_name = f"{search.replace(" ", "_")}_.csv"
data_rows = []
url = f"https://priceoye.pk/search?q={encoded}"
engine = AutomatedBrowserEngine(profile_path=path)
context = engine.spawn_secure_context()
page = context.new_page()
page.goto(url)
while i <= number:
    try:
            page.wait_for_selector("#product-list")
    except Exception:
            print("Loading timeout")
    html = page.content()
    if not html:
        break
    organise = bs(html, "html.parser")
    container = organise.find_all("div", class_="productBox")
    print(f"{i} is the page where the data is")
    for box in container:
        title_element = box.find("div", class_="p-title bold h5")
        if not title_element or title_element == "N/A":
            continue
        title = title_element.get_text(strip=True)
        price_element = box.find("div", class_="price-box p1 saving-hides")
        raw_price = price_element.get_text(strip=True)
        clean_price = price_cleaner(raw_price)
        link_element = box.find("a", class_="product-card")
        link = link_element.get('href')
        data_row =[title, clean_price, link]
        data_rows.append(data_row)
        print(title,"  ", clean_price, "  ", link)
        print("\n")
    i += 1
    page.evaluate("window.scrollTo(0, document.body.scrollHeight);")

with open(file_name, mode="w", newline="", encoding="utf-8") as target:
    excel = csv.writer(target)
    excel.writerow(["Title", "Price", "Link"])
    excel.writerows(remove_duplicates_by_key(data_rows, 0))
