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
    