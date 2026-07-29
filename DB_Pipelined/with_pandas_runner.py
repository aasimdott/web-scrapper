import os
import csv
import json
import asyncio
import logging
import sqlite3
from datetime import datetime
from urllib.parse import urljoin, urlparse

# Third-party libraries - install with: pip install beautifulsoup4 aiosqlite pandas pyarrow lxml requests
try:
    from bs4 import BeautifulSoup
    import aiosqlite
    import pandas as pd
    import requests
except ImportError as e:
    print(f"Missing required library: {e}")
    print("Please run: pip install beautifulsoup4 aiosqlite pandas pyarrow lxml requests")
    exit(1)

# ============ CONFIGURATION ============
DATABASE_PATH = "scraper_production.db"
OUTPUT_DIR = "exports"
TARGET_URLS = [
    "http://books.toscrape.com/catalogue/page-1.html",
    "http://books.toscrape.com/catalogue/page-2.html",
]
MAX_CONCURRENT_REQUESTS = 3
BATCH_SIZE = 10

# ============ LOGGING SETUP ============
os.makedirs(OUTPUT_DIR, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("scraper_system.log", encoding="utf-8"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("CompleteScraper")

# ============ PHASE 1: DATABASE MANAGER ============
class DatabaseManager:
    """Handles all database operations (both sync and async)"""
    
    @staticmethod
    def initialize_db_sync():
        """Create database tables synchronously (for setup)"""
        with sqlite3.connect(DATABASE_PATH) as conn:
            cursor = conn.cursor()
            
            # Table for raw HTML storage (Day 22 style)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS raw_html_stages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    url TEXT UNIQUE,
                    html_payload TEXT,
                    is_parsed INTEGER DEFAULT 0,
                    scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    error_message TEXT
                )
            """)
            
            # Table for clean product data (Day 21 style)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS product_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT,
                    price TEXT,
                    description TEXT,
                    source_page TEXT,
                    url TEXT UNIQUE,
                    scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Table for execution logs
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS execution_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    worker_id TEXT,
                    event_type TEXT,
                    message TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create indexes for performance
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_raw_url ON raw_html_stages(url)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_raw_parsed ON raw_html_stages(is_parsed)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_product_url ON product_records(url)")
            
            conn.commit()
            logger.info(f"Database initialized: {DATABASE_PATH}")
    
    @staticmethod
    async def save_raw_html_async(url: str, html: str, error: str = None):
        """Save raw HTML to staging table (async)"""
        async with aiosqlite.connect(DATABASE_PATH) as db:
            try:
                await db.execute("""
                    INSERT OR REPLACE INTO raw_html_stages (url, html_payload, is_parsed, error_message)
                    VALUES (?, ?, 0, ?)
                """, (url, html, error))
                await db.commit()
                return True
            except Exception as e:
                logger.error(f"Failed to save raw HTML for {url}: {e}")
                return False
    
    @staticmethod
    async def save_product_async(product_data: dict):
        """Save parsed product data to product_records (async)"""
        async with aiosqlite.connect(DATABASE_PATH) as db:
            try:
                await db.execute("""
                    INSERT OR REPLACE INTO product_records 
                    (title, price, description, source_page, url)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    product_data.get('title', 'Unknown'),
                    product_data.get('price', '£0.00'),
                    product_data.get('description', ''),
                    product_data.get('source_page', ''),
                    product_data.get('url', '')
                ))
                await db.commit()
                return True
            except Exception as e:
                logger.error(f"Failed to save product: {e}")
                return False
    
    @staticmethod
    async def log_event_async(worker_id: str, event_type: str, message: str):
        """Log an event to execution_logs (async)"""
        async with aiosqlite.connect(DATABASE_PATH) as db:
            try:
                await db.execute("""
                    INSERT INTO execution_logs (worker_id, event_type, message)
                    VALUES (?, ?, ?)
                """, (worker_id, event_type, message))
                await db.commit()
            except Exception as e:
                logger.error(f"Failed to log event: {e}")
    
    @staticmethod
    async def get_unparsed_count() -> int:
        """Get count of unparsed HTML in staging"""
        async with aiosqlite.connect(DATABASE_PATH) as db:
            cursor = await db.execute("SELECT COUNT(*) FROM raw_html_stages WHERE is_parsed = 0")
            result = await cursor.fetchone()
            return result[0] if result else 0
    
    @staticmethod
    async def get_product_count() -> int:
        """Get count of products in database"""
        async with aiosqlite.connect(DATABASE_PATH) as db:
            cursor = await db.execute("SELECT COUNT(*) FROM product_records")
            result = await cursor.fetchone()
            return result[0] if result else 0

