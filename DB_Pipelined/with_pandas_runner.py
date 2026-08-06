import os
import csv
import json
import asyncio
import logging
from datetime import datetime
from bs4 import BeautifulSoup as bs
import aiosqlite
import pandas as pd
from async_engine import AsyncBrowserEngine

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler("Scrapper.log", encoding="utf-8"), logging.StreamHandler()])
logger = logging.getLogger("DataBasePipelined")
if os.path.exists(".env"):
    with open(".env", "r") as envFile:
        for line in envFile:
            cleaned_line = line.strip()
            if cleaned_line and not cleaned_line.startswith("#"):
                key, val = cleaned_line.split("=", 1)
                os.environ[key.strip()] = val.strip()
else:
    logger.critical("No .env file found")
    exit(1)
CHROMIUM_EXE_PATH = os.environ.get("SYSTEM_CHROMIUM_PATH", "/usr/bin/chromium")
BASE_TARGET_URL = os.environ.get("TARGET_BASE_URL", "https://books.toscrape.com/")
NUMBER_CONSUMER_WORKERS = int(os.environ.get("TABS", 2))
TOTAL_PAGES = int(os.environ.get("PAGES", 3))
DATABASE_FILE = "scarped_data.db"

target_queue = asyncio.Queue()

class PipelineContext:
    def __init__(self,output_dir="exports"):
        self.output_dir = output_dir
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        os.makedirs(self.output_dir, exist_ok=True)
    def get_export_path(self, extension: str) -> str:
        return os.path.join(self.output_dir, f"products_{self.timestamp}.{extension}")

class DataQualityGuard:
    """Day 23: Screens attributes directly to catch code breakage or broken fields."""
    @staticmethod
    def verify_product(data: dict) -> tuple[bool, str]:
        if not data.get("title") or data["title"].strip() in ["Unknown Title", ""]:
            return False, "Data Extraction Fault: Title field is blank."
        if not data.get("url") or not data["url"].startswith("http"):
            return False, "Data Extraction Fault: Resource URL target format is invalid."
        if not any(char.isdigit() for char in data.get("price", "")):
            return False, f"Data Extraction Fault: Price string '{data.get('price')}' contains no numeric elements."
        return True, ""

