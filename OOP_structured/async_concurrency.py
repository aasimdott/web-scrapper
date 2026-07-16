import csv, time, asyncio, logging, os
from bs4 import BeautifulSoup as bs
from async_engine import Async_engine
from utils import DataCleanUtility
# 1. TIMESTAMPMED TELEMETRY MATRIX LOGGING
# Configures logging to pipe system data to both the standard output and disk logs
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] (Thread-%(thread)d) %(message)s",
    handlers=[
        logging.FileHandler("queue_system.log", encoding="utf-8"),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger("EnterpriseQueue")

if os.path.exists(".env"):
    logger.info("External configuration asset '.env' detected. Injecting memory states...")
    with open(".env", "r") as env_file:
        for line in env_file:
            # Strip trailing whitespaces and ignore comments or blank spacing lines
            cleaned_line = line.strip()
            if cleaned_line and not cleaned_line.startswith("#"):
                # Split only on the first equals sign to separate key and string values
                key, val = cleaned_line.split("=", 1)
                os.environ[key.strip()] = val.strip()
else:
    logger.critical("Fatal operational breakdown: Missing mandatory environment configuration asset '.env'")
    exit(1)

chromium_path = os.environ.get("SYSTEM_CHROMIUM_PATH", "/usr/bin/chromium")
base_url = os.environ.get("TARGET_BASE_URL", "https://books.toscrape.com")
output_file = os.environ.get("OUTPUT_FILE_NAME", "output.csv")
tabs = int(os.environ.get("TABS", 2))
pages = int(os.environ.get("PAGES", 5))

if not base_url:
    logger.critical("Fatal parameter initialization error: TARGET_BASE_URL variable is undefined.")
    exit(1)

# Initialize central global data array
target_queue = asyncio.Queue()
master_data_pool = []

# ─────────────────────────────────────────────────────────────────────
# ARCHITECTURE ZONE A: THE PRODUCER TASK
# ─────────────────────────────────────────────────────────────────────
async def URL_Discovery_Producer():
    """
    Acts as the data injection engine. Its sole responsibility is to populate 
    the central async queue buffer with fresh, un-scrubbed targets.
    """
    logger.info("[PRODUCER] Initializing database target discovery routine...")
    
    for page_num in range(1, pages + 1):
        target_url = f"{base_url}/catalogue/page-{page_num}.html"
        
        # Asynchronously push the target string into the memory queue box
        # .put() will safely await if the queue hits a defined upper storage limit
        await target_queue.put(target_url)
        logger.debug(f"[PRODUCER] Staged execution target footprint: {target_url}")
        
    logger.info(f"[PRODUCER] Discovery phase complete. Shared queue storage initialized with {target_queue.qsize()} elements.")

# ─────────────────────────────────────────────────────────────────────
# ARCHITECTURE ZONE B: THE CONSUMER WORKER
# ─────────────────────────────────────────────────────────────────────
async def Automation_Data_Consumer(worker_id, engine_instance):
    """
    A persistent, independent browser automation instance. Loops infinitely,
    consuming work from the central queue until the storage matrix is completely drained.
    
    :param worker_id: Incremental integer tracking specific task execution layers
    :param engine_instance: Reference to our inherited custom AsyncBrowserEngine framework code
    """
    logger.info(f"[CONSUMER-{worker_id+1}] Spawning background worker thread...")
    
    # Each consumer worker owns ONE persistent browser context tab to maximize resource lifecycle efficiency
    context = await engine_instance.spoofed_context()
    page = await context.new_page()
    
    try:
        while True:
            # Check the stop boundary condition
            if target_queue.empty():
                logger.info(f"[CONSUMER-{worker_id+1}] Queue exhaustion detected. Preparing loop shutdown sequence.")
                break
                
            # Atomically pull the next available target URL string from the FIFO queue
            current_target = await target_queue.get()
            logger.info(f"[CONSUMER-{worker_id+1}] Locked target assignment: Page {current_target[-3:-2]}")
            
            try:
                # Execute async network request with an aggressive 45-second latency tolerance barrier
                await page.goto(current_target, timeout=45000)
                
                # Verify client-side JavaScript elements have fully materialized before parsing
                await page.wait_for_selector("article.product_pod", timeout=15000)
                
                # Read completely executed browser markup directly from local memory allocations
                html_source = await page.content()
                soup = bs(html_source, "html.parser")
                quote_blocks = soup.find_all("article", class_="product_pod")
                
                local_scraped_counter = 0
                for block in quote_blocks:
                    text = block.h3.a["title"]
                    price = block.find("p", class_="price_color").text
                    
                    if text :
                        
                        # Write structured dictionary objects straight to our thread-safe shared array memory pool
                        master_data_pool.append({
                            "text": text,
                            "price": price
                        })
                        local_scraped_counter += 1
                        
                logger.info(f"[CONSUMER-{worker_id + 1}] Successfully mined {local_scraped_counter} records from Page {current_target[-3:-2]}")
                
            except Exception as execution_failure:
                logger.error(f"[CONSUMER-{worker_id + 1}] Operational crash on target {current_target}: {str(execution_failure)}")
                
            finally:
                # CRITICAL SYSTEM HOOK: Signals back to the queue manager that this specific element has cleared processing
                target_queue.task_done()
                
            # Intercept automated anti-bot fingerprint tracing by adding minor randomized network pacing
            await asyncio.sleep(1.5)
            
    except Exception as structural_failure:
        logger.critical(f"[CONSUMER-{worker_id+1}] Fatal structural thread breakdown: {str(structural_failure)}")
        
    finally:
        # Guarantee resource cleanup on the host BlackArch engine
        await context.close()
        logger.info(f"[CONSUMER-{worker_id+1}] Virtual tab destroyed. Hardware channel closed safely.")

# ─────────────────────────────────────────────────────────────────────
# ARCHITECTURE ZONE C: MAIN COORDINATION ENGINE
# ─────────────────────────────────────────────────────────────────────
async def main():
    """
    System Orchestrator. Sets up the environment, starts producers and consumers,
    tracks synchronization checkpoints, and pipes the final data into long-term storage.
    """
    execution_start_checkpoint = time.time()
    logger.info("Initializing Master Queue Automation Pipeline Control...")
    
    # 1. Initialize our standard async framework infrastructure code
    engine = Async_engine()
    await engine.async_engine_init(headless=True, exe_path=chromium_path)
    
    # 2. Fire the Producer to map all URL targets into RAM storage lines
    await URL_Discovery_Producer()
    
    # 3. Instantiate the exact number of Consumer instances allowed by our hardware constraints
    logger.info(f"[ORCHESTRATOR] Spawning {tabs} concurrent processing channels...")
    consumer_pool = [
        asyncio.create_task(Automation_Data_Consumer(worker_id=i, engine_instance=engine))
        for i in range(tabs)
    ]
    
    # 4. SYSTEM BLOCK POINT: Force the main script to wait until the queue .join() counter hits exactly 0
    logger.info("[ORCHESTRATOR] Synchronizing shared worker channels. Processing live queue context...")
    await target_queue.join()
    
    # 5. Bring down the background hardware hooks completely now that tasks are done
    logger.info("[ORCHESTRATOR] Queue cleared. Commencing mass engine teardown sequence...")
    await engine.shutdown()
    
    # Wait for all consumers to finish cleaning up their background processes
    await asyncio.gather(*consumer_pool)
    
    total_elapsed_time = time.time() - execution_start_checkpoint
    logger.info(f"All processing channels synchronized and closed in exactly: {total_elapsed_time:.2f} seconds.")
    
    if master_data_pool:
        logger.info(f"[DISK-IO] Initiating file write sequences for {len(master_data_pool)} tracked items...")
        try:
            with open(output_file, mode="w", newline="", encoding="utf-8") as storage_file:
                excel_writer = csv.writer(storage_file)
                
                # Write standard database headings
                excel_writer.writerow(["Quote Text Statement", "Book Price"])
                
                for data_record in master_data_pool:
                    excel_writer.writerow([data_record["text"], data_record["price"]])
                    
            logger.info(f"[VICTORY] Enterprise data payload compiled flawlessly inside: '{output_file}'")
            
        except IOError as system_disk_lock_error:
            logger.critical(f"[FATAL DISK ERROR] Could not commit memory payloads to storage file: {str(system_disk_lock_error)}")
    else:
        logger.error("[SYSTEM FAILED] Data compilation sequence resolved with zero valid extractions recorded.")

if __name__ == "__main__":
    asyncio.run(main())