# ============ PHASE 2: HTTP SCRAPER (Day 21 Style with Enhancements) ============
class HTTPScraper:
    """Fetches HTML from URLs with retry logic and headers"""
    
    def __init__(self):
        self.session = self._create_session()
        self.user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        ]
        self.user_agent_index = 0
    
    def _create_session(self):
        """Create a requests session with default settings"""
        session = requests.Session()
        session.headers.update({
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        })
        return session
    
    def _rotate_user_agent(self):
        """Rotate user agent for each request"""
        self.user_agent_index = (self.user_agent_index + 1) % len(self.user_agents)
        self.session.headers.update({
            'User-Agent': self.user_agents[self.user_agent_index]
        })
    
    async def fetch_page(self, url: str, retries: int = 3) -> tuple[str, str]:
        """
        Fetch a page with retry logic
        Returns: (url, html) or (url, None) on failure
        """
        self._rotate_user_agent()
        
        for attempt in range(retries):
            try:
                logger.info(f"Fetching: {url} (Attempt {attempt + 1}/{retries})")
                
                # Use asyncio.to_thread to make requests non-blocking
                response = await asyncio.to_thread(
                    self.session.get, 
                    url, 
                    timeout=30,
                    allow_redirects=True
                )
                
                if response.status_code == 200:
                    html = response.text
                    logger.info(f"Successfully fetched: {url} ({len(html)} bytes)")
                    return url, html
                else:
                    logger.warning(f"HTTP {response.status_code} for {url}")
                    
            except requests.exceptions.Timeout:
                logger.warning(f"Timeout on attempt {attempt + 1} for {url}")
            except requests.exceptions.ConnectionError:
                logger.warning(f"Connection error on attempt {attempt + 1} for {url}")
            except Exception as e:
                logger.warning(f"Error on attempt {attempt + 1} for {url}: {e}")
            
            # Wait before retry with exponential backoff
            if attempt < retries - 1:
                wait_time = 2 ** attempt  # 1, 2, 4 seconds
                await asyncio.sleep(wait_time)
        
        logger.error(f"All {retries} attempts failed for {url}")
        return url, None

