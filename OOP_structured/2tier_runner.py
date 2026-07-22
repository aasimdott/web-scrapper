import time, csv, logging, random, asyncio, os
from bs4 import BeautifulSoup as bs
from async_engine import Async_engine
from utils import StorageSharder

logging.basicConfig(level = logging.INFO, 
    format = "%(asctime)s [%(levelname)s] %(message)s",
    handlers = [logging.StreamHandler()])
log = logging.getLogger("Resilience")

if os.path.exists(".env"):
    with open(".env", "r") as env:
        for line in env:
            clean_line = line.strip()
            if clean_line and not clean_line.startswith("#"):
                key, val = clean_line.split("=", 1)
                os.environ[key.strip()] = val.strip()
else:
    log.critical("Fatal: No .env file found")
    exit(1)

browser_path = os.environ.get("SYSTEM_CHROMIUM_PATH", "/usr/bin/chromium")
base_url = os.environ.get("TARGET_BASE_URL", "https://books.toscrape.com/")
data_lake = os.environ.get("data_lake_root", "data_dir")
tabs = int(os.environ.get("TABS", 2))
pages = int(os.environ.get("PAGES", 5))

target_queue = asyncio.Queue()
data_pool = []

async def url_discovery():
    log.info("producing urls")
    targets = [f"{base_url}catalogue/page-{i}.html" for i in range(1, pages+1)]
    for url in targets:
        await target_queue.put(url)
    log.info("urls created")

async def Data_consumer(worker, engine_ins):
    log.info(f"tab-{worker} starting")
    context = await engine_ins.spoofed_context()
    page = await context.new_page()
    max_retries = 3
    base_delay = 2
    try:
        while True:
            if target_queue.empty():
                break
            current_url = await target_queue.get()
            attempt = 0
            success = False
            while attempt <= max_retries and not success:
                try:
                    if attempt > 0:    
                        delay = (base_delay * (2**attempt)) + random.uniform(0.0,1.5)
                        await asyncio.sleep(delay)
                        log.info(f"Tab no.{worker} -> Attempt no. {attempt}")
        
                    await page.goto(current_url, timeout=45000)
                    await page.wait_for_selector("article.product_pod", timeout=15000)
                    html = await page.content()
                    log.info(f"got the outer html content of worker-{worker}, page={current_url}. sending to parser")
                    soup = bs(html, "html.parser")
                    boxes = soup.find_all("article", class_="product_pod")
                    count = 0
                    log.info("traversing cards")
                    for box in boxes:
                        title = box.h3.a['title']
                        price = box.find("p", class_="price_color").text.strip() + "\n"
                        card = box.find("a")
                        card_url = card['href']
                        log.info(f">>> got url {base_url}catalogue/{card_url}")
                        await page.goto(f"{base_url}catalogue/{card_url}", timeout=30000)
                        await page.wait_for_selector("div.page_inner")
                        innerhtml = await page.content()
                        innersoup = bs(innerhtml, "html.parser")
                        instock = innersoup.find("p", class_="instock availability").text.strip() + "\n"
                        if title and price:
                            data_pool.append({"title": title, "price": price, "stock": instock})
                            count += 1
                    if count > 0:
                        success = True
                except (asyncio.TimeoutError,  Exception) as _error:
                    log.critical(f"Fatal Err0r: {_error}")
                    attempt += 1
            target_queue.task_done()
            await asyncio.sleep(1.5)
    finally:
        await context.close()

async def main():
    start = time.time()
    await url_discovery()
    engine = Async_engine()
    await engine.async_engine_init(headless=True, exe_path=browser_path)
    consumers = [asyncio.create_task(Data_consumer(worker=i, engine_ins=engine)) for i in range(1, tabs+1)]
    await target_queue.join()
    await asyncio.gather(*consumers)
    await engine.shutdown()
    elapsed_time = time.time() - start
    log.info(f"Tasks completed in {elapsed_time} seconds")
    
    if data_pool:
        sharder_path = StorageSharder.resolve_production_path(data_lake=data_lake, domain_label="books")
        try:
            log.info(f"Writing {len(data_pool)} data in {sharder_path}")
            with open(sharder_path, mode="w", newline="", encoding="utf-8") as file:
                excel = csv.writer(file)
                excel.writerow(["Title", "Price", "Availability"])
                for data in data_pool:
                    excel.writerow([data["title"], data["price"], data["stock"]])
                log.info("Data Successfully saved.")
        except IOError as write_error:
            log.critical(f"Disk lock : {write_error}")

if __name__ == "__main__":

    asyncio.run(main())
