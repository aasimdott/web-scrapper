import os
import json
import time
import asyncio
import logging
from datetime import datetime
from pathlib import Path
from bs4 import BeautifulSoup as bs
from async_engine import AsyncBrowserEngine, AutomatedStorageSharder

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("day20_stateful_system.log", encoding="utf-8"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("StatefulEngine")

# ─────────────────────────────────────────────────────────────────────
# ENVIRONMENT & PARAMETER CONFIGURATION
# ─────────────────────────────────────────────────────────────────────
if os.path.exists(".env"):
    with open(".env", "r") as env_file:
        for line in env_file:
            cleaned_line = line.strip()
            if cleaned_line and not cleaned_line.startswith("#"):
                key, val = cleaned_line.split("=", 1)
                os.environ[key.strip()] = val.strip()
else:
    logger.critical("Fatal execution stoppage: .env configuration file missing.")
    exit(1)

CHROMIUM_EXEC_PATH = os.environ.get("SYSTEM_CHROMIUM_PATH", "/usr/bin/chromium")
BASE_TARGET_URL = os.environ.get("TARGET_BASE_URL", "http://toscrape.com")
DATA_LAKE_ROOT = os.environ.get("DATA_LAKE_ROOT_DIR", "stateful_json_lake")
NUM_CONSUMER_WORKERS = int(os.environ.get("MAX_CONCURRENT_WORKERS", 2))
TOTAL_PIPELINE_PAGES = int(os.environ.get("TOTAL_PIPELINE_PAGES", 5)) # Scaled to test multi-page tracking

CHECKPOINT_FILE = "state_checkpoint.json"
target_queue = asyncio.Queue()
master_data_pool = []
checkpoint_lock = asyncio.Lock()

# ─────────────────────────────────────────────────────────────────────
# UTILITY ZONE: STATE PERSISTENCE MANAGER
# ─────────────────────────────────────────────────────────────────────
class PipelineCheckpointManager:
    """Manages reading and writing persistent state to prevent duplicated work."""
    
    @staticmethod
    def load_checkpoint():
        """Reads checkpoint file from disk or initializes an empty one."""
        if os.path.exists(CHECKPOINT_FILE):
            try:
                with open(CHECKPOINT_FILE, "r", encoding="utf-8") as f:
                    state = json.load(f)
                    logger.info(f"[CHECKPOINT] Found existing state file. Loaded {len(state.get('completed_pages', []))} processed pages.")
                    return state
            except Exception as e:
                logger.error(f"[CHECKPOINT] Corrupted checkpoint file found. Resetting. Error: {str(e)}")
        
        return {"completed_pages": [], "last_execution_timestamp": 0}

    @staticmethod
    async def save_page_completion(url):
        """Atomically appends a page to the completed database layer."""
        async with checkpoint_lock:
            state = PipelineCheckpointManager.load_checkpoint()
            if url not in state["completed_pages"]:
                state["completed_pages"].append(url)
            state["last_execution_timestamp"] = int(time.time())
            
            # Atomic temporary write-and-rename pattern to guard against partial writes during crashes
            temp_file = f"{CHECKPOINT_FILE}.tmp"
            try:
                with open(temp_file, "w", encoding="utf-8") as f:
                    json.dump(state, f, indent=4)
                os.replace(temp_file, CHECKPOINT_FILE)
            except Exception as e:
                logger.error(f"[CHECKPOINT FAIL] Could not write state index to disk: {str(e)}")

# ─────────────────────────────────────────────────────────────────────
# WORKER PIPELINE LOGIC
# ─────────────────────────────────────────────────────────────────────
async def URL_Discovery_Producer(current_checkpoint):
    logger.info("[PRODUCER] Assessing pipeline work balance against historical checkpoints...")
    raw_targets = [f"{BASE_TARGET_URL}catalogue/page-{p}.html" for p in range(1, TOTAL_PIPELINE_PAGES + 1)]
    
    skipped_count = 0
    for url in raw_targets:
        if url in current_checkpoint.get("completed_pages", []):
            skipped_count += 1
            continue
        await target_queue.put(url)
        
    logger.info(f"[PRODUCER] Staged {target_queue.qsize()} fresh targets. Safely bypassed {skipped_count} already-completed pages.")

async def Automation_Data_Consumer(worker_id, engine_instance):
    logger.info(f"[CONSUMER-{worker_id}] Launching failure-resilient extraction worker channels...")
    context = await engine_instance.spoofed_context()
    page = await context.new_page()
    
    try:
        while True:
            if target_queue.empty():
                break
            current_catalog_url = await target_queue.get()
            
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
                            absolute_detail_url = f"http://toscrape.com/catalogue/{raw_href.replace('../', '')}"
                        else:
                            absolute_detail_url = f"http://toscrape.com{raw_href}"
                            
                        target_detail_links.append({
                            "title": title_text,
                            "price": price_text,
                            "url": absolute_detail_url
                        })

                # Tier 2 Extraction Sequence
                for book in target_detail_links:
                    try:
                        await page.goto(book["url"], timeout=30000)
                        await page.wait_for_selector("div.product_description", timeout=10000)
                        
                        detail_soup = bs(await page.content(), "html.parser")
                        desc_header = detail_soup.find("div", id="product_description")
                        desc_node = desc_header.find_next_sibling("p") if desc_header else None
                        description_text = desc_node.get_text(strip=True) if desc_node else "N/A"
                        
                        master_data_pool.append({
                            "title": book["title"],
                            "price": book["price"],
                            "description": description_text,
                            "source_catalog_page": current_catalog_url
                        })
                        await asyncio.sleep(0.5)
                        
                    except Exception as inner_fault:
                        logger.error(f"[CONSUMER-{worker_id}] Inner exception on detail extraction block: {str(inner_fault)}")
                        continue
                
                # ── STATE LOCK FLUSH ──
                # If the entire listing index and its nested items extract cleanly, log page completion permanently
                await PipelineCheckpointManager.save_page_completion(current_catalog_url)
                logger.info(f"[CONSUMER-{worker_id}] State persistent checkpoint locked for index node: {current_catalog_url.split('/')[-1]}")

            finally:
                target_queue.task_done()
            await asyncio.sleep(1.0)
    finally:
        await context.close()

# ─────────────────────────────────────────────────────────────────────
# MASTER RUNNER CONSOLE
# ─────────────────────────────────────────────────────────────────────
async def main():
    start_time = time.time()
    
    # Read state database from disc before running engine loops
    active_checkpoint = PipelineCheckpointManager.load_checkpoint()
    
    engine = Async_engine()
    try:
        await engine.async_engine_init(headless=True, executable_path=CHROMIUM_EXEC_PATH)
    except TypeError:
        await engine.async_engine_init(headless=True)
        
    await URL_Discovery_Producer(active_checkpoint)
    
    if target_queue.qsize() == 0:
        logger.info("[COMPLETE] All configured targets are already marked complete inside state checkpoints. Stopping pipeline execution safely.")
        await engine.shutdown()
        return

    consumer_pool = [
        asyncio.create_task(Automation_Data_Consumer(worker_id=i, engine_instance=engine))
        for i in range(NUM_CONSUMER_WORKERS)
    ]
    
    await target_queue.join()
    await engine.shutdown()
    await asyncio.gather(*consumer_pool)
    
    total_elapsed_duration = time.time() - start_time
    
    if master_data_pool:
        # Dynamic pathing targeting structural JSON storage parameters
        output_json_path = AutomatedStorageSharder.resolve_production_path(DATA_LAKE_ROOT, "stateful_records")
        output_json_path = Path(output_json_path).with_suffix('.json')
        output_json_path.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            with open(output_json_path, mode="w", encoding="utf-8") as storage_file:
                json.dump(master_data_pool, storage_file, ensure_ascii=False, indent=4)
                
            logger.info(f"[VICTORY] Enterprise JSON document matrix compiled successfully in: {total_elapsed_duration:.2f}s")
            logger.info(f"[STORAGE NODE LOCKED] Path node target location: {output_json_path}")
        except IOError as system_disk_lock_error:
            logger.critical(f"[DISK EXPORT BLOCKED] Failed filesystem transaction: {str(system_disk_lock_error)}")
    else:
        logger.error("[PIPELINE FAIL] Empty dataset tracking arrays encountered.")

if __name__ == "__main__":
    asyncio.run(main())
