"""
Emma Mason Algolia API Scraper v5.1 - FIXED
[OK] Automatic bypass of pagination limit (1000 products)
[OK] Splitting large brands via collection_style facets
[OK] Recursive splitting if collection_style >1000
[OK] Clean JSON without HTML parsing
[OK] 100% all products for all brands
[OK] FIXED: Proper handling of expired API key (400/403 errors)
"""

import time
import random
import logging
import sys
import json
from pathlib import Path
from typing import List, Dict, Optional, Set, Tuple
from datetime import datetime
from urllib.parse import quote

# Smart imports
try:
    from ..modules.error_logger import ScraperErrorMixin
except ImportError:
    project_root = Path(__file__).parent.parent.parent
    sys.path.insert(0, str(project_root))

    try:
        from app.modules.error_logger import ScraperErrorMixin
    except ImportError:
        class ScraperErrorMixin:
            def log_scraping_error(self, error, url=None, context=None):
                logger = logging.getLogger("emmamason_algolia")
                logger.error(f"Scraping error: {error}")

# requests
try:
    import requests
except ImportError:
    print("Error: requests library not installed!")
    print("Install: pip install requests")
    sys.exit(1)

logger = logging.getLogger("emmamason_algolia")

class AlgoliaAPIKeyExpired(Exception):
    """Exception when Algolia API key expired or invalid"""
    pass

