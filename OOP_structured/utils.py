from datetime import datetime
from pathlib import Path
import re
class DataCleanUtility:
    @staticmethod
    def sanitize_title(raw_text):
        if not raw_text:
            return "No text data provided"
        # 1. Replace non-breaking spaces (\xa0) and newline characters (\n) with clean empty spaces
        cleaned = raw_text.replace("\xa0", " ").replace("\n", " ").replace("\r", " ").strip()
        # 2. Strip typographic curling quotes (“ and ”) that cause spreadsheet format breaks
        cleaned = cleaned.lstrip("“\"'").rstrip("”\"'")
        # 3. Collapse multiple concurrent internal spaces down to a single clean space character
        # Example: "Albert    Einstein" -> "Albert Einstein"
        cleaned = re.sub(r'\s+', ' ', cleaned)
        return cleaned

class StorageSharder:  
    @staticmethod
    def resolve_production_path(data_lake, domain_label):
        # 1. Grab current chronological time markers from the host kernel clock
        current_time = datetime.now()
        year_str = current_time.strftime("%Y")   # e.g., "2026"
        month_str = current_time.strftime("%m")  # e.g., "07"
        timestamp_str = current_time.strftime("%d_%H%M%S") # e.g., "17_143022" (Day_HourMinSec)
        
        # 2. Construct cross-platform directory pathways cleanly using pathlib objects
        # Path: data_lake / quotes_to_scrape / 2026 / 07
        target_directory = Path(data_lake) / domain_label / year_str / month_str
        
        # 3. CRITICAL LINUX SYSTEM CALL: Safely create the folders if they do not exist
        # parents=True forces Python to build all missing parent directories automatically
        # exist_ok=True prevents crashes if the folders are already present on disk
        target_directory.mkdir(parents=True, exist_ok=True)
        
        # 4. Generate a unique, timestamped file name payload destination
        final_file_destination = target_directory / f"{timestamp_str}_harvest_run.csv"
        
        return final_file_destination