import os
import asyncio
import logging
from datetime import datetime
from bs4 import BeautifulSoup as bs
import aiosqlite
from async_engine import AsyncBrowserEngine

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("day21_database_system.log", encoding="utf-8"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("DatabaseEngine")

if os.path.exists(".env"):
    with open(".env", "r") as env_file:
        for line in env_file:
            cleaned_line = line.strip()
            if cleaned_line and not cleaned_line.startswith("#"):
                key, val = cleaned_line.split("=", 1)
                os.environ[key.strip()] = val.strip()
else:
    logger.critical("Configuration failure: .env file is missing.")
    exit(1)

CHROMIUM_EXEC_PATH = os.environ.get("SYSTEM_CHROMIUM_PATH", "/usr/bin/chromium")
BASE_TARGET_URL = os.environ.get("TARGET_BASE_URL", "http://books.toscrape.com/")
NUM_CONSUMER_WORKERS = int(os.environ.get("TABS", 2))
TOTAL_PIPELINE_PAGES = int(os.environ.get("PAGES", 3))

DATABASE_FILE = "crawler_production.db"
target_queue = asyncio.Queue()
class AsyncDatabaseManager:
    """Handles non-blocking SQL initialization, writes, and logging."""
    
    @staticmethod
    async def initialize_db():
        """Creates tables and applies performance indexes on system startup."""
        async with aiosqlite.connect(DATABASE_FILE) as db:
            await db.execute("PRAGMA journal_mode=WAL;")
            await db.execute("""
                CREATE TABLE IF NOT EXISTS product_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    price TEXT,
                    description TEXT,
                    source_page TEXT,
                    url TEXT UNIQUE,
                    scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS execution_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    worker_id TEXT,
                    event_type TEXT,
                    message TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            await db.execute("CREATE INDEX IF NOT EXISTS idx_product_url ON product_records(url);")
            await db.commit()
            logger.info(f"[DATABASE] Initialized '{DATABASE_FILE}' with WAL logging and indexes.")

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
        """Finds already completed source pages to prevent duplicate scrapes."""
        async with aiosqlite.connect(DATABASE_FILE) as db:
            async with db.execute("SELECT DISTINCT source_page FROM product_records;") as cursor:
                rows = await cursor.fetchall()
                return {row for row in rows if row}

    @staticmethod
    async def write_product(worker_id, title, price, description, source_page, url):
        """Saves an extracted product safely, skipping if the URL already exists."""
        async with aiosqlite.connect(DATABASE_FILE) as db:
            try:
                await db.execute("""
                    INSERT INTO product_records (title, price, description, source_page, url)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(url) DO NOTHING;
                """, (title, price, description, source_page, url))
                await db.commit()
            except Exception as e:
                await AsyncDatabaseManager.log_event(
                    worker_id, "WRITE_ERROR", f"Failed writing product {url}: {str(e)}"
                )
                logger.error(f"[{worker_id}] SQL Write Error: {str(e)}")

async def URL_Discovery_Producer():
    """Queues up tasks, automatically filtering out pages processed in past runs."""
    logger.info("[PRODUCER] Fetching historical progress from SQL database...")
    completed_pages = await AsyncDatabaseManager.get_completed_pages()
    
    raw_targets = [f"{BASE_TARGET_URL}catalogue/page-{p}.html" for p in range(1, TOTAL_PIPELINE_PAGES + 1)]
    staged_count = 0
    
    for url in raw_targets:
        if url in completed_pages:
            continue
        await target_queue.put(url)
        staged_count += 1
        
    logger.info(f"[PRODUCER] Staged {staged_count} fresh pages. Skipped {len(completed_pages)} matching DB logs.")
    await AsyncDatabaseManager.log_event("PRODUCER", "STAGING_COMPLETE", f"Staged: {staged_count}, Skipped: {len(completed_pages)}")

async def Automation_Data_Consumer(worker_name, engine_instance):
    """Processes pages, extracts details, and streams data directly to SQLite."""
    logger.info(f"[{worker_name}] Starting worker channel...")
    await AsyncDatabaseManager.log_event(worker_name, "LIFECYCLE", "Worker spawned successfully.")
    
    context = await engine_instance.create_spoofed_context()
    page = await context.new_page()
    
    try:
        while not target_queue.empty():
            current_catalog_url = await target_queue.get()
            logger.info(f"[{worker_name}] Processing index page: {current_catalog_url}")
            
            try:
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
                            absolute_detail_url = f"http://books.toscrape.com/catalogue/{raw_href.replace('../', '')}"
                        else:
                            absolute_detail_url = f"http://books.toscrape.com{raw_href}"
                            
                        target_detail_links.append({
                            "title": title_text,
                            "price": price_text,
                            "url": absolute_detail_url
                        })

                items_saved = 0
                for book in target_detail_links:
                    try:
                        await page.goto(book["url"], timeout=30000)
                        await page.wait_for_selector("div.page_inner", timeout=10000)
                        
                        detail_soup = bs(await page.content(), "html.parser")
                        desc_header = detail_soup.find("div", id="product_description")
                        desc_node = desc_header.find_next_sibling("p") if desc_header else None
                        description_text = desc_node.get_text(strip=True) if desc_node else "N/A"
                        
                        await AsyncDatabaseManager.write_product(
                            worker_id=worker_name,
                            title=book["title"],
                            price=book["price"],
                            description=description_text,
                            source_page=current_catalog_url,
                            url=book["url"]
                        )
                        items_saved += 1
                        await asyncio.sleep(0.2)
                        
                    except Exception as inner_fault:
                        logger.error(f"[{worker_name}] Error extracting detail page {book['url']}: {str(inner_fault)}")
                        continue
                
                await AsyncDatabaseManager.log_event(
                    worker_name, "PAGE_SUCCESS", f"Processed page {current_catalog_url}. Saved {items_saved} items."
                )

            except Exception as page_fault:
                logger.error(f"[{worker_name}] Error loading catalog page {current_catalog_url}: {str(page_fault)}")
                await AsyncDatabaseManager.log_event(worker_name, "PAGE_ERROR", f"Failed page {current_catalog_url}: {str(page_fault)}")
            finally:
                target_queue.task_done()
                
            await asyncio.sleep(1.0)
    finally:
        await context.close()
        await AsyncDatabaseManager.log_event(worker_name, "LIFECYCLE", "Worker shutdown cleanly.")

async def main():
    start_time = datetime.now()
    
    await AsyncDatabaseManager.initialize_db()
    await AsyncDatabaseManager.log_event("SYSTEM", "START", "Crawler execution cycle triggered.")
    
    engine = AsyncBrowserEngine()
    try:
        await engine.initialize_engine(headless=True, executable_path=CHROMIUM_EXEC_PATH)
    except TypeError:
        await engine.initialize_engine(headless=True)
        
    await URL_Discovery_Producer()
    
    if target_queue.qsize() == 0:
        logger.info("[COMPLETE] All configured targets match existing database records. Pipeline stopped safely.")
        await AsyncDatabaseManager.log_event("SYSTEM", "SHUTDOWN", "No fresh targets found. Stopped execution.")
        await engine.shutdown()
        return

    consumer_pool = [
        asyncio.create_task(Automation_Data_Consumer(f"Worker-{i}", engine_instance=engine))
        for i in range(NUM_CONSUMER_WORKERS)
    ]
    
    await target_queue.join()
    await engine.shutdown()
    await asyncio.gather(*consumer_pool)
    
    duration = (datetime.now() - start_time).total_seconds()
    logger.info(f"[FINISH] SQLite relational extraction sequence completed in {duration:.2f} seconds.")
    await AsyncDatabaseManager.log_event("SYSTEM", "END", f"Pipeline cycle finished in {duration:.2f}s")

if __name__ == "__main__":
    asyncio.run(main())
