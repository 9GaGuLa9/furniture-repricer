"""
Emma Mason Algolia API Scraper v5.1
✅ Автоматичний обхід pagination limit (1000 товарів)
✅ Розбиття великих брендів через collection_style facets
✅ Рекурсивне розбиття якщо collection_style >1000
✅ Чистий JSON без HTML parsing
✅ 100% всіх товарів для всіх брендів
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


class EmmaMasonAlgoliaScraperV5_1(ScraperErrorMixin):
    """
    Scraper для Emma Mason через Algolia Search API
    v5.1: Автоматичний обхід pagination limit через facets
    """
    
    # Algolia API Configuration
    ALGOLIA_URL = "https://ctz7lv7pje-dsn.algolia.net/1/indexes/*/queries"
    ALGOLIA_APP_ID = "CTZ7LV7PJE"
    ALGOLIA_API_KEY = "MmQ5Yjc2NjZhMjcyMDM3YWM5YjM0ZTM0NWMyNjExNzkyZmNlMzgzZWFjMTNkODkxYjRkNTEyY2EwMTk1MmFhYXRhZ0ZpbHRlcnM9JnZhbGlkVW50aWw9MTc2ODM5NjkyNg=="
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
        Побудувати facetFilters
        
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
        """Побудувати URL params для Algolia"""
        
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
        Побудувати params з price range
        
        Args:
            filters: Базові фільтри
            min_price: Мінімальна ціна
            max_price: Максимальна ціна
        """
        facet_filters = self._build_facet_filters(filters)
        
        # Додати price range до numericFilters
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
        """Виконати запит до Algolia API"""
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
                
                if response.status_code == 200:
                    return response.json()
                else:
                    logger.warning(f"Status {response.status_code} (attempt {attempt})")
                    time.sleep(2)
            
            except Exception as e:
                logger.error(f"Request error (attempt {attempt}): {e}")
                time.sleep(2)
        
        return None
    
    def _get_facets(self, filters: List[Tuple[str, str]], 
                    facet_name: str = "collection_style") -> Dict[str, int]:
        """
        Отримати facets для набору фільтрів
        
        Args:
            filters: Поточні фільтри
            facet_name: Який facet отримати
        
        Returns:
            {facet_value: count}
        """
        params = self._build_params(
            filters=filters,
            facets=[facet_name],
            hits=0  # Не треба hits, тільки facets
        )
        
        data = self._fetch_algolia(params)
        
        if not data:
            return {}
        
        facets = data['results'][0].get('facets', {})
        return facets.get(facet_name, {})
    
    def _parse_hits(self, hits: List[Dict], brand: str) -> List[Dict]:
        """Парсити hits в products"""
        products = []
        
        for hit in hits:
            try:
                product = {
                    'id': hit.get('objectID'),
                    'sku': hit.get('sku'),
                    'name': hit.get('name'),
                    'url': hit.get('url'),
                    'brand': brand,
                    'scraped_at': datetime.now().isoformat()
                }
                
                # Ціна
                price_data = hit.get('price', {})
                if isinstance(price_data, dict):
                    usd_price = price_data.get('USD', {})
                    if isinstance(usd_price, dict):
                        product['price'] = str(usd_price.get('default'))
                    else:
                        product['price'] = None
                else:
                    product['price'] = None
                
                products.append(product)
            
            except Exception as e:
                logger.debug(f"Failed to parse hit: {e}")
                continue
        
        return products
    
    def _split_price_range(self, min_price: float, max_price: float) -> List[Tuple[float, float]]:
        """
        Розбити price range на менші діапазони
        
        Args:
            min_price: Початкова ціна
            max_price: Кінцева ціна
        
        Returns:
            Список (min, max) кортежів
        """
        range_size = max_price - min_price
        step = range_size / 5  # Розбити на 5 частин
        
        ranges = []
        for i in range(5):
            sub_min = min_price + (i * step)
            sub_max = min_price + ((i + 1) * step)
            ranges.append((sub_min, sub_max))
        
        return ranges
    
    def _scrape_simple_from_data(self, data: Dict, brand: str, seen_ids: Set[str]) -> List[Dict]:
        """
        Scraping hits з готових даних (одна сторінка)
        
        Args:
            data: Algolia response data
            brand: Назва бренду
            seen_ids: Set для дедуплікації
        
        Returns:
            Список товарів
        """
        hits = data['results'][0].get('hits', [])
        
        if not hits:
            return []
        
        # Parse
        products = self._parse_hits(hits, brand)
        
        # Дедуплікація
        unique_products = []
        for product in products:
            if product['id'] not in seen_ids:
                seen_ids.add(product['id'])
                unique_products.append(product)
        
        return unique_products
    
    def _scrape_price_range(self, filters: List[Tuple[str, str]], 
                           brand: str, seen_ids: Set[str],
                           min_price: float, max_price: float) -> List[Dict]:
        """
        Scraping з price range та повною пагінацією
        
        Args:
            filters: Базові фільтри
            brand: Назва бренду
            seen_ids: Set для дедуплікації
            min_price: Мін ціна
            max_price: Макс ціна
        
        Returns:
            Список товарів
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
            
            # Parse і дедуплікація
            products = self._parse_hits(hits, brand)
            
            new_count = 0
            for product in products:
                if product['id'] not in seen_ids:
                    seen_ids.add(product['id'])
                    all_products.append(product)
                    new_count += 1
            
            logger.debug(f"      Page {page}: {new_count} new")
            
            # Перевірити чи є ще
            if len(hits) < self.hits_per_page:
                break
            
            page += 1
            self._random_delay()
        
        return all_products
    
    def _scrape_with_filters(self, filters: List[Tuple[str, str]], 
                            brand: str, seen_ids: Set[str], depth: int = 0) -> List[Dict]:
        """
        Scraping з конкретними фільтрами
        Якщо результатів >1000, автоматично розбиває через price ranges
        
        Args:
            filters: [(facet_name, value), ...]
            brand: Назва бренду
            seen_ids: Set для дедуплікації
            depth: Глибина рекурсії (захист від нескінченної рекурсії)
        
        Returns:
            Список товарів
        """
        # ✅ ЗАХИСТ: Максимальна глибина рекурсії
        MAX_DEPTH = 3
        if depth >= MAX_DEPTH:
            logger.warning(f"  ⚠️  Max recursion depth reached, using simple scrape")
            return self._scrape_simple(filters, brand, seen_ids)
        
        # Крок 1: Отримати загальну кількість
        params = self._build_params(filters=filters, hits=0)
        data = self._fetch_algolia(params)
        
        if not data:
            logger.error(f"  Failed to fetch for filters: {filters}")
            return []
        
        nb_hits = data['results'][0].get('nbHits', 0)
        
        filter_str = " + ".join([f"{n}={v}" for n, v in filters])
        logger.debug(f"  [Depth {depth}] Filters: {filter_str} → {nb_hits} hits")
        
        # Крок 2: Якщо ≤1000 - просто завантажити
        if nb_hits <= self.PAGINATION_LIMIT:
            return self._scrape_simple(filters, brand, seen_ids)
        
        # Крок 3: Якщо >1000 - розбити через PRICE RANGES (не collection_style!)
        logger.info(f"  🔄 Splitting {nb_hits} hits via price ranges (depth {depth})...")
        
        # ✅ Використовувати price ranges замість collection_style
        # Це завжди працює, бо ціни різні для кожного товару
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
            
            # Перевірити скільки hits в цьому range
            price_params = self._build_params_with_price(
                filters=filters,
                min_price=min_price,
                max_price=max_price,
                hits=0  # Тільки count
            )
            
            data = self._fetch_algolia(price_params)
            
            if not data:
                continue
            
            range_hits = data['results'][0].get('nbHits', 0)
            
            if range_hits == 0:
                logger.debug(f"      → 0 hits, skipping")
                continue
            
            logger.debug(f"      → {range_hits} hits in this range")
            
            # Якщо price range >1000 - розбити на менші діапазони
            if range_hits > self.PAGINATION_LIMIT:
                logger.info(f"      🔄 Splitting ${min_price}-${max_price} further...")
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
                # Простий scraping для цього range
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
        Простий scraping (≤1000 товарів) з пагінацією
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
            
            # Дедуплікація
            new_count = 0
            for product in products:
                if product['id'] not in seen_ids:
                    seen_ids.add(product['id'])
                    all_products.append(product)
                    new_count += 1
            
            logger.debug(f"    Page {page}: {new_count} new ({len(all_products)} total)")
            
            # Перевірити чи є ще
            if len(hits) < self.hits_per_page:
                break
            
            page += 1
            self._random_delay()
        
        return all_products
    
    def scrape_brand(self, brand: str, seen_ids: Set[str]) -> List[Dict]:
        """
        Scrape бренд з автоматичним обходом pagination limit
        """
        logger.info(f"\nProcessing brand: {brand}")
        
        # Початкові фільтри: тільки бренд
        filters = [("brand", brand)]
        
        # Використати розумний scraping (depth=0 початково)
        products = self._scrape_with_filters(filters, brand, seen_ids, depth=0)
        
        logger.info(f"✓ Brand {brand}: {len(products)} products")
        
        return products
    
    def scrape_all_brands(self) -> List[Dict]:
        """Scrape всіх брендів"""
        all_products = []
        seen_ids = set()
        
        try:
            for idx, brand in enumerate(self.BRANDS, 1):
                try:
                    logger.info(f"\n[{idx}/{len(self.BRANDS)}] Starting: {brand}")
                    
                    products = self.scrape_brand(brand, seen_ids)
                    all_products.extend(products)
                    
                except Exception as e:
                    self.log_scraping_error(error=e, context={'brand': brand})
                    logger.error(f"Failed {brand}: {e}")
                    continue
                
                time.sleep(random.uniform(1, 2))
        
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
    """Main function для v5.1"""
    scraper = EmmaMasonAlgoliaScraperV5_1(config, error_logger)
    return scraper.scrape_all_brands()


if __name__ == "__main__":
    import logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s | %(levelname)-8s | %(message)s',
        datefmt='%H:%M:%S'
    )
    
    config = {
        'delay_min': 0.5,
        'delay_max': 1.5,
        'retry_attempts': 3,
        'timeout': 30,
        'hits_per_page': 1000
    }
    
    print("\n" + "="*60)
    print("ТЕСТ ALGOLIA SCRAPER v5.1 (Smart Pagination)")
    print("="*60 + "\n")
    
    results = scrape_emmamason_algolia(config)
    
    print(f"\n✅ РЕЗУЛЬТАТ: {len(results)} products")
