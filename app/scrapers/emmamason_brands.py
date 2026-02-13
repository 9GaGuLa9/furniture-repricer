"""
Emma Mason Brands Scraper
    Price parsing - converts "887,84" → 887.84 (comma to dot)
    URL consistency for matching
    Error handling for price conversion
    Removed redundant conditions and unused methods
"""

import time
import random
import logging
from typing import List, Dict, Optional, Set
from datetime import datetime
from bs4 import BeautifulSoup
from ..modules.error_logger import ScraperErrorMixin

# Try importing curl_cffi
try:
    from curl_cffi import requests
    CURL_CFFI_AVAILABLE = True
except ImportError:
    import requests
    CURL_CFFI_AVAILABLE = False
    logging.warning("[!] curl_cffi not found, using standard requests")

logger = logging.getLogger("emmamason_brands")

class EmmaMasonBrandsScraper(ScraperErrorMixin):
    """Scraper for emmamason.com - collects by brands"""

    BASE_URL = "https://emmamason.com"

    # Target brands
    BRANDS = [
        {"name": "ACME", "url": "brands-by-acme~129973.html"},
        {"name": "Westwood Design", "url": "brands-by-westwood-design~937124.html"},
        {"name": "Legacy Classic", "url": "brands-by-legacy-classic~130027.html"},
        {"name": "Legacy Classic", "url": "brands-by-legacy-classic-kids~130028.html"},
        {"name": "Aspenhome Furniture", "url": "brands-by-aspenhome~129985.html"},
        {"name": "Steve Silver", "url": "brands-by-steve-silver~1242933.html"},
        {"name": "Intercon furniture", "url": "brands-intercon-furniture.html"},
        {"name": "by Intercon", "url": "brands-by-intercon~130018.html"},
    ]

    USER_AGENTS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    ]

    def __init__(self, config: dict, error_logger=None):
        self.config = config
        self.error_logger = error_logger
        self.scraper_name = "EmmaMasonScraper"
        self.delay_min = config.get('delay_min', 2.0)
        self.delay_max = config.get('delay_max', 4.0)
        self.retry_attempts = config.get('retry_attempts', 3)
        self.timeout = config.get('timeout', 45)
        self.per_page = 40

        if not CURL_CFFI_AVAILABLE:
            logger.error("curl_cffi not available! Scraper may fail!")
        else:
            logger.info("[OK] curl_cffi available")

        logger.info("="*60)
        logger.info("Emma Mason Brands Scraper v3.0 (Optimized)")
        logger.info("="*60)

    def _random_delay(self):
        """Delay between requests"""
        time.sleep(random.uniform(self.delay_min, self.delay_max))

    def _get_random_user_agent(self) -> str:
        """Random User-Agent"""
        return random.choice(self.USER_AGENTS)

    def _fetch_page(self, url: str, referer: Optional[str] = None) -> Optional[str]:
        """Load page (curl_cffi + impersonate)"""
        for attempt in range(1, self.retry_attempts + 1):
            try:
                headers = {
                    "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "accept-language": "en-US,en;q=0.9",
                    "accept-encoding": "gzip, deflate, br",
                    "user-agent": self._get_random_user_agent(),
                    "cache-control": "no-cache",
                    "pragma": "no-cache",
                }
                if referer:
                    headers["referer"] = referer

                if CURL_CFFI_AVAILABLE:
                    response = requests.get(
                        url,
                        headers=headers,
                        impersonate="chrome123",
                        timeout=self.timeout
                    )
                else:
                    response = requests.get(
                        url,
                        headers=headers,
                        timeout=self.timeout
                    )

                if response.status_code == 200:
                    return response.text

                elif response.status_code == 403:
                    logger.warning(f"403 Forbidden (attempt {attempt}/{self.retry_attempts})")
                    time.sleep(random.uniform(5, 10))

                else:
                    logger.warning(f"Status {response.status_code} (attempt {attempt})")
                    time.sleep(3)

            except Exception as e:
                error_msg = str(e)

                if "timed out" in error_msg.lower() or "timeout" in error_msg.lower():
                    logger.warning(f"Timeout (attempt {attempt}/{self.retry_attempts})")
                    time.sleep(random.uniform(5, 10))
                else:
                    logger.error(f"Request error (attempt {attempt}): {e}")
                    time.sleep(3)

        return None

    def _parse_price(self, price_text: str) -> Optional[str]:
        """
        Emma Mason can return:
            - “$887.84” (period) - OK
            - “$887,84” (comma) - must be replaced with a period!
            - “$887.84” (without $, with comma)
            - “$887.84” (without $, with period)

        Returns:
        String with the price in the format “$887.84” or None
        """
        if not price_text:
            return None

        try:
            # Remove $, spaces
            cleaned = price_text.replace('$', '').replace(' ', '').strip()

            if not cleaned:
                return None

            # Determine separator
            # If there is a comma and NO period, it is the European format.
            if ',' in cleaned and '.' not in cleaned:
                cleaned = cleaned.replace(',', '.')
                logger.debug(f"Converted comma price: {price_text} → {cleaned}")

            elif ',' in cleaned and '.' in cleaned:
                comma_pos = cleaned.index(',')
                dot_pos = cleaned.index('.')

                if dot_pos > comma_pos:
                    # "1,234.56" - American format, remove comma
                    cleaned = cleaned.replace(',', '')
                else:
                    # "1.234,56" - European format
                    cleaned = cleaned.replace('.', '').replace(',', '.')

            # Try converting to check
            try:
                float(cleaned)
                return cleaned
            except ValueError:
                logger.warning(f"Failed to parse price '{price_text}' → '{cleaned}'")
                return None

        except Exception as e:
            logger.error(f"Price parsing error for '{price_text}': {e}")
            return None

    def _extract_products_from_page(self, html: str, brand_name: str) -> List[Dict]:
        """
        Remove products from the brand page

        Returns:
            List[Dict]: [{id, url, price, brand}, ...]
        """
        products = []

        try:
            soup = BeautifulSoup(html, 'html.parser')
            product_items = soup.find_all('div', class_='product-item-info')

            for item in product_items:
                try:
                    # Product ID with price-box data-product-id
                    price_box = item.find('div', {'data-role': 'priceBox'})
                    if not price_box:
                        continue

                    product_id = price_box.get('data-product-id')
                    if not product_id:
                        continue

                    # URL
                    link = item.find('a', class_='product-item-link')
                    url = link['href'] if link else None

                    if not url:
                        continue

                    # Price with correct comma processing
                    price = None
                    price_elem = item.find('span', class_='price')
                    if price_elem:
                        price_text = price_elem.get_text(strip=True)
                        price = self._parse_price(price_text)

                    products.append({
                        'id': product_id,
                        'url': url,
                        'price': price,
                        'brand': brand_name,
                        'scraped_at': datetime.now().isoformat()
                    })

                except Exception as e:
                    logger.debug(f"Failed to parse product: {e}")
                    continue

        except Exception as e:
            logger.error(f"Failed to parse page: {e}")

        return products

    def scrape_brand(self, brand_info: dict, seen_ids: Set[str]) -> List[Dict]:
        """Parsite one brand"""
        brand_name = brand_info['name']
        brand_url = brand_info['url']

        logger.info(f"Processing brand: {brand_name}")

        brand_products = []
        page = 1

        while True:
            # Build URL
            if page == 1:
                url = f"{self.BASE_URL}/{brand_url}?product_list_limit={self.per_page}"
            else:
                url = f"{self.BASE_URL}/{brand_url}?p={page}&product_list_limit={self.per_page}"

            logger.debug(f"  Page {page}: {url}")

            # Download pageDownload page
            html = self._fetch_page(url, referer=self.BASE_URL)

            if not html:
                logger.error(f"  Failed to fetch page {page}")
                break

            # Cloudflare verification
            if "Just a moment" in html or "Checking your browser" in html:
                logger.warning(f"  Cloudflare challenge detected")
                break

            # Parsite goods
            products = self._extract_products_from_page(html, brand_name)

            # Stop only when there are NO products
            if not products:
                logger.info(f"  No products on page {page} - last page")
                break

            # Add unique
            new_count = 0
            duplicate_count = 0

            for product in products:
                product_id = product['id']

                if product_id not in seen_ids:
                    seen_ids.add(product_id)
                    brand_products.append(product)
                    new_count += 1
                else:
                    duplicate_count += 1

            logger.info(f"  Page {page}: {new_count} new, {duplicate_count} duplicates (total: {len(brand_products)})")

            # Protection from infinite loops
            if page >= 100:
                logger.warning(f"  Page limit reached (100)")
                break

            page += 1
            self._random_delay()

        logger.info(f"[OK] Brand {brand_name}: {len(brand_products)} unique products")

        return brand_products

    def scrape_all_brands(self) -> List[Dict]:
        """Parsite all brands"""

        all_products = []
        seen_ids = set()

        try:
            for idx, brand_info in enumerate(self.BRANDS, 1):
                try:
                    products = self.scrape_brand(brand_info, seen_ids)
                    all_products.extend(products)

                except Exception as e:
                    # LOG ERROR
                    self.log_scraping_error(
                        error=e,
                        context={'brand': brand_info['name']}
                    )
                    logger.error(f"Failed {brand_info['name']}: {e}")
                    continue

                time.sleep(3)

        except Exception as e:
            # LOG GLOBAL ERROR
            self.log_scraping_error(error=e, context={'stage': 'main'})
            raise

        # Final statistics
        logger.info("\n" + "="*60)
        logger.info("SCRAPING COMPLETED")
        logger.info("="*60)
        logger.info(f"Total products: {len(all_products)}")
        logger.info(f"Unique IDs: {len(seen_ids)}")

        # Parsite all brands
        brands_stats = {}
        for p in all_products:
            brand = p['brand']
            brands_stats[brand] = brands_stats.get(brand, 0) + 1

        logger.info("\nBy brand:")
        for brand, count in brands_stats.items():
            logger.info(f"  {brand}: {count}")
        logger.info("="*60)

        return all_products


def scrape_emmamason_brands(config: dict) -> List[Dict]:
    """
    Main function for parsing Emma Mason

    USED IN app/main.py:
    from app.scrapers.emmamason_brands import scrape_emmamason_brands
    results = scrape_emmamason_brands(config)

    Returns:
        List[Dict]: [{id, url, price, brand}, ...]
    """
    scraper = EmmaMasonBrandsScraper(config)
    results = scraper.scrape_all_brands()
    return results


if __name__ == "__main__":
    pass