# ============ PHASE 3: HTML PARSER (Day 22 Style with Enhancements) ============
class HTMLParser:
    """Parses HTML and extracts structured data"""
    
    @staticmethod
    def parse_product_page(html: str, source_url: str) -> list[dict]:
        """
        Parse a product listing page
        Returns list of product dictionaries
        """
        if not html:
            return []
        
        soup = BeautifulSoup(html, 'html.parser')
        products = []
        
        # Find all product containers (books on books.toscrape.com)
        product_containers = soup.find_all('article', class_='product_pod')
        
        if not product_containers:
            # Try alternative selectors for other websites
            product_containers = soup.find_all('li', class_='col-xs-6') or soup.find_all('div', class_='product')
        
        for container in product_containers:
            try:
                # Extract title
                title_elem = container.find('h3')
                if title_elem:
                    link_elem = title_elem.find('a')
                    title = link_elem.get('title') or link_elem.get_text(strip=True) if link_elem else 'Unknown'
                else:
                    title = 'Unknown'
                
                # Extract price
                price_elem = container.find('p', class_='price_color')
                if not price_elem:
                    price_elem = container.find('div', class_='price')
                if not price_elem:
                    price_elem = container.find('span', class_='price')
                price = price_elem.get_text(strip=True) if price_elem else '£0.00'
                
                # Extract URL
                link_elem = container.find('a')
                if link_elem and link_elem.get('href'):
                    product_url = urljoin(source_url, link_elem.get('href'))
                else:
                    product_url = source_url
                
                # Extract rating/description if available
                rating_elem = container.find('p', class_='star-rating')
                rating = rating_elem.get('class')[1] if rating_elem and len(rating_elem.get('class', [])) > 1 else 'No Rating'
                
                products.append({
                    'title': title,
                    'price': price,
                    'description': f'Rating: {rating}',
                    'source_page': source_url,
                    'url': product_url
                })
                
            except Exception as e:
                logger.error(f"Error parsing product container: {e}")
                continue
        
        return products
    
    @staticmethod
    def parse_product_detail(html: str, source_url: str) -> dict:
        """
        Parse a product detail page
        Returns a single product dictionary
        """
        if not html:
            return {}
        
        soup = BeautifulSoup(html, 'html.parser')
        
        # Title extraction with multiple selectors
        title_selectors = ['h1', '.product-title', '#productTitle', '.title']
        title = 'Unknown'
        for selector in title_selectors:
            if selector.startswith('.'):
                elem = soup.find(class_=selector[1:])
            elif selector.startswith('#'):
                elem = soup.find(id=selector[1:])
            else:
                elem = soup.find(selector)
            if elem and elem.get_text(strip=True):
                title = elem.get_text(strip=True)
                break
        
        # Price extraction
        price_selectors = ['.price_color', '.price', '.price-value', '#priceblock']
        price = '£0.00'
        for selector in price_selectors:
            if selector.startswith('.'):
                elem = soup.find(class_=selector[1:])
            elif selector.startswith('#'):
                elem = soup.find(id=selector[1:])
            else:
                elem = soup.find(selector)
            if elem and elem.get_text(strip=True):
                price = elem.get_text(strip=True)
                break
        
        # Description extraction
        description = ''
        desc_elem = soup.find('div', id='product_description')
        if desc_elem:
            next_p = desc_elem.find_next_sibling('p')
            if next_p:
                description = next_p.get_text(strip=True)
        
        if not description:
            meta_desc = soup.find('meta', attrs={'name': 'description'})
            if meta_desc:
                description = meta_desc.get('content', '')
        
        if not description:
            first_p = soup.find('p')
            if first_p:
                description = first_p.get_text(strip=True)[:200]
        
        return {
            'title': title,
            'price': price,
            'description': description[:500],
            'source_page': source_url,
            'url': source_url
        }

