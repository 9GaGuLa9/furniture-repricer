"""
Coleman Furniture Scraper
Parses only 3 specific manufacturers via the manufacturer API endpoint
"""

import requests
import time
import logging
from typing import List, Dict, Optional
from datetime import datetime
from ..modules.error_logger import ScraperErrorMixin

logger = logging.getLogger("coleman")

class ColemanScraper(ScraperErrorMixin):
    """Scraper for colemanfurniture.com"""

    BASE_URL = "https://colemanfurniture.com"

    # Hardcode 3 manufacturer IDs
    MANUFACTURERS = {
        "Martin Furniture": 224,
        "Steve Silver": 123,
        "Legacy Classic": 22,
        "Intercon": 196,
        "Westwood": 265,
        "Aspenhome": 237,
        "ACME": 185,
    }

    def __init__(self, config: dict, error_logger=None):
        self.config = config
        self.error_logger = error_logger
        self.scraper_name = "ColemanScraper"
        self.delay_min = config.get('delay_min', 2.0)
        self.delay_max = config.get('delay_max', 5.0)
        self.retry_attempts = config.get('retry_attempts', 3)
        self.timeout = config.get('timeout', 20)

        self.stats = {
            'total_products': 0,
            'unique_products': 0,
            'errors': 0,
            'manufacturers_processed': 0,
            'successful_retries': 0,
            'failed_requests': 0
        }

        # Track failed requests details
        self.failed_requests_list = []

        logger.info("Coleman Furniture scraper initialized (3 manufacturers)")

    def _random_delay(self):
        """Delay between requests"""
        import random
        time.sleep(random.uniform(self.delay_min, self.delay_max))

    def _safe_request(self, url: str, params: dict, headers: dict,
                    manufacturer_name: str = None, page: int = None) -> Optional[dict]:
        """
        Executes a request with retry logic
            IMPROVED: Detailed logging for logs and Google Sheets

        Args:
            url: URL for the request
            params: Query parameters
            headers: HTTP headers
            manufacturer_name: Manufacturer name (for logging)
            page: Page number (for logging)

        Returns:
            JSON dict or None if error
        """
        last_error = None
        last_status_code = None

        # Exponential backoff delays: 10s, 30s, 60s, ...
        retry_delays = [10 * (3 ** i) for i in range(self.retry_attempts)]

        for attempt in range(self.retry_attempts):
            # Increase timeout on retries (1.5x per attempt)
            current_timeout = self.timeout * (1.5 ** attempt)

            try:
                response = requests.get(
                    url,
                    params=params,
                    headers=headers,
                    timeout=current_timeout
                )
                response.raise_for_status()

                # Content-Type verification
                content_type = response.headers.get('Content-Type', '')
                if 'application/json' not in content_type:
                    error_msg = f"Non-JSON response (Content-Type: {content_type})"
                    logger.warning(
                        f"[!]  {error_msg} - Manufacturer: '{manufacturer_name}', "
                        f"Page: {page}, Attempt: {attempt + 1}/{self.retry_attempts}"
                    )

                    if attempt < self.retry_attempts - 1:
                        time.sleep(3)
                        continue
                    return None
                if attempt > 0:
                    logger.info(
                        f"[DONE] Retry SUCCESS - Manufacturer: '{manufacturer_name}', "
                        f"Page: {page} (succeeded on attempt {attempt + 1}/{self.retry_attempts})"
                    )
                    self.stats['successful_retries'] += 1

                return response.json()

            except requests.exceptions.HTTPError as e:
                last_error = e
                status_code = e.response.status_code
                last_status_code = status_code
                if status_code == 404:
                    logger.debug(f"404 Not Found - Manufacturer: '{manufacturer_name}', Page: {page}")
                    return None

                logger.warning(
                    f"[!]  HTTP {status_code} - Manufacturer: '{manufacturer_name}', "
                    f"Page: {page}, Attempt: {attempt + 1}/{self.retry_attempts}"
                )
                self.log_scraping_error(
                    error=e,
                    url=url,
                    context={
                        'method': '_safe_request',
                        'manufacturer': manufacturer_name,
                        'page': page,
                        'attempt': f"{attempt + 1}/{self.retry_attempts}",
                        'status_code': status_code,
                        'params': str(params)[:100]
                    }
                )

            except Exception as e:
                last_error = e
                error_str = str(e)

                logger.warning(
                    f"[!]  Request error - Manufacturer: '{manufacturer_name}', "
                    f"Page: {page}, Attempt: {attempt + 1}/{self.retry_attempts}, "
                    f"Error: {error_str[:100]}"
                )
                self.log_scraping_error(
                    error=e,
                    url=url,
                    context={
                        'method': '_safe_request',
                        'manufacturer': manufacturer_name,
                        'page': page,
                        'attempt': f"{attempt + 1}/{self.retry_attempts}",
                        'error_type': type(e).__name__
                    }
                )

            # Exponential backoff before retry
            if attempt < self.retry_attempts - 1:
                delay = retry_delays[attempt]
                logger.info(
                    f"[...] Waiting {delay}s before retry "
                    f"(attempt {attempt + 2}/{self.retry_attempts})..."
                )
                time.sleep(delay)
        if last_error:
            logger.error(
                f"[X] FINAL FAILURE - Manufacturer: '{manufacturer_name}', Page: {page} - "
                f"gave up after {self.retry_attempts} attempts"
            )

            # Track failed request
            self.failed_requests_list.append({
                'manufacturer': manufacturer_name,
                'page': page,
                'error': str(last_error)[:100],
                'status_code': last_status_code
            })
            self.stats['failed_requests'] += 1

        self.stats['errors'] += 1
        return None

    def _extract_products(self, products_data: List[dict], manufacturer_name: str) -> List[Dict[str, str]]:
        """Extracts product data from the list"""
        products = []

        for product in products_data:
            if not product:
                continue

            sku = product.get("sku")
            if not sku:
                continue

            # Extracting data
            price_data = product.get("price", {})
            manufacturer_data = product.get("manufacturer", {})

            products.append({
                "sku": sku,
                "manufacturer": manufacturer_data.get("title") or manufacturer_name,
                "price": price_data.get("final"),
                "url": product.get("url")
            })

        return products

    def scrape_manufacturer(self, manufacturer_name: str, manufacturer_id: int,
                            seen_skus: set) -> List[Dict[str, str]]:
        """Parses all products from the manufacturer"""
        try:
            logger.info(f"Processing manufacturer: {manufacturer_name} (ID: {manufacturer_id})")

            manufacturer_products = []
            page = 1

            headers = {
                "Accept": "application/json",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36",
                "Referer": f"{self.BASE_URL}/martin-furniture.html"
            }

            # First request to find out the number of pages
            url = f"{self.BASE_URL}/manufacturer/detail/{manufacturer_id}"
            params = {
                "order": "recommended",
                "p": 1,
                "storeid": 1
            }

            data = self._safe_request(url, params, headers,
                            manufacturer_name=manufacturer_name, page=1)

            if not data or "data" not in data:
                logger.error(f"Failed to get data for {manufacturer_name}")
                return []

            # Get info about pagination
            try:
                content = data["data"]["content"]
                pager = content.get("pager", {})

                max_page = pager.get("total", 1)
                items_count = pager.get("items", 0)

                logger.info(f"Manufacturer {manufacturer_name}: {items_count} items, {max_page} pages")

                # Remove products from the first page
                products_data = content.get("products", [])
                products = self._extract_products(products_data, manufacturer_name)

                # Add only unique SKUs
                for product in products:
                    sku = product["sku"]
                    if sku not in seen_skus:
                        seen_skus.add(sku)
                        manufacturer_products.append(product)

                logger.info(f"  Page 1/{max_page}: found {len(products)} products")

            except KeyError as e:
                logger.error(f"Missing data in response: {e}")
                return []

            # We'll parse the rest of the pages (if any)
            for page in range(2, max_page + 1):
                params["p"] = page

                data = self._safe_request(url, params, headers,
                            manufacturer_name=manufacturer_name, page=page)

                if not data:
                    logger.warning(f"Failed to load page {page}, skipping...")
                    # Cooldown after failure to let the server recover
                    logger.info(f"[...] Cooldown 30s after failed page {page}...")
                    time.sleep(30)
                    continue

                try:
                    products_data = data["data"]["content"]["products"]
                    products = self._extract_products(products_data, manufacturer_name)

                    # Add only unique SKU
                    new_count = 0
                    for product in products:
                        sku = product["sku"]
                        if sku not in seen_skus:
                            seen_skus.add(sku)
                            manufacturer_products.append(product)
                            new_count += 1

                    logger.info(f"  Page {page}/{max_page}: found {new_count} new products (total: {len(manufacturer_products)})")

                except KeyError as e:
                    logger.error(f"Missing data on page {page}: {e}")
                    continue

                # Delay between pages
                if page < max_page:
                    self._random_delay()

            logger.info(f"Manufacturer {manufacturer_name}: collected {len(manufacturer_products)} unique products")
            self.stats['manufacturers_processed'] += 1

            return manufacturer_products

        except Exception as e:
            # ADD: Log error with context
            self.log_scraping_error(
                error=e,
                context={
                    'manufacturer': manufacturer_name,
                    'products_scraped': len(products)
                }
            )
            # You can continue with the next manufacturer
            logger.error(f"Failed to scrape {manufacturer_name}: {e}")

    def _print_scraping_summary(self, products: List[Dict[str, str]], seen_skus: set):
        """
        Print detailed scraping statistics
            Shows successful retries, failed requests, detailed analysis

        Args:
            products: List of all collected products
            seen_skus: Set of unique SKUs
        """
        logger.info("")
        logger.info("="*70)
        logger.info("COLEMAN FURNITURE SCRAPER SUMMARY")
        logger.info("="*70)

        # Main statistics
        logger.info(f"[DATA] STATISTICS:")
        logger.info(f"   Manufacturers processed: {self.stats['manufacturers_processed']}/{len(self.MANUFACTURERS)}")
        logger.info(f"   Total products: {len(products)}")
        logger.info(f"   Unique SKUs: {len(seen_skus)}")

        logger.info("")
        logger.info(f"[RETRY] RETRIES:")
        logger.info(f"   Total errors: {self.stats['errors']}")
        logger.info(f"   Successful retries: {self.stats['successful_retries']}")
        logger.info(f"   Failed requests: {self.stats['failed_requests']}")
        if self.stats['errors'] > 0:
            success_rate = (self.stats['successful_retries'] / self.stats['errors']) * 100
            logger.info(f"   Retry success rate: {success_rate:.1f}%")
        if self.failed_requests_list:
            logger.warning("")
            logger.warning(f"[!]  FAILED REQUESTS ({len(self.failed_requests_list)}):")

            # Show first 10
            for i, fr in enumerate(self.failed_requests_list[:10], 1):
                status = f"HTTP {fr['status_code']}" if fr['status_code'] else "Error"
                logger.warning(
                    f"   {i}. '{fr['manufacturer']}' page {fr['page']} - "
                    f"{status}: {fr['error']}"
                )

            if len(self.failed_requests_list) > 10:
                remaining = len(self.failed_requests_list) - 10
                logger.warning(f"   ... and {remaining} more failed requests")

            logger.warning("")
            logger.warning("[i] TIP: Check 'Scraping_Errors' sheet in Google Sheets for full details")
            logger.warning("[i] TIP: Use grep 'FINAL FAILURE' in logs to see all failed requests")
        else:
            logger.info("")
            logger.info("[DONE] No failed requests - all retries successful!")

        logger.info("="*70)

    def scrape_all_products(self) -> List[Dict[str, str]]:
        """Parses all products from 3 manufacturers"""
        try:
            logger.info("="*60)
            logger.info("Starting Coleman Furniture scraping")
            logger.info(f"Manufacturers: {list(self.MANUFACTURERS.keys())}")
            logger.info("="*60)

            all_products = []
            seen_skus = set()

            for manufacturer_name, manufacturer_id in self.MANUFACTURERS.items():
                logger.info(f"\nProcessing: {manufacturer_name}")

                products = self.scrape_manufacturer(manufacturer_name, manufacturer_id, seen_skus)
                all_products.extend(products)

                self.stats['total_products'] = len(all_products)
                self.stats['unique_products'] = len(seen_skus)

                # Delay between manufacturers
                time.sleep(2)

            self._print_scraping_summary(all_products, seen_skus)

            return all_products
        except Exception as e:
            self.log_scraping_error(
                error=e,
                context={'stage': 'main_scraping'}
            )
            raise  # Re-raise so that main.py knows about the error

    def get_stats(self) -> dict:
        """Returns statistics"""
        return self.stats.copy()

def scrape_coleman(config: dict, error_logger=None) -> List[Dict[str, str]]:
    """Main function for parsing Coleman Furniture"""
    scraper = ColemanScraper(config, error_logger=error_logger)
    results = scraper.scrape_all_products()
    return results

if __name__ == "__main__":
    pass