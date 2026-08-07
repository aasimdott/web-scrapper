import os
from pydantic import BaseModel, HttpUrl, Field

# 1. Centralized Connection and System Configurations
REDIS_BROKER_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
JSONL_OUTPUT_PATH = "master_distributed_output.jsonl"

# 2. Strict Pydantic Schema Validation (Phase 6 Data Integrity Guard rail)
class ScrapedItemSchema(BaseModel):
    url: str
    title: str = Field(min_length=1, max_length=500)
    status_code: int
    worker_node: str
    timestamp: float

# 3. State Management Metrics Tracker (The cls memory pattern from Phase 2)
class SessionMetricsTracker:
    total_processed = 0
    total_bytes_downloaded = 0

    @classmethod
    def increment_metrics(cls, byte_size: int):
        cls.total_processed += 1
        cls.total_bytes_downloaded += byte_size