# ============ PHASE 4: DATA EXPORTER (Day 22 Style) ============
class DataExporter:
    """Exports data to multiple formats"""
    
    def __init__(self, output_dir: str):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    async def export_all(self) -> dict:
        """Export to all formats and return statistics"""
        async with aiosqlite.connect(DATABASE_PATH) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM product_records ORDER BY id")
            rows = await cursor.fetchall()
            
            if not rows:
                logger.warning("No data to export")
                return {'exported': 0}
            
            # Convert to list of dicts
            products = [dict(row) for row in rows]
            
            # Export to CSV
            csv_path = await self.export_csv(products)
            
            # Export to JSON
            json_path = await self.export_json(products)
            
            # Export to Excel (if pandas available)
            excel_path = await self.export_excel(products)
            
            return {
                'total': len(products),
                'csv': csv_path,
                'json': json_path,
                'excel': excel_path
            }
    
    async def export_csv(self, products: list[dict]) -> str:
        """Export to CSV format"""
        if not products:
            return None
        
        filename = os.path.join(self.output_dir, f"products_{self.timestamp}.csv")
        
        # Clean data for CSV
        clean_products = []
        for p in products:
            clean_products.append({
                'Title': p.get('title', ''),
                'Price': p.get('price', ''),
                'Description': p.get('description', '')[:100],
                'Source Page': p.get('source_page', ''),
                'URL': p.get('url', ''),
                'Scraped At': p.get('scraped_at', '')
            })
        
        with open(filename, 'w', newline='', encoding='utf-8') as f:
            if clean_products:
                writer = csv.DictWriter(f, fieldnames=clean_products[0].keys())
                writer.writeheader()
                writer.writerows(clean_products)
        
        logger.info(f"Exported CSV: {filename}")
        return filename
    
    async def export_json(self, products: list[dict]) -> str:
        """Export to JSON format"""
        if not products:
            return None
        
        filename = os.path.join(self.output_dir, f"products_{self.timestamp}.json")
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(products, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Exported JSON: {filename}")
        return filename
    
    async def export_excel(self, products: list[dict]) -> str:
        """Export to Excel format (requires pandas)"""
        if not products:
            return None
        
        try:
            filename = os.path.join(self.output_dir, f"products_{self.timestamp}.xlsx")
            df = pd.DataFrame(products)
            df.to_excel(filename, index=False, engine='openpyxl')
            logger.info(f"Exported Excel: {filename}")
            return filename
        except Exception as e:
            logger.warning(f"Excel export failed (openpyxl not installed): {e}")
            return None

# ============ PHASE 5: MAIN SCRAPER ENGINE ============
class ScraperEngine:
    """Orchestrates the entire scraping pipeline"""
    
    def __init__(self):
        self.scraper = HTTPScraper()
        self.parser = HTMLParser()
        self.exporter = DataExporter(OUTPUT_DIR)
        self.semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)
    
    async def scrape_urls(self, urls: list[str]):
        """Scrape multiple URLs and store raw HTML"""
        logger.info(f"Starting to scrape {len(urls)} URLs...")
        
        tasks = []
        for url in urls:
            task = self._scrape_single_url(url)
            tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        successful = 0
        failed = 0
        for result in results:
            if isinstance(result, Exception):
                failed += 1
                logger.error(f"Scrape task failed: {result}")
            elif result:
                successful += 1
        
        logger.info(f"Scraping complete: {successful} successful, {failed} failed")
        return successful, failed
    
    async def _scrape_single_url(self, url: str):
        """Scrape a single URL with rate limiting"""
        async with self.semaphore:
            # Fetch HTML
            fetched_url, html = await self.scraper.fetch_page(url)
            
            if html:
                # Store raw HTML
                await DatabaseManager.save_raw_html_async(fetched_url, html)
                return True
            else:
                # Store failure
                await DatabaseManager.save_raw_html_async(url, '', error='Failed to fetch')
                return False
    
    async def parse_staged_data(self):
        """Parse all unparsed HTML in staging table"""
        logger.info("Starting parsing of staged HTML...")
        
        async with aiosqlite.connect(DATABASE_PATH) as db:
            db.row_factory = aiosqlite.Row
            
            # Get all unparsed HTML
            cursor = await db.execute("""
                SELECT id, url, html_payload FROM raw_html_stages 
                WHERE is_parsed = 0 AND html_payload != ''
                LIMIT ?
            """, (BATCH_SIZE * 10,))  # Process more at once
            
            rows = await cursor.fetchall()
            
            if not rows:
                logger.info("No unparsed HTML found")
                return 0
            
            parsed_count = 0
            for row in rows:
                row_id = row['id']
                url = row['url']
                html = row['html_payload']
                
                try:
                    # Parse the HTML
                    products = self.parser.parse_product_page(html, url)
                    
                    if products:
                        # Save each product
                        for product in products:
                            await DatabaseManager.save_product_async(product)
                            parsed_count += 1
                        
                        # Mark as parsed
                        await db.execute("UPDATE raw_html_stages SET is_parsed = 1 WHERE id = ?", (row_id,))
                        await db.commit()
                        logger.info(f"Parsed {len(products)} products from {url}")
                    else:
                        # No products found, mark as parsed anyway to avoid re-processing
                        await db.execute("UPDATE raw_html_stages SET is_parsed = -1 WHERE id = ?", (row_id,))
                        await db.commit()
                        logger.info(f"No products found on {url}")
                        
                except Exception as e:
                    logger.error(f"Error parsing {url}: {e}")
                    # Mark as error
                    await db.execute("UPDATE raw_html_stages SET is_parsed = -1, error_message = ? WHERE id = ?", 
                                   (str(e)[:200], row_id))
                    await db.commit()
            
            return parsed_count
    
    async def run_full_pipeline(self, urls: list[str]):
        """Run the complete scraping pipeline"""
        start_time = datetime.now()
        
        # Phase 1: Initialize
        logger.info("=" * 60)
        logger.info("STARTING COMPLETE SCRAPING PIPELINE")
        logger.info("=" * 60)
        
        # Initialize database
        await asyncio.to_thread(DatabaseManager.initialize_db_sync)
        await DatabaseManager.log_event_async("SYSTEM", "START", "Pipeline started")
        
        # Phase 2: Scrape and store raw HTML
        scraped, failed = await self.scrape_urls(urls)
        await DatabaseManager.log_event_async("SCRAPER", "COMPLETE", f"Scraped: {scraped}, Failed: {failed}")
        
        # Phase 3: Parse staged HTML
        parsed = await self.parse_staged_data()
        await DatabaseManager.log_event_async("PARSER", "COMPLETE", f"Parsed: {parsed} items")
        
        # Phase 4: Export data
        export_stats = await self.exporter.export_all()
        
        # Phase 5: Show summary
        total_products = await DatabaseManager.get_product_count()
        unparsed = await DatabaseManager.get_unparsed_count()
        
        elapsed = (datetime.now() - start_time).total_seconds()
        
        logger.info("=" * 60)
        logger.info("PIPELINE COMPLETE - SUMMARY")
        logger.info("=" * 60)
        logger.info(f"Total time: {elapsed:.2f} seconds")
        logger.info(f"URLs scraped: {scraped}")
        logger.info(f"Products parsed: {parsed}")
        logger.info(f"Total products in database: {total_products}")
        logger.info(f"Unparsed HTML remaining: {unparsed}")
        logger.info(f"Exports: {export_stats}")
        logger.info("=" * 60)
        
        await DatabaseManager.log_event_async("SYSTEM", "END", f"Pipeline finished in {elapsed:.2f}s")
        
        return {
            'time': elapsed,
            'scraped': scraped,
            'parsed': parsed,
            'total_products': total_products,
            'exports': export_stats
        }

