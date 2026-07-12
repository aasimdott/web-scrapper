import csv
import requests
from bs4 import BeautifulSoup

fake_browser_id = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64)"}

with open("dynamic_books.csv", mode="w", newline="", encoding="utf-8") as target_file:
    excel_writer = csv.writer(target_file)
    excel_writer.writerow(["Book Title", "Price"])

    page_number = 1  # Start at page 1

    while True:  # Keep looping indefinitely
        url = f"http://toscrape.com{page_number}.html"
        webpage_data = requests.get(url, headers=fake_browser_id)

        # BRAKE SYSTEM: If the website says the page doesn't exist (404), STOP!
        if webpage_data.status_code == 404:
            print(f"\nPage {page_number} does not exist. Stopping scraper safely!")
            break

        print(f"Scraping page: {page_number}...")
        organized_html = BeautifulSoup(webpage_data.text, "html.parser")
        all_book_containers = organized_html.find_all("article", class_="product_pod")

        for container in all_book_containers:
            book_title = container.h3.a["title"]
            book_price = container.find("p", class_="price_color").text
            excel_writer.writerow([book_title, book_price])

        page_number += 1  # Increment to move to the next page layout
