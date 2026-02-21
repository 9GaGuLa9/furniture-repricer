"""
AFA Stores Scraper - CLOUDFLARE BYPASS + CATEGORY-BASED SCRAPING
Uses cloudscraper to bypass Cloudflare + goes through manufacturer categories
run command “python -m app.scrapers.afa”
"""

import time
import logging
import json
from pathlib import Path
from typing import List, Dict, Optional, Set
from datetime import datetime, timedelta

# Playwright for cookie warm-up
try:
    from rebrowser_playwright.sync_api import sync_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False

from ..modules.error_logger import ScraperErrorMixin
from ..modules.logger import get_logger

try:
    from curl_cffi import requests as curl_requests
    CURL_CFFI_AVAILABLE = True
except ImportError:
    CURL_CFFI_AVAILABLE = False
    try:
        import cloudscraper
        CLOUDSCRAPER_AVAILABLE = True
    except ImportError:
        CLOUDSCRAPER_AVAILABLE = False
        import requests
        logging.error("Neither curl_cffi nor cloudscraper installed! Install: pip install curl-cffi")

logger = get_logger("afa")

class AFAScraper(ScraperErrorMixin):
    """Scraper for afastores.com via Shopify collections - category-based"""

    BASE_URL = "https://www.afastores.com"
    PRODUCTS_PER_PAGE = 30  # AFA displays 30 products per page
    
    # Cookie caching for Playwright warm-up
    COOKIE_FILE = Path('app/data/cookies_afa.json')
    COOKIE_LIFETIME = 1800  # 30 minutes


    # Mapping manufacturers to their slug for category uploads
    MANUFACTURER_SLUGS = {
        "Steve Silver": "steve-silver",
        "Legacy Classic Furniture": "legacy-classic-furniture",
        "Legacy Classic Kids": "legacy-classic-kids",
        "Martin Furniture": "martin-furniture",
        "ACME Furniture": "acme-furniture",
        "Intercon Furniture": "intercon-furniture",
        "Westwood Design": "westwood-design"
    }

    def __init__(self, config: dict, error_logger=None):
        self.config = config
        self.error_logger = error_logger
        self.scraper_name = "AFAScraper"
        self.delay_min = config.get('delay_min', 1.0)
        self.delay_max = config.get('delay_max', 2.0)
        self.retry_attempts = config.get('retry_attempts', 3)
        self.timeout = config.get('timeout', 40)
        self.proxies = config.get('proxies', None)

        self.stats = {
            'total_products': 0,
            'unique_products': 0,
            'errors': 0,
            'manufacturers_processed': 0,
            'categories_processed': 0,
            'empty_categories': 0,
            'successful_retries': 0,
            'failed_categories': 0
        }

        # Track failed categories details
        self.failed_categories_list = []

        # Download categories from JSON
        self.manufacturer_categories = self._load_categories()

        # Initialize session with best available method
        self.session_type = None
        self.impersonate = None

        if CURL_CFFI_AVAILABLE:
            # We use Session to store cookies between requests.
            from curl_cffi.requests import Session

            self.session_type = 'curl_cffi'

            # Auto-detect working browser fingerprint
            logger.info("Initializing curl_cffi with auto-detection...")
            self.impersonate = self._find_working_impersonate()

            if not self.impersonate:
                logger.warning("Auto-detection failed, falling back to chrome120")
                self.impersonate="chrome123"

            # Create a Session (stores cookies including cf_clearance)
            self.session = Session(impersonate=self.impersonate)
            self.scraper = None  # Not used for curl_cffi

            logger.info(f"[DONE] curl_cffi Session created with {self.impersonate}")

            # Warm-up for obtaining cf_clearance
            self._warm_up_session()

        elif CLOUDSCRAPER_AVAILABLE:
            import cloudscraper
            self.session_type = 'cloudscraper'
            self.scraper = cloudscraper.create_scraper(
                browser={
                    'browser': 'chrome',
                    'platform': 'windows',
                    'mobile': False
                },
                delay=10
            )

            self.scraper.headers.update({
                'Accept': 'application/json, text/plain, */*',
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept-Encoding': 'gzip, deflate, br',
                'Referer': 'https://www.afastores.com/',
                'Origin': 'https://www.afastores.com',
                'DNT': '1',
                'Connection': 'keep-alive',
                'Sec-Fetch-Dest': 'empty',
                'Sec-Fetch-Mode': 'cors',
                'Sec-Fetch-Site': 'same-origin'
            })

            logger.info(f"AFA Stores scraper initialized with cloudscraper")

        else:
            # Fallback to regular requests (not recommended for Cloudflare)
            self.session_type = 'requests'
            self.scraper = requests.Session()
            logger.warning("Using basic requests - Cloudflare bypass may not work!")
            logger.warning("Install curl_cffi: pip install curl-cffi")

    def _find_working_impersonate(self) -> Optional[str]:
        """
        Tests various browser fingerprints and returns the one that works
        Critical for bypassing Cloudflare — different fingerprints have different success rates

        Returns:
            Name of working fingerprint or None
        """
        # List of browsers for testing (in order of priority)
        browsers = [
            'chrome123',
            'chrome123',
            'chrome116',
            'chrome110',
            'edge99',
            'safari15_5',
            'safari15_3'
        ]

        logger.info("[SEARCH] Testing browser fingerprints for Cloudflare bypass...")

        for browser in browsers:
            try:
                logger.info(f"  Testing {browser}...")

                # Test 1: Homepage
                response = curl_requests.get(
                    self.BASE_URL,
                    impersonate=browser,
                    timeout=10,
                    proxies=self.proxies
                )

                if response.status_code == 200:
                    logger.info(f"  [DONE] {browser} homepage: 200 OK")

                    # Test 2: Products.json API
                    test_url = f"{self.BASE_URL}/products.json?limit=1"
                    test_resp = curl_requests.get(
                        test_url,
                        impersonate=browser,
                        timeout=20,
                        proxies=self.proxies
                    )

                    if test_resp.status_code == 200:
                        logger.info(f"  [DONE] {browser} products API: 200 OK")
                        logger.info(f"  [DONE][DONE] {browser} PASSED ALL TESTS!")
                        return browser
                    else:
                        logger.warning(f"  [!]  {browser} homepage OK but API failed: {test_resp.status_code}")
                else:
                    logger.warning(f"  [X] {browser} homepage failed: {response.status_code}")

            except Exception as e:
                logger.warning(f"  [X] {browser} error: {e}")
                continue

            time.sleep(2)  # Delay between tests to avoid triggering rate limits

        logger.error("[X] No working browser fingerprint found!")
        return None

    def _load_categories(self) -> dict:
        """
        Download manufacturer categories from JSON file

        Returns:
            Dict with categories for each manufacturer
        """
        try:
            # Path to JSON file with categories
            json_path = Path(__file__).parent.parent / 'data' / 'manufacturer_categories.json'

            if not json_path.exists():
                logger.warning(f"Categories file not found: {json_path}")
                return {}

            with open(json_path, 'r', encoding='utf-8') as f:
                categories = json.load(f)

            logger.info(f"Loaded categories for {len(categories)} manufacturers")
            return categories

        except Exception as e:
            logger.error(f"Failed to load categories: {e}")
            return {}

    def _load_cookies_from_cache(self) -> Optional[Dict]:
        """Load cookies from file if not expired"""
        if not self.COOKIE_FILE.exists():
            logger.debug("[!] No cookie cache found")
            return None
        
        try:
            with open(self.COOKIE_FILE, 'r') as f:
                data = json.load(f)
            
            age = time.time() - data['timestamp']
            if age > self.COOKIE_LIFETIME:
                logger.info(f"[!] Cookies expired ({age/60:.1f} min old)")
                return None
            
            logger.info(f"[OK] Loaded {len(data['cookies'])} cookies from cache ({age/60:.1f} min old)")
            return data['cookies']
        
        except Exception as e:
            logger.error(f"Failed to load cookie cache: {e}")
            return None
    
    def _save_cookies_to_cache(self, cookies: Dict):
        """Save cookies to file"""
        try:
            data = {
                'timestamp': time.time(),
                'cookies': cookies
            }
            with open(self.COOKIE_FILE, 'w') as f:
                json.dump(data, f, indent=2)
            
            logger.info(f"[OK] Saved {len(cookies)} cookies to cache")
        
        except Exception as e:
            logger.error(f"Failed to save cookies: {e}")
    
    def _warm_up_with_playwright(self) -> Dict:
        """
        Get Cloudflare cookies via Playwright (real browser)
        
        Returns:
            Dict of cookies
        """
        if not PLAYWRIGHT_AVAILABLE:
            logger.warning("Playwright not installed! Install: pip install playwright")
            logger.warning("Then run: playwright install chromium")
            return {}
        
        logger.info("="*60)
        logger.info("[HOT] Warming up with Playwright (real browser)...")
        logger.info("="*60)
        
        cookies = {}
        
        try:
            with sync_playwright() as p:
                logger.info("  -> Launching Chromium...")
                browser = p.chromium.launch(headless=True)
                
                context = browser.new_context(
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36',
                    viewport={'width': 1920, 'height': 1080},
                    locale='en-US'
                )
                
                page = context.new_page()
                
                logger.info(f"  -> Opening {self.BASE_URL}...")
                page.goto(self.BASE_URL, wait_until='domcontentloaded', timeout=60000)
                
                logger.info("  -> Waiting for Cloudflare challenge...")
                time.sleep(7)
                
                title = page.title()
                logger.info(f"  -> Page loaded: {title[:50]}")
                
                # Extract cookies
                cookies_list = context.cookies()
                cookies = {c['name']: c['value'] for c in cookies_list}
                
                # Check critical cookies
                if 'cf_clearance' in cookies:
                    logger.info(f"  [OK] Got cf_clearance: {cookies['cf_clearance'][:30]}...")
                else:
                    logger.warning("  [!] No cf_clearance (may still work)")
                
                shopify_cookies = [k for k in cookies.keys() if 'shopify' in k.lower()]
                if shopify_cookies:
                    logger.info(f"  [OK] Got {len(shopify_cookies)} Shopify cookies")
                
                logger.info(f"  [OK] Total cookies: {len(cookies)}")
                
                browser.close()
            
            # Save to cache
            self._save_cookies_to_cache(cookies)
            
            logger.info("[OK] Playwright warm-up completed")
            logger.info("="*60)
            
            return cookies
        
        except Exception as e:
            logger.error(f"Playwright warm-up failed: {e}")
            logger.error("Continuing with curl_cffi warm-up...")
            return {}
    
    def _warm_up_session(self):
        """
        ENHANCED: Playwright warm-up + curl_cffi fallback
        Gets cf_clearance cookie via Playwright or curl_cffi
        """
        # Try to load cached cookies first
        cached_cookies = self._load_cookies_from_cache()
        
        if cached_cookies:
            # Use cached cookies with curl_cffi session
            if self.session_type == 'curl_cffi':
                for name, value in cached_cookies.items():
                    self.session.cookies.set(name, value, domain='afastores.com')
                logger.info("[OK] Using cached cookies with curl_cffi")
                return
        
        # No cache or expired - try Playwright
        if PLAYWRIGHT_AVAILABLE:
            playwright_cookies = self._warm_up_with_playwright()
            
            if playwright_cookies and self.session_type == 'curl_cffi':
                for name, value in playwright_cookies.items():
                    self.session.cookies.set(name, value, domain='afastores.com')
                logger.info("[OK] Applied Playwright cookies to curl_cffi session")
                return
        
        # Fallback to original curl_cffi warm-up
        try:
            logger.info("[HOT] Warming up session with curl_cffi...")

            if self.session_type == 'curl_cffi':
                response = self.session.get(
                    self.BASE_URL,
                    timeout=self.timeout,
                    proxies=self.proxies
                )
            else:
                response = self.scraper.get(
                    self.BASE_URL,
                    timeout=self.timeout,
                    proxies=self.proxies
                )

            response.raise_for_status()

            if self.session_type == 'curl_cffi':
                cookies_str = str(self.session.cookies)[:200]
                has_cf = 'cf_clearance' in cookies_str or 'cloudflare' in cookies_str.lower()
                logger.info(f"[OK] curl_cffi warm-up: {response.status_code}")
                logger.info(f"   Cookies preview: {cookies_str}...")
                if has_cf:
                    logger.info(f"   [OK] Cloudflare cookies detected!")
                else:
                    logger.warning(f"   [!] No obvious Cloudflare cookies (may still work)")
            else:
                logger.info(f"[OK] Session warmed up: {response.status_code}")
                logger.info(f"   Cookies count: {len(self.scraper.cookies)}")

            time.sleep(5)

        except Exception as e:
            logger.error(f"[X] curl_cffi warm-up failed: {e}")
            logger.error("[!] Continuing anyway, but expect 403 errors!")

    def _random_delay(self):
        """
        Longer random delay to bypass rate limiting
        Cloudflare analyzes request speed - too fast = bot
        """
        import random

        base_delay = random.uniform(3.0, 6.0)
        jitter = random.uniform(0, 2.0)
        total_delay = base_delay + jitter

        logger.debug(f"[TIMER]  Random delay: {total_delay:.1f}s")
        time.sleep(total_delay)

    def _fetch_category_products(self, category_slug: str, page: int = 1) -> Optional[dict]:
        """
        Get JSON with products for category from Shopify JSON API
            IMPROVED: Improved logging for logs and Google Sheets

        Args:
            category_slug: Category slug (e.g. "coffee-tables-by-acme")
            page: Page number (default: 1)

        Returns:
            JSON dict with products or None if error
        """
        url = f"{self.BASE_URL}/collections/{category_slug}/products.json"
        params = {'page': page}
        headers = {
            'Accept': 'application/json, text/javascript, */*; q=0.01',
            'Accept-Language': 'en-US,en;q=0.9',
            'Referer': self.BASE_URL,
            'X-Requested-With': 'XMLHttpRequest',
        }

        # Retry loop from tracking
        last_error = None
        last_status_code = None

        for attempt in range(self.retry_attempts):
            try:
                if self.session_type == 'curl_cffi':
                    response = curl_requests.get(
                        url,
                        params=params,
                        headers=headers,
                        timeout=self.timeout,
                        impersonate=self.impersonate,
                        proxies=self.proxies
                    )
                else:
                    response = self.scraper.get(
                        url,
                        params=params,
                        timeout=self.timeout,
                        proxies=self.proxies
                    )

                response.raise_for_status()
                if attempt > 0:
                    logger.info(
                        f"[DONE] Retry SUCCESS - Category: '{category_slug}', "
                        f"Page: {page} (succeeded on attempt {attempt + 1}/{self.retry_attempts})"
                    )
                    self.stats['successful_retries'] += 1

                return response.json()

            except Exception as e:
                last_error = e
                error_str = str(e)

                # Determine HTTP status code
                status_code = None
                for code in ["403", "401", "429", "500", "502", "503"]:
                    if code in error_str:
                        status_code = code
                        last_status_code = code
                        break
                if status_code:
                    logger.warning(
                        f"[!]  HTTP {status_code} - Category: '{category_slug}', "
                        f"Page: {page}, Attempt: {attempt + 1}/{self.retry_attempts}"
                    )
                else:
                    logger.warning(
                        f"[!]  Request error - Category: '{category_slug}', "
                        f"Page: {page}, Attempt: {attempt + 1}/{self.retry_attempts}, "
                        f"Error: {error_str[:100]}"
                    )
                self.log_scraping_error(
                    error=e,
                    url=url,  #  URL for quick debugging
                    context={
                        'method': '_fetch_category_products',
                        'category_slug': category_slug,
                        'page': page,
                        'attempt': f"{attempt + 1}/{self.retry_attempts}",
                        'status_code': status_code,
                        'session_type': self.session_type,
                        'impersonate': self.impersonate if self.session_type == 'curl_cffi' else 'N/A'
                    }
                )
                if status_code == "403":
                    if attempt < self.retry_attempts - 1:
                        backoff_delay = 10 * (2 ** attempt)  # 10s, 20s, 40s
                        logger.warning(f"   [wait] Waiting {backoff_delay}s before retry (exponential backoff)...")
                        time.sleep(backoff_delay)
                        continue
                    else:
                        logger.error(
                            f"   [X] Category '{category_slug}' page {page} FAILED "
                            f"after {self.retry_attempts} attempts (HTTP {status_code})"
                        )
                        break

                # if 401 no point retrying
                if status_code == "401":
                    logger.error(f"   [X] HTTP 401 - authentication issue, stopping retries")
                    break

                # Standard retry for non-403/401 errors
                if attempt < self.retry_attempts - 1 and status_code not in ["403", "401"]:
                    time.sleep(5)
        if last_error:
            logger.error(
                f"[X] FINAL FAILURE - Category: '{category_slug}', Page: {page} - "
                f"gave up after {self.retry_attempts} attempts"
            )

            #  NEW: Track failed category
            self.failed_categories_list.append({
                'category': category_slug,
                'page': page,
                'error': str(last_error)[:100],
                'status_code': last_status_code
            })
            self.stats['failed_categories'] += 1

        self.stats['errors'] += 1
        return None

    def _extract_products_from_json(self, json_data: dict, manufacturer_name: str) -> List[Dict[str, str]]:
        """
        Extracts products from Shopify JSON API response

        Args:
            json_data: JSON response from /collections/.../products.json
            manufacturer_name: Manufacturer name

        Returns:
            List of products
        """
        products = []

        try:
            for product in json_data.get('products', []):
                # Process each product variant
                for variant in product.get('variants', []):
                    sku = variant.get('sku', '').strip()

                    if not sku:
                        continue

                    # Save product
                    products.append({
                        'sku': sku,
                        'price': variant.get('price', ''),
                        'url': f"{self.BASE_URL}/products/{product.get('handle', '')}",
                        'title': product.get('title', ''),
                        'vendor': product.get('vendor', manufacturer_name),
                        'available': variant.get('available', False)
                    })

        except Exception as e:
            logger.error(f"Failed to extract products from JSON: {e}")

        return products

    def _print_scraping_summary(self, all_products: List[Dict[str, str]]):
        """
        Print detailed scraping statistics
         NEW: Shows successful retries, failed categories, and detailed analysis

        Args:
            all_products: List of all collected products
        """
        logger.info("")
        logger.info("="*70)
        logger.info("AFA SCRAPER SUMMARY")
        logger.info("="*70)

        # Main statistics
        logger.info(f"[DATA] STATISTICS:")
        logger.info(f"   Manufacturers processed: {self.stats['manufacturers_processed']}")
        logger.info(f"   Categories processed: {self.stats['categories_processed']}")
        logger.info(f"   Products collected: {len(all_products)}")
        logger.info(f"   Empty categories: {self.stats['empty_categories']}")

        logger.info("")
        logger.info(f"[RETRY] RETRIES:")
        logger.info(f"   Total errors: {self.stats['errors']}")
        logger.info(f"   Successful retries: {self.stats['successful_retries']}")
        logger.info(f"   Failed categories: {self.stats['failed_categories']}")
        if self.stats['errors'] > 0:
            success_rate = (self.stats['successful_retries'] / self.stats['errors']) * 100
            logger.info(f"   Retry success rate: {success_rate:.1f}%")
        if self.failed_categories_list:
            logger.warning("")
            logger.warning(f"[!]  FAILED CATEGORIES ({len(self.failed_categories_list)}):")

            # Show first 15 failed categories
            for i, fc in enumerate(self.failed_categories_list[:15], 1):
                status = f"HTTP {fc['status_code']}" if fc['status_code'] else "Error"
                logger.warning(
                    f"   {i}. '{fc['category']}' page {fc['page']} - "
                    f"{status}: {fc['error']}"
                )

            # If more 15, show how many more
            if len(self.failed_categories_list) > 15:
                remaining = len(self.failed_categories_list) - 15
                logger.warning(f"   ... and {remaining} more failed categories")

            logger.warning("")
            logger.warning("[i] TIP: Check 'Scraping_Errors' sheet in Google Sheets for full details")
            logger.warning("[i] TIP: Use grep 'FINAL FAILURE' in logs to see all failed categories")
        else:
            logger.info("")
            logger.info("[DONE] No failed categories - all retries successful!")

        logger.info("="*70)

    def scrape_category(self, category_slug: str, manufacturer_name: str, seen_skus: Set[str]) -> List[Dict[str, str]]:
        """
        Parses all products from one category

        Args:
            category_slug: Category slug (e.g., “counter-stools-by-steve-silver”)
            manufacturer_name: Manufacturer name for logging
            seen_skus: Set for tracking duplicates

        Returns:
            List of products in this category
        """
        category_products = []
        page = 1

        while True:
            logger.debug(f"    Page {page}...")

            # Get JSON from API
            json_data = self._fetch_category_products(category_slug, page)

            if not json_data:
                logger.debug(f"    No data on page {page}")
                break

            # Extract products from JSON
            page_products = self._extract_products_from_json(json_data, manufacturer_name)

            # Check for empty list - stop
            if not page_products:
                logger.debug(f"    Empty products list on page {page} - stopping")
                break

            # Add only unique SKUs
            new_count = 0
            for product in page_products:
                sku = product['sku']
                if sku not in seen_skus:
                    seen_skus.add(sku)
                    category_products.append(product)
                    new_count += 1

            logger.debug(f"    Page {page}: {len(page_products)} products, {new_count} new")

            # If there are fewer than 30 items, this is the last page
            if len(page_products) < self.PRODUCTS_PER_PAGE:
                logger.debug(f"    Got {len(page_products)} products (< {self.PRODUCTS_PER_PAGE}) - last page")
                break

            page += 1

            # Protection from infinite loops
            if page > 100:
                logger.warning(f"    Reached page limit (100) for category {category_slug}")
                break

            self._random_delay()

        return category_products

    def scrape_manufacturer(self, manufacturer_name: str, manufacturer_slug: str,
                            seen_skus: Set[str]) -> List[Dict[str, str]]:
        """
        Parses all categories of one manufacturer

        Args:
            manufacturer_name: Manufacturer name (e.g., “Steve Silver”)
            manufacturer_slug: Manufacturer slug for category retrieval
            seen_skus: Set for tracking duplicates

        Returns:
            List of products from this manufacturer
        """
        logger.info(f"\n{'='*60}")
        logger.info(f"Processing manufacturer: {manufacturer_name}")
        logger.info(f"{'='*60}")

        # Get a list of categories for this manufacturer
        categories = self.manufacturer_categories.get(manufacturer_slug, [])

        if not categories:
            logger.warning(f"No categories found for {manufacturer_name} (slug: {manufacturer_slug})")
            return []

        logger.info(f"Found {len(categories)} categories")

        manufacturer_products = []
        start_time = datetime.now()

        for idx, category_slug in enumerate(categories, 1):
            logger.info(f"\n  [{idx}/{len(categories)}] Category: {category_slug}")

            # Scrape category
            category_products = self.scrape_category(category_slug, manufacturer_name, seen_skus)

            if category_products:
                manufacturer_products.extend(category_products)
                logger.info(f"    [OK] Collected {len(category_products)} products")
                self.stats['categories_processed'] += 1
            else:
                logger.debug(f"    Empty category")
                self.stats['empty_categories'] += 1

            # Progress info every 5 categories
            if idx % 5 == 0 and idx < len(categories):
                elapsed = (datetime.now() - start_time).total_seconds() / 60
                speed = idx / elapsed if elapsed > 0 else 0
                remaining = len(categories) - idx
                eta = remaining / speed if speed > 0 else 0

                logger.info(f"\n  Progress:")
                logger.info(f"     Categories: {idx}/{len(categories)} ({idx/len(categories)*100:.1f}%)")
                logger.info(f"     Products: {len(manufacturer_products)}")
                logger.info(f"     Speed: {speed:.1f} cat/min")
                logger.info(f"     ETA: {eta:.1f} min\n")

            # Delay between categories
            if idx < len(categories):
                self._random_delay()

        elapsed = (datetime.now() - start_time).total_seconds() / 60
        logger.info(f"\n[OK] Manufacturer {manufacturer_name} completed:")
        logger.info(f"  Categories processed: {len(categories)}")
        logger.info(f"  Products collected: {len(manufacturer_products)}")
        logger.info(f"  Time: {elapsed:.1f} minutes")

        self.stats['manufacturers_processed'] += 1

        return manufacturer_products

    def scrape_all_products(self) -> List[Dict[str, str]]:
        """Parses all products from all manufacturers"""

        all_products = []
        seen_skus: Set[str] = set()

        try:
            for manufacturer_name, manufacturer_slug in self.MANUFACTURER_SLUGS.items():
                try:
                    products = self.scrape_manufacturer(
                        manufacturer_name,
                        manufacturer_slug,
                        seen_skus
                    )
                    all_products.extend(products)

                except Exception as e:
                    self.log_scraping_error(
                        error=e,
                        context={'manufacturer': manufacturer_name}
                    )
                    logger.error(f"Failed {manufacturer_name}: {e}")
                    continue

                time.sleep(4)

        except Exception as e:
            self.log_scraping_error(error=e, context={'stage': 'main'})
            raise
        self._print_scraping_summary(all_products)

        return all_products

    def get_stats(self) -> dict:
        """Returns statistics"""
        return self.stats.copy()

    def test_connection(self) -> dict:
        """Tests the connection to the diagnostic site"""
        results = {
            'homepage': False,
            'products_api': False,
            'ip_blocked': False,
            'cloudflare': False,
            'session_type': self.session_type,
            'details': []
        }

        # Headers for tests
        headers = {
            'Accept': 'application/json, text/javascript, */*; q=0.01',
            'Accept-Language': 'en-US,en;q=0.9',
            'Referer': self.BASE_URL,
            'X-Requested-With': 'XMLHttpRequest',
        }

        # Test 1: Access to the main page
        try:
            logger.info("Testing homepage access...")

            if self.session_type == 'curl_cffi':
                resp = curl_requests.get(
                    self.BASE_URL,
                    headers=headers,
                    timeout=self.timeout,
                    impersonate=self.impersonate,
                    proxies=self.proxies
                )
            else:
                resp = self.scraper.get(self.BASE_URL, timeout=self.timeout, proxies=self.proxies)

            results['homepage'] = resp.status_code == 200
            results['details'].append(f"Homepage: {resp.status_code}")

            if 'cloudflare' in resp.text.lower() or 'cf-ray' in resp.headers:
                results['cloudflare'] = True
                results['details'].append("Cloudflare detected")
        except Exception as e:
            results['details'].append(f"Homepage error: {e}")

        # Test 2: Products JSON API (test category)
        try:
            logger.info("Testing products API...")

            # Use the first category of the first manufacturer
            first_mfr_slug = list(self.MANUFACTURER_SLUGS.values())[0] if self.MANUFACTURER_SLUGS else None
            if first_mfr_slug and first_mfr_slug in self.manufacturer_categories:
                test_category = self.manufacturer_categories[first_mfr_slug][0]
                test_url = f"{self.BASE_URL}/collections/{test_category}/products.json"

                if self.session_type == 'curl_cffi':
                    resp = curl_requests.get(
                        test_url,
                        params={'page': 1},
                        headers=headers,
                        timeout=self.timeout,
                        impersonate=self.impersonate,
                        proxies=self.proxies
                    )
                else:
                    resp = self.scraper.get(
                        test_url,
                        params={'page': 1},
                        timeout=self.timeout,
                        proxies=self.proxies
                    )

                results['products_api'] = resp.status_code == 200
                results['details'].append(f"Products API: {resp.status_code}")

                if resp.status_code == 403:
                    results['ip_blocked'] = True
                    results['details'].append("403 Forbidden - possible IP block")
        except Exception as e:
            results['details'].append(f"Products API error: {e}")
            if '403' in str(e):
                results['ip_blocked'] = True

        return results

