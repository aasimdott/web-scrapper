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

    """Provides rigid layout schema assertion filters to check and scrub harvested data blocks."""
    
    @staticmethod
    def validate_record(raw_title, raw_price, raw_description):
        """
        Validates the type and presence of incoming data strings, applies fallback
        placeholders for empty elements, and drops broken record maps completely.
        """
        # 1. Structural Schema Assertion Check: Title is non-negotiable data metadata
        clean_title = raw_title.strip() if isinstance(raw_title, str) else ""
        if not clean_title or len(clean_title) < 2:
            logger.warning("[VALIDATION ENGINE] Dropping corrupted record: Missing valid structural Title node.")
            return None
            
        # 2. Type Checking and Fallback Interpolation for Price Elements
        clean_price = raw_price.strip() if isinstance(raw_price, str) else ""
        if not clean_price or "£" not in clean_price:
            logger.warning(f"[VALIDATION ENGINE] Missing currency format marker for item: '{clean_title[:15]}'. Assigning fallback.")
            clean_price = "£0.00 (Price Data Missing)"
            
        # 3. Completeness Verification on Deep Multi-Page Text Nodes
        clean_desc = raw_description.strip() if isinstance(raw_description, str) else ""
        # If text data falls below our minimum completeness threshold, swap with structural flag
        if not clean_desc or len(clean_desc) < 10 or clean_desc.startswith("No description"):
            logger.info(f"[VALIDATION ENGINE] Deep description missing or incomplete for: '{clean_title[:15]}'. Injecting placeholder.")
            clean_desc = "DATA_ERROR: Product description field was left unpopulated by source domain."
            
        return {
            "title": clean_title,
            "price": clean_price,
            "description": clean_desc
        }


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

    