# ============ PHASE 6: COMMAND LINE INTERFACE ============
async def main():
    """Main entry point with user interaction"""
    
    print("\n" + "="*60)
    print("COMPLETE WEB SCRAPER SYSTEM")
    print("="*60)
    print("\nThis will scrape books.toscrape.com and:")
    print("1. Store raw HTML in database")
    print("2. Parse product information")
    print("3. Export to CSV, JSON, and Excel")
    print("\n" + "="*60 + "\n")
    
    # Ask for custom URLs
    print("Default URLs (books.toscrape.com page 1-2)")
    use_default = input("Use default URLs? (y/n): ").lower()
    
    if use_default == 'y':
        urls = TARGET_URLS
    else:
        print("Enter URLs (one per line, empty line to finish):")
        urls = []
        while True:
            url = input().strip()
            if not url:
                break
            urls.append(url)
        
        if not urls:
            print("No URLs provided, using defaults")
            urls = TARGET_URLS
    
    # Create and run engine
    engine = ScraperEngine()
    results = await engine.run_full_pipeline(urls)
    
    print("\n" + "="*60)
    print("RESULTS")
    print("="*60)
    print(f"✅ Successfully scraped: {results['scraped']} pages")
    print(f"✅ Parsed: {results['parsed']} products")
    print(f"✅ Total products in DB: {results['total_products']}")
    print(f"⏱️ Time taken: {results['time']:.2f} seconds")
    print("\n📁 Check the 'exports/' folder for your data files!")
    print("📄 Check 'scraper_system.log' for detailed logs")
    print("="*60)

if __name__ == "__main__":
    # Create requirements file
    requirements = """
beautifulsoup4>=4.12.0
aiosqlite>=0.19.0
pandas>=2.0.0
pyarrow>=12.0.0
lxml>=4.9.0
requests>=2.31.0
openpyxl>=3.1.0
"""
    with open("requirements.txt", "w") as f:
        f.write(requirements.strip())
    
    print("\n📦 Installing requirements...")
    print("Run: pip install -r requirements.txt")
    print("Then run: python complete_scraper.py\n")
    
    # Run the scraper
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n⚠️  Scraper stopped by user")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        print("Check scraper_system.log for details")