class MultiFormatExporting:
    def __init__(self, context: PipelineContext):
        self.context = context
    async def execute_transform_and_export(self) -> bool:
        logger.info("Init: Export MultiFormat Engine")
        if not os.path.exists(DATABASE_FILE):
            logger.error("Exporting aborted, no Database file found")
            return False
        async with aiosqlite.connect(DATABASE_FILE) as db:
            db.row_factory = aiosqlite.Row
            query = "SELECT title, price, description, source_page, url FROM product_records;"
            async with db.execute(query) as cursor:
                rows = await cursor.fetchall()
        if not rows:
            logger.warning("Export Aborting, DB file is empty")
            return False
        logger.info(f"Exporting {len(rows)} from DB")
        cleaned_records = []
        for row in rows:
            raw_price = row["price"] or "£0.00"
            numeric_price = "".join(c for c in raw_price if c.isdigit() or c == ".")
            cleaned_records.append({
                "title": row["title"],
                "raw_price": raw_price,
                "numeric_price": float(numeric_price) if numeric_price else 0.00,
                "description": (row["description"] or "")[:120]+"...",
                "source_page": row["source_page"],
                "item_url": row["url"]
            })
        csv_file = self.context.get_export_path("csv")
        headers =  cleaned_records[0].keys()
        with open(csv_file, mode="w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=headers)
            writer.writeheader()
            writer.writerows(cleaned_records)
        logger.info(f"[CSV] done in {csv_file}")
        json_file = self.context.get_export_path("json")
        with open(json_file, mode="w", encoding="utf-8") as f:
            json.dump(cleaned_records, f, indent=4, ensure_ascii=False)
        logger.info(f"[JSON] done {json_file}")
        parquet_file = self.context.get_export_path("parquet")
        df = pd.DataFrame(cleaned_records)
        df.to_parquet(parquet_file, index=False, compression="snappy")
        logger.info(f"[Parquet] done {parquet_file}")
        return True

class AsyncDatabaseManager:
    @staticmethod
    async def initialize_db():
        # Replace the base initialize_db string inside AsyncDatabaseManager with this logic:
        async with aiosqlite.connect(DATABASE_FILE) as db:
            await db.execute("PRAGMA journal_mode=WAL;")
            await db.execute("""
                CREATE TABLE IF NOT EXISTS product_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, price TEXT,
                    description TEXT, source_page TEXT, url TEXT UNIQUE, scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS execution_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, worker_id TEXT, event_type TEXT, message TEXT, timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            await db.execute("CREATE INDEX IF NOT EXISTS idx_product_url ON product_records(url);")
            
            # --- DAY 23 UPDATED PRAGMA METADATA PATTERNS ---
            db.row_factory = aiosqlite.Row
            async with db.execute("PRAGMA table_info(product_records);") as cursor:
                existing_columns = {col["name"] for col in await cursor.fetchall()}
            
            if "stock_status" not in existing_columns:
                await db.execute("ALTER TABLE product_records ADD COLUMN stock_status TEXT DEFAULT 'In stock';")
            await db.commit()

    # Expand the static signature arguments and execution maps inside write_product:
    @staticmethod
    async def write_product(worker_id, title, price, description, source_page, url, stock_status):
        async with aiosqlite.connect(DATABASE_FILE) as db:
            await db.execute("""
                INSERT INTO product_records (title, price, description, source_page, url, stock_status)
                VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT(url) DO NOTHING;
            """, (title, price, description, source_page, url, stock_status))
            await db.commit()

    @staticmethod
    async def log_event(worker_id, event_type, message):
        """Saves a pipeline engine event to the internal database ledger."""
        async with aiosqlite.connect(DATABASE_FILE) as db:
            await db.execute(
                "INSERT INTO execution_logs (worker_id, event_type, message) VALUES (?, ?, ?);",
                (worker_id, event_type, message)
            )
            await db.commit()
    @staticmethod
    async def get_completed_pages():
        async with aiosqlite.connect(DATABASE_FILE) as db:
            async with db.execute("SELECT DISTINCT source_page FROM product_records;") as cursor:
                rows = await cursor.fetchall()
                return {row[0] for row in rows if row}

async def URL_Discovery_Producer():
    logger.info("[PRODUCER] Fetching historical progress from SQL database...")
    completed_pages = await AsyncDatabaseManager.get_completed_pages()    
    raw_targets = [f"{BASE_TARGET_URL}catalogue/page-{p}.html" for p in range(1, TOTAL_PAGES + 1)]
    staged_count = 0    
    for url in raw_targets:
        if url in completed_pages:
            continue
        await target_queue.put(url)
        staged_count += 1        
    logger.info(f"[PRODUCER] Staged {staged_count} fresh pages. Skipped {len(completed_pages)} matching DB logs.")
    await AsyncDatabaseManager.log_event("PRODUCER", "STAGING_COMPLETE", f"Staged: {staged_count}, Skipped: {len(completed_pages)}")

async def Automation_Data_Consumer(worker_name, engine_instance):
    logger.info(f"[{worker_name}] Starting worker channel...")
    await AsyncDatabaseManager.log_event(worker_name, "LIFECYCLE", "Worker spawned successfully.")
    context = await engine_instance.create_spoofed_context()
    page = await context.new_page()
    try:
        while not target_queue.empty():
            current_catalog_url = await target_queue.get()
            logger.info(f"[{worker_name}] Processing index page: {current_catalog_url}")
            try:
                logger.info(f"Current_page ---- {current_catalog_url}")
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
                            absolute_detail_url = f"{BASE_TARGET_URL}catalogue/{raw_href.replace("../","")}"
                        else:
                            absolute_detail_url = f"{BASE_TARGET_URL}{raw_href.replace("../","")}"
                        instock_node = pod.find("p", class_="instock")
                        stock_text = instock_node.get_text(strip=True) if instock_node else "In stock"
                        target_detail_links.append({
                            "title": title_text, "price": price_text, "url": absolute_detail_url,
                             "stock_status": stock_text
                        })
                items_saved = 0
                for book in target_detail_links:
                    try:
                        await page.goto(book["url"], timeout=30000)
                        logger.info(f"product >>> {absolute_detail_url}")
                        await page.wait_for_selector("div.page_inner", timeout=10000)
                        detail_soup = bs(await page.content(), "html.parser")
                        logger.info("^^^ got details page")
                        desc_header = detail_soup.find("div", id="product_description")
                        desc_node = desc_header.find_next_sibling("p") if desc_header else None
                        description_text = desc_node.get_text(strip=True) if desc_node else "N/A"
                        product_payload = {"title": book["title"], "price": book["price"], "url": book["url"]}
                        is_valid, validation_error = DataQualityGuard.verify_product(product_payload)
                        
                        if not is_valid:
                            logger.warning(f"[{worker_name}] [QUARANTINE ALERT] Data anomaly hit: {validation_error}")
                            await AsyncDatabaseManager.log_event(worker_name, "SCHEMA_DRIFT", f"{validation_error} at URL: {book['url']}")
                            continue # Bypasses bad entries without halting worker tasks
        
                        # Update the target call to match your versioned schema properties
                        await AsyncDatabaseManager.write_product(
                            worker_id=worker_name, title=book["title"], price=book["price"], description=description_text,
                            source_page=current_catalog_url, url=book["url"], stock_status=book["stock_status"])
                        
                        items_saved += 1
                        await asyncio.sleep(0.2)
                    except Exception as inner_fault:
                        logger.error(f"[{worker_name}] Error <{inner_fault}> extracting detail page of {book["url"]}")
                        continue
            except Exception as page_fault:
                logger.error(f"[{worker_name}] Error loading catalog page {current_catalog_url}: {str(page_fault)}")
                await AsyncDatabaseManager.log_event(worker_name, "PAGE_ERROR", 
                    f"Failed page {current_catalog_url}: {str(page_fault)}")  
            finally:
                target_queue.task_done()
        await asyncio.sleep(1.0)
    finally:
        await context.close()
        await AsyncDatabaseManager.log_event(worker_name, "LIFECYCLE", "Worker shutdown cleanly.")

async def main():
    start_time = datetime.now()
    pipeline_context = PipelineContext(output_dir="exports")
    export_engine = MultiFormatExporting(context=pipeline_context)
    await AsyncDatabaseManager.initialize_db()
    await AsyncDatabaseManager.log_event("SYSTEM", "START", "Crawler execution cycle triggered.")
    engine = AsyncBrowserEngine()
    try:
        await engine.initialize_engine(headless=True, executable_path=CHROMIUM_EXE_PATH)
    except TypeError:
        await engine.initialize_engine(headless=True)
    await URL_Discovery_Producer()
    if target_queue.qsize() == 0:
        logger.info("[COMPLETE] Targets clear. Triggering snapshot export on historic values.")
        await AsyncDatabaseManager.log_event("SYSTEM", "SHUTDOWN",
            "No fresh targets found. Generating snapshots.")
        await engine.shutdown()
    await export_engine.execute_transform_and_export()
    
    consumer_pool = [asyncio.create_task(Automation_Data_Consumer(f"Worker-{i}", 
        engine_instance=engine))for i in range(NUMBER_CONSUMER_WORKERS)]
    await target_queue.join()
    await engine.shutdown()
    await asyncio.gather(*consumer_pool)
    await export_engine.execute_transform_and_export()
    duration = (datetime.now() - start_time).total_seconds()
    logger.info(f"[FINISH] SQLite and file extraction sequence completed in {duration:.2f} seconds.")
    await AsyncDatabaseManager.log_event("SYSTEM", "END", f"Pipeline cycle finished in {duration:.2f}s")
    
if __name__ == "__main__":
    asyncio.run(main())