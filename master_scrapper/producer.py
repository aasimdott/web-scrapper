import sys
from pipeline_tasks import distributed_network_worker

def execute_pipeline_dispatch():
    # Scalable collection array: Can scale cleanly up to 100,000+ target payloads
    target_pool = [
        f"https://books.toscrape.com/catalogue/page-{page_index}.html" 
        for page_index in range(1, 11)
    ]
    
    print(f"🚀 Master Architecture: Blasting {len(target_pool)} tasks out to the Redis Ticket Wheel...")
    
    for url in target_pool:
        # Use .delay() to hand the work entirely off to the background message broker.
        # This function execution returns instantly, bypassing standard loop latency!
        distributed_network_worker.delay(url)
        
    print("\n✅ Load balancing injection pipeline finished successfully.")
    print("👉 All tasks are buffered in Redis. Distributed worker processes are processing them in parallel.")

if __name__ == "__main__":
    execute_pipeline_dispatch()