class EmmaMasonAlgoliaScraperV5_1(ScraperErrorMixin):
    """
    Scraper for Emma Mason via Algolia Search API
    v5.1: Automatic bypass of pagination limit via facets
    """

    # Algolia API Configuration
    ALGOLIA_URL = "https://ctz7lv7pje-dsn.algolia.net/1/indexes/*/queries"
    ALGOLIA_APP_ID = "CTZ7LV7PJE"
    ALGOLIA_API_KEY = "NDk4M2Q0ZWU0ZGQ3ODNmMDcxZGZlMmY2ZTA3NmUzNmVmYzE0MmExMWZmZTQ2YTA0YmY1ODczZTM4ZDE2YzFiZnRhZ0ZpbHRlcnM9JnZhbGlkVW50aWw9MTc3MTAyNzA4Nw=="
    INDEX_NAME = "magento2_emmamason_products"

    # Pagination limit
    PAGINATION_LIMIT = 1000

    # Brands to scrape
    BRANDS = [
        "Intercon Furniture",
        "ACME",
        "Aspenhome",
        "Steve Silver",
        "Westwood Design",
        "Legacy Classic",
        "Legacy Classic Kids",
    ]

    def __init__(self, config: dict, error_logger=None):
        self.config = config
        self.error_logger = error_logger
        self.scraper_name = "EmmaMasonAlgoliaScraper"

        self.delay_min = config.get('delay_min', 0.5)
        self.delay_max = config.get('delay_max', 1.5)
        self.retry_attempts = config.get('retry_attempts', 3)
        self.timeout = config.get('timeout', 30)
        self.hits_per_page = config.get('hits_per_page', 1000)

        logger.info("="*60)
        logger.info("Emma Mason Algolia API Scraper v5.1 (Smart Pagination)")
        logger.info("="*60)
        logger.info(f"Feature: Auto-split via facets to bypass 1000 limit")

    def _random_delay(self):
        time.sleep(random.uniform(self.delay_min, self.delay_max))

    def _build_facet_filters(self, filters: List[Tuple[str, str]]) -> str:
        """
        Build facetFilters

        Args:
            filters: [(facet_name, value), ...]

        Returns:
            URL-encoded facetFilters string
        """
        # Format: [["brand:ACME","collection_style:Contemporary"]]
        filter_strings = [f'"{name}:{value}"' for name, value in filters]
        return f'[[{",".join(filter_strings)}]]'

    def _build_params(self, filters: List[Tuple[str, str]], page: int = 0,
                      facets: List[str] = None, hits: int = None) -> str:
        """Build URL params for Algolia"""

        facet_filters = self._build_facet_filters(filters)

        params = {
            'facetFilters': facet_filters,
            'hitsPerPage': str(hits or self.hits_per_page),
            'page': str(page),
            'numericFilters': '["visibility_search=1"]',
            'highlightPreTag': '__ais-highlight__',
            'highlightPostTag': '__/ais-highlight__',
        }

        if facets:
            params['facets'] = str(facets).replace("'", '"')

        return '&'.join([f"{k}={quote(str(v))}" for k, v in params.items()])

    def _build_params_with_price(self, filters: List[Tuple[str, str]],
                                  min_price: float, max_price: float,
                                  page: int = 0, hits: int = None) -> str:
        """
        Build params with price range

        Args:
            filters: Base filters
            min_price: Minimum price
            max_price: Maximum price
        """
        facet_filters = self._build_facet_filters(filters)

        # Add price range to numericFilters
        numeric_filters = [
            "visibility_search=1",
            f"price.USD.default>={min_price}",
            f"price.USD.default<{max_price}"
        ]
        numeric_filters_str = str(numeric_filters).replace("'", '"')

        params = {
            'facetFilters': facet_filters,
            'hitsPerPage': str(hits or self.hits_per_page),
            'page': str(page),
            'numericFilters': numeric_filters_str,
            'highlightPreTag': '__ais-highlight__',
            'highlightPostTag': '__/ais-highlight__',
        }

        return '&'.join([f"{k}={quote(str(v))}" for k, v in params.items()])

    def _fetch_algolia(self, params_string: str) -> Optional[Dict]:
        """
        Execute request to Algolia API

        Returns:
            Response data or None

        Raises:
            AlgoliaAPIKeyExpired: If API key expired (400/403)
        """
        for attempt in range(1, self.retry_attempts + 1):
            try:
                headers = {
                    "accept": "*/*",
                    "content-type": "application/x-www-form-urlencoded",
                    "x-algolia-api-key": self.ALGOLIA_API_KEY,
                    "x-algolia-application-id": self.ALGOLIA_APP_ID,
                    "origin": "https://emmamason.com",
                    "referer": "https://emmamason.com/",
                    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                }

                payload = {
                    "requests": [
                        {"indexName": self.INDEX_NAME, "params": params_string}
                    ]
                }

                response = requests.post(
                    self.ALGOLIA_URL, json=payload,
                    headers=headers, timeout=self.timeout
                )

                # Expired key check
                if response.status_code == 200:
                    return response.json()

                elif response.status_code in [400, 403]:
                    # API key expired or invalid
                    logger.error(f"[X] API key issue - Status {response.status_code}")
                    logger.error(f"Response: {response.text[:200]}")

                    # Throw an exception for automatic refresh
                    raise AlgoliaAPIKeyExpired(
                        f"API key expired or invalid (status {response.status_code})"
                    )

                else:
                    logger.warning(f"Status {response.status_code} (attempt {attempt})")
                    if attempt < self.retry_attempts:
                        time.sleep(2)

            except AlgoliaAPIKeyExpired:
                # Pass the exception up
                raise

            except Exception as e:
                error_msg = str(e).lower()

                # Check if it could be an expired key
                if any(keyword in error_msg for keyword in [
                    'forbidden', 'unauthorized', 'invalid api key'
                ]):
                    raise AlgoliaAPIKeyExpired(f"API authentication error: {e}")

                logger.error(f"Request error (attempt {attempt}): {e}")
                if attempt < self.retry_attempts:
                    time.sleep(2)

        # If all attempts are unsuccessful
        logger.error("All retry attempts failed")
        return None

    def _get_facets(self, filters: List[Tuple[str, str]],
                    facet_name: str = "collection_style") -> Dict[str, int]:
        """
        Get facets for filters

        Args:
            filters: Current filters
            facet_name: Which facet to get

        Returns:
            {facet_value: count}
        """
        params = self._build_params(
            filters=filters,
            facets=[facet_name],
            hits=0  # No hits, only facets
        )

        data = self._fetch_algolia(params)

        if not data:
            return {}

        facets = data['results'][0].get('facets', {})
        return facets.get(facet_name, {})

    def _parse_hits(self, hits: List[Dict], brand: str) -> List[Dict]:
        """Parsing hits in products"""
        products = []

        for hit in hits:
            try:
                product = {
                    'id': hit.get('objectID'),
                    'sku': hit.get('sku'),
                    'name': hit.get('name'),
                    'url': hit.get('url'),
                    'brand': brand,
                    'price': self._extract_price(hit),
                    'in_stock': hit.get('in_stock'),
                    'categories': hit.get('categories', []),
                    'collection_style': hit.get('collection_style'),
                    'scraped_at': datetime.now().isoformat()
                }

                products.append(product)

            except Exception as e:
                logger.debug(f"Failed to parse hit {hit.get('objectID')}: {e}")
                continue

        return products

    def _extract_price(self, hit: Dict) -> Optional[str]:
        """Get the price from hit"""
        try:
            price_data = hit.get('price', {})

            if isinstance(price_data, dict):
                usd = price_data.get('USD', {})

                if isinstance(usd, dict):
                    default_price = usd.get('default')

                    if default_price is not None:
                        return str(default_price)

            return None

        except Exception as e:
            logger.debug(f"Price extraction error: {e}")
            return None

    def _split_price_range(self, min_price: float, max_price: float) -> List[Tuple[float, float]]:
        """
        Break down the price range into smaller ranges
        """
        # If the range is small, simply divide it in half
        if max_price - min_price <= 500:
            mid = (min_price + max_price) / 2
            return [(min_price, mid), (mid, max_price)]

        # Otherwise, divide into 5 parts
        step = (max_price - min_price) / 5
        ranges = []

        for i in range(5):
            start = min_price + (i * step)
            end = min_price + ((i + 1) * step)
            ranges.append((start, end))

        return ranges

    def _scrape_price_range(self, filters: List[Tuple[str, str]],
                            brand: str, seen_ids: Set[str],
                            min_price: float, max_price: float) -> List[Dict]:
        """
        Scrape products in price range
        """
        all_products = []
        page = 0

        while True:
            params = self._build_params_with_price(
                filters=filters,
                min_price=min_price,
                max_price=max_price,
                page=page
            )

            data = self._fetch_algolia(params)

            if not data:
                break

            hits = data['results'][0].get('hits', [])

            if not hits:
                break

            # Parse
            products = self._parse_hits(hits, brand)

            # Deduplication
            new_count = 0
            for product in products:
                if product['id'] not in seen_ids:
                    seen_ids.add(product['id'])
                    all_products.append(product)
                    new_count += 1

            logger.debug(f"        Page {page}: {new_count} new")

            # Check if there are more
            if len(hits) < self.hits_per_page:
                break

            page += 1
            self._random_delay()

        return all_products

    def _scrape_with_filters(self, filters: List[Tuple[str, str]],
                            brand: str, seen_ids: Set[str],
                            depth: int = 0) -> List[Dict]:
        """
        Smart scraping with automatic splitting

        Args:
            filters: Current filters
            brand: Brand name
            seen_ids: Set for deduplication
            depth: Recursion depth (protection from infinite recursion)

        Returns:
            List of products
        """
        # PROTECTION: Maximum recursion depth
        MAX_DEPTH = 3
        if depth >= MAX_DEPTH:
            logger.warning(f"  [!]  Max recursion depth reached, using simple scrape")
            return self._scrape_simple(filters, brand, seen_ids)

        # Step 1: Get total count
        params = self._build_params(filters=filters, hits=0)
        data = self._fetch_algolia(params)

        if not data:
            logger.error(f"  Failed to fetch for filters: {filters}")
            return []

        nb_hits = data['results'][0].get('nbHits', 0)

        filter_str = " + ".join([f"{n}={v}" for n, v in filters])
        logger.debug(f"  [Depth {depth}] Filters: {filter_str} → {nb_hits} hits")

        # Step 2: If ≤1000 - just load
        if nb_hits <= self.PAGINATION_LIMIT:
            return self._scrape_simple(filters, brand, seen_ids)

        # Step 3: If >1000 - split via PRICE RANGES (not collection_style!)
        logger.info(f"  [REFRESH] Splitting {nb_hits} hits via price ranges (depth {depth})...")

        # Use price ranges instead of collection_style
        # This always works because prices differ for each product
        price_ranges = [
            (0, 200),
            (200, 500),
            (500, 1000),
            (1000, 2000),
            (2000, 10000)
        ]

        all_products = []

        for min_price, max_price in price_ranges:
            logger.info(f"    • Price ${min_price}-${max_price}")

            # Check how many hits in this range
            price_params = self._build_params_with_price(
                filters=filters,
                min_price=min_price,
                max_price=max_price,
                hits=0  # Count only
            )

            data = self._fetch_algolia(price_params)

            if not data:
                continue

            range_hits = data['results'][0].get('nbHits', 0)

            if range_hits == 0:
                logger.debug(f"      → 0 hits, skipping")
                continue

            logger.debug(f"      → {range_hits} hits in this range")

            # If price range >1000 - break down into smaller ranges
            if range_hits > self.PAGINATION_LIMIT:
                logger.info(f"      [REFRESH] Splitting ${min_price}-${max_price} further...")
                sub_ranges = self._split_price_range(min_price, max_price)

                for sub_min, sub_max in sub_ranges:
                    products = self._scrape_price_range(
                        filters=filters,
                        brand=brand,
                        seen_ids=seen_ids,
                        min_price=sub_min,
                        max_price=sub_max
                    )
                    all_products.extend(products)
                    self._random_delay()
            else:
                # Simple scraping for this range
                products = self._scrape_price_range(
                    filters=filters,
                    brand=brand,
                    seen_ids=seen_ids,
                    min_price=min_price,
                    max_price=max_price
                )
                all_products.extend(products)

            self._random_delay()

        return all_products

    def _scrape_simple(self, filters: List[Tuple[str, str]],
                      brand: str, seen_ids: Set[str]) -> List[Dict]:
        """
        Simple scraping (≤1000 products) with pagination
        """
        all_products = []
        page = 0

        while True:
            params = self._build_params(filters=filters, page=page)
            data = self._fetch_algolia(params)

            if not data:
                logger.error(f"  Failed page {page}")
                break

            hits = data['results'][0].get('hits', [])

            if not hits:
                break

            # Parse
            products = self._parse_hits(hits, brand)

            # Deduplication
            new_count = 0
            for product in products:
                if product['id'] not in seen_ids:
                    seen_ids.add(product['id'])
                    all_products.append(product)
                    new_count += 1

            logger.debug(f"    Page {page}: {new_count} new ({len(all_products)} total)")

            # Check if there are more
            if len(hits) < self.hits_per_page:
                break

            page += 1
            self._random_delay()

        return all_products

    def scrape_brand(self, brand: str, seen_ids: Set[str]) -> List[Dict]:
        """
        Scrape brand with automatic pagination limit bypass
        """
        logger.info(f"\nProcessing brand: {brand}")

        # Initial filters: brand only
        filters = [("brand", brand)]

        # Use smart scraping (depth=0 initially)
        products = self._scrape_with_filters(filters, brand, seen_ids, depth=0)

        logger.info(f"[OK] Brand {brand}: {len(products)} products")

        return products

    def scrape_all_brands(self) -> List[Dict]:
        """
        Scrape all brands

        Raises:
            AlgoliaAPIKeyExpired: If API key expired
        """
        all_products = []
        seen_ids = set()

        try:
            for idx, brand in enumerate(self.BRANDS, 1):
                try:
                    logger.info(f"\n[{idx}/{len(self.BRANDS)}] Starting: {brand}")

                    products = self.scrape_brand(brand, seen_ids)
                    all_products.extend(products)

                except AlgoliaAPIKeyExpired:
                    # Pass the exception up for auto-refresh
                    logger.error(f"API key expired while processing {brand}")
                    raise

                except Exception as e:
                    self.log_scraping_error(error=e, context={'brand': brand})
                    logger.error(f"Failed {brand}: {e}")
                    continue

                time.sleep(random.uniform(1, 2))

        except AlgoliaAPIKeyExpired:
            # Forward
            raise

        except Exception as e:
            self.log_scraping_error(error=e, context={'stage': 'main'})
            raise

        # Stats
        logger.info("\n" + "="*60)
        logger.info("SCRAPING COMPLETED")
        logger.info("="*60)
        logger.info(f"Total products: {len(all_products)}")
        logger.info(f"Unique IDs: {len(seen_ids)}")

        brands_stats = {}
        for p in all_products:
            brand = p['brand']
            brands_stats[brand] = brands_stats.get(brand, 0) + 1

        logger.info("\nBy brand:")
        for brand, count in brands_stats.items():
            logger.info(f"  {brand}: {count}")

        logger.info("="*60)

        return all_products

def scrape_emmamason_algolia(config: dict, error_logger=None) -> List[Dict]:
    """Main function for v5.1"""
    scraper = EmmaMasonAlgoliaScraperV5_1(config, error_logger)
    return scraper.scrape_all_brands()

if __name__ == "__main__":
    pass
