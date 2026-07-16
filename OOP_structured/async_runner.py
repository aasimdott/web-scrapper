import time, csv, logging, asyncio
from bs4 import BeautifulSoup as bs
from enginebyhand import Async_engine
log = logging.getLogger("Async_Runner")
urls = ["https://books.toscrape.com", "https://priceoye.com"]
data_pool = []
async def harvest(engine_instance, url):
    context = await engine_instance.spoofed_context()
    page = await context.new_page()
    try:
        await page.goto(url)
        await page.wait_for_selector("div.quote", timeout=30000)
        html = await page.content()
        soup = bs(html, "html.parser")
        boxes = soup.find_all("div", class_="quote")
        for box in boxes:
            text = box.find("div", class_="text").get_text(strip=True)
            author = box.find("div", class_="author").get_text(strip=True)
            price = box.find("div", class_="price").get_text(strip=True)
            data_pool.append({"text": text, "author": author, "price": price})
    except Exception as e:
            log.error(f"work failed on url {url} > error: {str(e)}")
async def main():
    start_time = time.time()
    engine = Async_engine()
    await engine.async_engine_init()
    tasks = [harvest(engine, url) for url in urls]
    await asyncio.gather(*tasks)
    await engine.shutdown()
    elapsed = start_time - time.time()
    if data_pool:
        with open("data.csv", mode="w", newline="", encoding="utf-8") as target:
            xl = csv.writer(target)
            xl.writerow(["Title", "Author", "Price"])
            for item in data_pool:
                xl.writerow([item["text"], item["author"], item["price"] ])
if __name__ == "__main__":
    asyncio.run(main())