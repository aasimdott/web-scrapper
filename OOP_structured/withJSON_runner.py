# =====================================================================
# SYSTEM ARCHITECTURE: DAY 19 CENTRALIZED JSON STORAGE PIPELINE
# COMPATIBILITY: Python 3.11+ / Playwright Async Core / BlackArch Linux
# =====================================================================

import os
import json  # Inject Python's native high-velocity JSON serialization engine
import time
import asyncio
import logging
from datetime import datetime
from pathlib import Path
from bs4 import BeautifulSoup as bs
from async_engine import Async_engine

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("day19_json_system.log", encoding="utf-8"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("JsonLakeEngine")

# ─────────────────────────────────────────────────────────────────────
# CONFIGURATION VARIABLE PARSING
# ─────────────────────────────────────────────────────────────────────
if os.path.exists(".env"):
    with open(".env", "r") as env_file:
        for line in env_file:
            cleaned_line = line.strip()
            if cleaned_line and not cleaned_line.startswith("#"):
                key, val = cleaned_line.split("=", 1)
                os.environ[key.strip()] = val.strip()
else:
    logger.critical("Fatal execution stoppage: Configuration map missing.")
    exit(1)

CHROMIUM_EXEC_PATH = os.environ.get("SYSTEM_CHROMIUM_PATH", "/usr/bin/chromium")
BASE_TARGET_URL = os.environ.get("TARGET_BASE_URL")
DATA_LAKE_ROOT = os.environ.get("DATA_LAKE_ROOT_DIR", "json_data_lake")
NUM_CONSUMER_WORKERS = int(os.environ.get("MAX_CONCURRENT_WORKERS", 2))
TOTAL_PIPELINE_PAGES = int(os.environ.get("TOTAL_PIPELINE_PAGES", 3))

target_queue = asyncio.Queue()
master_data_pool = []

# ─────────────────────────────────────────────────────────────────────
# ARCHITECTURE ZONE A: EXTENDED FRAMEWORK SHARDER UTILITY (JSON UPDATE)
# ─────────────────────────────────────────────────────────────────────
class JsonStorageSharder:
    """Dynamically creates directory pathways and returns a valid target JSON filename path."""
    
    @staticmethod
    def resolve_json_production_path(domain_label):
        current_time = datetime.now()
        year_str = current_time.strftime("%Y")
        month_str = current_time.strftime("%m")
        timestamp_str = current_time.strftime("%d_%H%M%S")
        
        # Build paths leading inside our configured JSON data reservoir directory
        target_directory = Path(DATA_LAKE_ROOT) / domain_label / year_str / month_str
        target_directory.mkdir(parents=True, exist_ok=True)
        
        # Enforce strict .json extension formatting profiles
        return target_directory / f"{timestamp_str}_document_nodes.json"

# ─────────────────────────────────────────────────────────────────────
# ARCHITECTURE ZONE B: TWO-TIER MULTI-ARRAY WORKER RHYTHM
# ─────────────────────────────────────────────────────────────────────
async def URL_Discovery_Producer():
    targets = [f"{BASE_TARGET_URL}catalogue/page-{p}.html" for p in range(1, TOTAL_PIPELINE_PAGES + 1)]
    for url in targets:
        await target_queue.put(url)

async def Automation_Data_Consumer(worker_id, engine_instance):
    logger.info(f"[CONSUMER-{worker_id}] Launching JSON extraction worker pipeline links...")
    context = await engine_instance.spoofed_context()
    page = await context.new_page()
    
    try:
        while True:
            if target_queue.empty():
                break
            current_catalog_url = await target_queue.get()
            
            try:
                logger.info(f">>> {current_catalog_url}")
                await page.goto(current_catalog_url, timeout=45000)
                await page.wait_for_selector("article.product_pod", timeout=15000)
                
                soup = bs(await page.content(), "html.parser")
                book_pods = soup.find_all("article", class_="product_pod")
                
                target_detail_links = []
                for pod in book_pods:
                    link_node = pod.find("h3").find("a") if pod.find("h3") else None
                    price_node = pod.find("p", class_="price_color")
                    
                    if link_node and price_node:
                        raw_href = link_node.get("href")
                        title_text = link_node.get("title") or link_node.get_text(strip=True)
                        price_text = price_node.get_text(strip=True)
                        
                        if "catalogue/" not in raw_href:
                            absolute_detail_url = f"https://books.toscrape.com/catalogue/{raw_href.replace('../', '')}"
                        else:
                            absolute_detail_url = f"https://books.toscrape.com{raw_href}"
                        logger.info(f">> {absolute_detail_url}")   
                        target_detail_links.append({
                            "title": title_text,
                            "price": price_text,
                            "url": absolute_detail_url
                        })
                
                # TIER 2: ADVANCED NESTED MAP EXTRACTION
                for book in target_detail_links:
                    try:
                        await page.goto(book["url"], timeout=30000)
                        await page.wait_for_selector("div.page_inner", timeout=10000)
                        
                        detail_soup = bs(await page.content(), "html.parser")
                        desc_header = detail_soup.find("div", id="product_description")
                        desc_node = desc_header.find_next_sibling("p") if desc_header else None
                        description_text = desc_node.get_text(strip=True) if desc_node else "N/A"
                        
                        # 1. Pull nested sub-tier elements to demonstrate JSON's layered capability
                        # We extract the book classification breadcrumb pathway from the header
                        breadcrumb_list = detail_soup.find("ul", class_="breadcrumb")
                        category_name = "Unassigned"
                        if breadcrumb_list:
                            crumbs = breadcrumb_list.find_all("li")
                            if len(crumbs) >= 3:
                                category_name = crumbs[2].get_text(strip=True)

                        # 2. Build a rich, deeply nested multi-tiered object structure
                        json_document_node = {
                            "item_identity": {
                                "title": book["title"],
                                "category": category_name
                            },
                            "financials": {
                                "price_raw": book["price"],
                                "currency_type": "GBP"
                            },
                            "metadata": {
                                "deep_description": description_text,
                                "source_link_node": book["url"],
                                "scraped_timestamp_epoch": int(time.time())
                            }
                        }
                        
                        master_data_pool.append(json_document_node)
                        await asyncio.sleep(1.0)
                        
                    except Exception as inner_fault:
                        logger.error(f"[CONSUMER-{worker_id}] Inner bypass error on detail layout page: {str(inner_fault)}")
                        continue
            finally:
                target_queue.task_done()
            await asyncio.sleep(1.5)
    finally:
        await context.close()

# ─────────────────────────────────────────────────────────────────────
# ARCHITECTURE ZONE C: CENTRAL SYSTEMS CONTROLLER & JSON EXPORT
# ─────────────────────────────────────────────────────────────────────
async def main():
    start_time = time.time()
    
    engine = Async_engine()
    try:
        await engine.async_engine_init(headless=True, executable_path=CHROMIUM_EXEC_PATH)
    except TypeError:
        await engine.async_engine_init(headless=True)
        
    await URL_Discovery_Producer()
    
    consumer_pool = [
        asyncio.create_task(Automation_Data_Consumer(worker_id=i, engine_instance=engine))
        for i in range(NUM_CONSUMER_WORKERS)
    ]
    
    await target_queue.join()
    await engine.shutdown()
    await asyncio.gather(*consumer_pool)
    
    total_elapsed_duration = time.time() - start_time
    
    # ─────────────────────────────────────────────────────────────────────
    # JSON STORAGE SERIALIZATION TRANSITION LAYER
    # ─────────────────────────────────────────────────────────────────────
    if master_data_pool:
        # Secure unique timestamped file path targeting our JSON lake
        output_json_path = JsonStorageSharder.resolve_json_production_path("bookstore_json_nodes")
        
        logger.info(f"[DISK-IO] Serializing database dictionaries down to JSON path node: {output_json_path}")
        try:
            with open(output_json_path, mode="w", encoding="utf-8") as storage_file:
                # json.dump() converts memory arrays instantly into a valid JSON string file.
                # indent=4 formats the output with beautiful spacing profiles for easy scannability.
                json.dump(master_data_pool, storage_file, ensure_ascii=False, indent=4)
                
            logger.info(f"[VICTORY] Enterprise JSON document matrix compiled successfully in: {total_elapsed_duration:.2f}s")
            logger.info(f"[STORAGE NODE LOCKED] Path node target location: {output_json_path}")
        except IOError as system_disk_lock_error:
            logger.critical(f"[DISK EXPORT BLOCKED] Failed filesystem transaction: {str(system_disk_lock_error)}")
    else:
        logger.error("[PIPELINE FAIL] Empty dataset tracking arrays encountered.")

if __name__ == "__main__":
    asyncio.run(main())
