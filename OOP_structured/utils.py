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