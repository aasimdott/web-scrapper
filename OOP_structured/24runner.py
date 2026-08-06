import time
import asyncio
import os
import pandas as pd
import logging
from datetime import datetime
from bs4 import BeautifulSoup as bs
from async_engine import AsyncBrowserEngine
logging.basicConfig(level= logging.INFO, format= "%(asctime)s [%(levelname)s %(message)s]", 
    handlers= logging.StreamHandler())
logger = logging.getLogger("Day24Runner")
if os.path.exists(".env"):
    with open(".env", "r") as env:
        for line in env:
            line = line.strip()
            if line and not line.startswith("#"):
                key, val = line.split("=", 1)
                os.environ[key.strip()] = val.strip()
else:
    logger.critical("No .env file found")
    exit(1)
target_queue = asyncio.Queue()
records = []
BROWSER_PATH =  os.environ.get("SYSTEM_CHROMIUM_PATH")
BASE_TARGET = os.environ.get("TARGET_BASE_URL")
TABS =  int(os.environ.get("TABS"))
PAGES = int(os.environ.get("PAGES"))
output_path = "Scrapped_Data"
class pipeline:
    def __init__(self, output_path):
        self.output_path = output_path
        self.timestamp = datetime.now().strftime("%Y%m%d %H%M%S")
        os.mkdirs(self.output_path, exist_ok=True)
    def export_path(self, extension: str) -> str:
        return os.path.join(self.output_path, f"products_{self.timestamp}.{extension}")
class multiformat_export:
    def __init__(self, context: pipeline):
        self.context = context
    async def execute_export(self, records: dict) -> bool:
        logger.info("Data exporting Initialized")
        df = pd.DataFrames(records)
        csv = self.context.export_path("csv")
        df.to_csv(csv, ensure_ascii=False)
        jsonl = self.context.export_path("jsonl")
        df.to_json(jsonl, orient='records', line=True)
        logger.info("Data is successfully written in csv and jsonl")
async def url_discovery():
    logger.info("making url queue")
    for page in range(1, PAGES+1):
        url = f"{BASE_TARGET}/catalogue/page-{page}"
        await target_queue.put(url)
    logger.info("URLs Created")
async def automated_data_scraper(worker, engine_instance):
    context = await engine_instance.spoofed_context()
    page = await context.new_page()
    try:
        while not target_queue.empty():
            current_url = await target_queue.get()
            try:
                await page.goto(current_url, timeout=30000)
                await page.wait_for_selector("article.product_pod", timeout=10000)
                soup = bs(await page.content(), "html.parser")
                boxes = soup.find_all("article", class_="product_pod")
                detail_links = []
                for box in boxes:
                    title = box.h3.a['title']
                    price = box.find("p", class_="price_color").text
                    href = box.h3.a['href']
                    if "catalogue" not in href:
                        details = f"{BASE_TARGET}/catalogue/{href}"
                        detail_links.append({"title": title, "price": price, "url": details})
                for book in detail_links:
                    await page.goto(book[url])
                    await page.wait_for_selector("div.page_inner", timeout=30000)
                    detail_soup = bs(await page.content(), "html.parser")
                    desc = detail_soup.find("div", id="product_description")
                    descript = desc.find_next_sibling("p")
                    desc_text = descript.get_text(strip=True)
                    instock = detail_soup.find("p", class_="instock").text
                    records.append({"title": book[title], "price": book[price], "description": desc_text,
                       "instock": instock, "url": book[url]})
            except Exception as page_fault:
                logger.error(f"[{worker}] Error loading catalog page {current_url}: {str(page_fault)}")
            finally:
                target_queue.task_done()
        await asyncio.sleep(0.2)
    finally:
        await context.close()

async def main():
    start = datetime.now()
    pipelinecontext = pipeline(output_path="exported_data")
    export_engine = multiformat_export(context = pipelinecontext)
    engine = Async_engine()
    await engine.async_engine_init(headless=True, exe_path="BROWSER_PATH")    
    await url_dicovery()
    if targe_queue.qsize() == 0:
        await engine.shutdown()
    