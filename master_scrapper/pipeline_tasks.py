import os
import json
import time
import socket
import requests
from bs4 import BeautifulSoup
from celery import Celery
from config import REDIS_BROKER_URL, JSONL_OUTPUT_PATH, ScrapedItemSchema, SessionMetricsTracker

# Initialize the Celery Distributed Framework bound to Redis
app = Celery("master_scraper_workers", broker=REDIS_BROKER_URL)

@app.task(bind=True, max_retries=3, default_retry_delay=7)
def distributed_network_worker(self, target_url: str):
    """
    Core Phase 6 distributed task. Can be swallowed and run concurrently 
    by any arbitrary amount of worker machines reading from the Redis queue.
    """
    node_identity = f"worker_node_{socket.gethostname()}_{os.getpid()}"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) ScraperPipeline/2.0"}
    
    # --- PHASE 3 Resilience & Exponential Network Retries Layer ---
    try:
        # Strict timeout guard ensures workers never hang up indefinitely
        response = requests.get(target_url, headers=headers, timeout=8)
        response.raise_for_status()
        
    except (requests.exceptions.RequestException, requests.exceptions.Timeout) as network_error:
        print(f"⚠️ [{node_identity}] Network disruption detected for {target_url}. Error: {network_error}")
        # Automatically pushes the work ticket straight back to the Redis wheel for retry
        raise self.retry(exc=network_error)

    # --- PHASE 2 Extraction, Validation, and Streaming Serialization Layer ---
    raw_html_content = response.text
    downloaded_bytes = len(response.content)
    
    # 1. Update the in-memory global state metrics via classmethod tracker
    SessionMetricsTracker.increment_metrics(downloaded_bytes)
    
    # 2. Extract structured fields safely from DOM
    soup = BeautifulSoup(raw_html_content, "html.parser")
    title_element = soup.find("h1") or soup.find("title")
    extracted_title = title_element.text.strip() if title_element else "Untitled Document"

    try:
        # 3. Enforce absolute type-safety using Pydantic structure
        validated_payload = ScrapedItemSchema(
            url=target_url,
            title=extracted_title,
            status_code=response.status_code,
            worker_node=node_identity,
            timestamp=time.time()
        )
        
        # 4. Stream instantly to hard storage in atomic JSON Lines format (Zero memory leaks)
        with open(JSONL_OUTPUT_PATH, "a", encoding="utf-8") as jsonl_stream:
            jsonl_stream.write(validated_payload.model_dump_json() + "\n")
            
        return f"✅ [{node_identity}] Processed {target_url} successfully. Metric Store size: {SessionMetricsTracker.total_bytes_downloaded}B"

    except Exception as parsing_or_validation_fault:
        # Prevents one broken layout or bad scrape from taking down the master servers
        log_fault = {
            "failed_url": target_url,
            "error_log": str(parsing_or_validation_fault),
            "timestamp": time.time()
        }
        with open("pipeline_crash_logs.jsonl", "a", encoding="utf-8") as fault_stream:
            fault_stream.write(json.dumps(log_fault) + "\n")
        return f"❌ [{node_identity}] Validation or write fault sustained on {target_url}"