def scrape_afa(config: dict, error_logger=None) -> List[Dict[str, str]]:
    """Main function for parsing AFA Stores"""
    scraper = AFAScraper(config, error_logger=error_logger)
    results = scraper.scrape_all_products()
    return results

# Standalone mode - launch as a separate module
# Usage: python -m app.scrapers.afa

if __name__ == "__main__":
    import sys
    import argparse
    import yaml

    print("="*60)
    print("AFA Stores Scraper - Standalone Mode")
    print("="*60)
    print()

    # Parse arguments
    parser = argparse.ArgumentParser(
        description='AFA Stores Scraper',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument(
        '--test',
        action='store_true',
        help='Test connection only (diagnose 403 errors)'
    )

    parser.add_argument(
        '--manufacturer',
        type=str,
        help='Scrape single manufacturer (e.g., "Steve Silver")'
    )

    parser.add_argument(
        '--output',
        type=str,
        help='Output JSON file (default: afa_products_TIMESTAMP.json)'
    )

    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Enable verbose logging'
    )

    parser.add_argument(
        '--config',
        type=str,
        default='config.yaml',
        help='Path to config.yaml (default: config.yaml)'
    )

    args = parser.parse_args()

    # Setup logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%H:%M:%S'
    )

    # Load config
    config_path = Path(args.config)

    if not config_path.exists():
        print(f"\033[91m✗ Config file not found: {config_path}\033[0m")
        print("\nTrying to find config.yaml...")

        # Try to find relative to the current file
        module_dir = Path(__file__).parent.parent.parent
        config_path = module_dir / 'config.yaml'

        if not config_path.exists():
            print(f"\033[91m✗ Config not found at: {config_path}\033[0m")
            print("\nPlease specify config path with --config")
            sys.exit(1)

    print(f"\033[92m[OK] Loading config: {config_path}\033[0m")

    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)

    # Get AFA config
    afa_config = config.get('scrapers', {}).get('afastores', {})

    scraper_config = {
        'delay_min': afa_config.get('delay_min', 1.0),
        'delay_max': afa_config.get('delay_max', 2.0),
        'retry_attempts': afa_config.get('max_retries', 3),
        'timeout': afa_config.get('timeout', 40),
        'proxies': None
    }

    # Initialize error logger (optional)
    error_logger = None

    try:
        from ..modules.error_logger import ErrorLogger
        from ..modules.google_sheets import GoogleSheetsClient

        credentials_path = config.get('google', {}).get('credentials_file')
        sheet_id = config.get('main_sheet', {}).get('id')

        if credentials_path and sheet_id:
            credentials_path = Path(credentials_path)
            if credentials_path.exists():
                sheets_client = GoogleSheetsClient(str(credentials_path))
                error_logger = ErrorLogger(
                    sheets_client=sheets_client,
                    sheet_id=sheet_id,
                    enabled=True
                )
                print(f"\033[92m[OK] Error logger initialized\033[0m")
    except Exception as e:
        print(f"\033[93m[!] Could not initialize error logger: {e}\033[0m")

    # Create scraper
    print(f"\033[94mℹ Initializing AFA scraper...\033[0m")

    scraper = AFAScraper(
        config=scraper_config,
        error_logger=error_logger
    )

    print(f"\033[92m[OK] Scraper initialized (session: {scraper.session_type})\033[0m")
    print()

    # Execute command

    if args.test:
        # TEST CONNECTION
        print("\033[94mℹ Testing connection to AFA Stores...\033[0m")
        print("="*60)

        results = scraper.test_connection()

        # Display results
        print(f"\nSession type: {results.get('session_type', 'unknown')}")

        status = "\033[92m[OK]\033[0m" if results['homepage'] else "\033[91m[FAIL]\033[0m"
        print(f"Homepage: {status}")

        status = "\033[92m[OK]\033[0m" if results['products_api'] else "\033[91m[FAIL]\033[0m"
        print(f"Products API: {status}")

        status = "detected" if results['cloudflare'] else "not detected"
        print(f"Cloudflare: {status}")

        status = "\033[91mYES\033[0m" if results['ip_blocked'] else "no"
        print(f"IP blocked: {status}")

        print("\nDetails:")
        for detail in results.get('details', []):
            print(f"  - {detail}")

        print("="*60)

        # Summary
        if results['ip_blocked']:
            print(f"\n\033[91m[X] IP BLOCKED (403 Forbidden)\033[0m")
            print(f"\033[94mℹ Possible solutions:\033[0m")
            print("  1. Use proxy (configure in config.yaml)")
            print("  2. Wait 24h for IP unblock")
            print("  3. Try from different network/VPS")
        elif results['homepage'] and results['products_api']:
            print(f"\n\033[92m[OK] Connection OK\033[0m")
        elif results['cloudflare']:
            print(f"\n\033[93m[!]  Cloudflare detected but connection works\033[0m")
        else:
            print(f"\n\033[91m[X] Connection failed\033[0m")

    elif args.manufacturer:

        # SCRAPE ONE MANUFACTURER
        manufacturer_name = args.manufacturer
        manufacturer_slug = scraper.MANUFACTURER_SLUGS.get(manufacturer_name)

        if not manufacturer_slug:
            print(f"\033[91m✗ Manufacturer not found: {manufacturer_name}\033[0m")
            print("\nAvailable manufacturers:")
            for name in scraper.MANUFACTURER_SLUGS.keys():
                print(f"  - {name}")
            sys.exit(1)

        print(f"\033[94mℹ Scraping manufacturer: {manufacturer_name}\033[0m")
        print("="*60)

        seen_skus = set()
        products = scraper.scrape_manufacturer(
            manufacturer_name=manufacturer_name,
            manufacturer_slug=manufacturer_slug,
            seen_skus=seen_skus
        )

        print("="*60)
        print(f"\033[92m[OK] Collected {len(products)} products from {manufacturer_name}\033[0m")

        # Save if requested
        if args.output or not args.output:
            output_file = args.output or f"afa_{manufacturer_slug}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(products, f, indent=2, ensure_ascii=False)

            print(f"\033[92m[OK] Results saved to: {output_file}\033[0m")

    else:

        # SCRAPE ALL MANUFACTURERS
        print(f"\033[94mℹ Scraping all manufacturers...\033[0m")
        print("="*60)

        products = scraper.scrape_all_products()

        print("="*60)
        print(f"\033[92m[OK] Total products collected: {len(products)}\033[0m")

        # Stats
        stats = scraper.get_stats()
        print("\nStatistics:")
        print(f"  Manufacturers: {stats['manufacturers_processed']}")
        print(f"  Categories: {stats['categories_processed']}")
        print(f"  Empty categories: {stats['empty_categories']}")
        print(f"  Unique products: {stats['unique_products']}")
        print(f"  Errors: {stats['errors']}")

        # Save
        output_file = args.output or f"afa_products_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(products, f, indent=2, ensure_ascii=False)

        print(f"\n\033[92m[OK] Results saved to: {output_file}\033[0m")

    # Summary
    print()
    print("="*60)
    print(f"\033[92m [OK] COMPLETED\033[0m")
    print("="*60)
    print()

    if error_logger:
        print(f"\033[94mℹ Errors logged to Google Sheets: Scraping_Errors\033[0m")

    print()
