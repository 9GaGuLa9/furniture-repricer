"""
1StopBedrooms Scraper
Парсить ціни з 1stopbedrooms.com через GraphQL API
"""

import requests
import time
import logging
from typing import List, Dict, Optional
from datetime import datetime

logger = logging.getLogger("onestopbedrooms")


class OneStopBedroomsScraper:
    """Scraper для 1stopbedrooms.com"""
    
    BASE_URL = "https://www.1stopbedrooms.com"
    GRAPHQL_URL = "https://www.1stopbedrooms.com/graphql/1"
    
    CATEGORIES = [
        "bedroom", "living", "dining", "office",
        "bar-furniture", "decor", "outdoor",
        "mattresses", "lighting"
    ]
    
    GRAPHQL_QUERY = """
fragment fragmentImage on catalogSearchImage {
    style
    alt
    src
    sources { media srcset }
    classes
}
fragment fragmentDynamicAttribute on catalogSearchPrimaryDynamicAttributeInterface {
    __typename
    type
    ... on catalogSearchPrimaryDynamicAttributeTextType { count label }
    ... on catalogSearchPrimaryDynamicAttributeThumbnailType { additional items { image webId classes } }
    ... on catalogSearchPrimaryDynamicAttributeSwatchThumbnailType { additional items { image webId classes } }
}
fragment fragmentCatalogProduct on catalogSearchProductInterface {
    __typename
    id
    webId
    name
    labels
    brand { id name }
    cat_names
    collection
    sku
    useInCriteoFeed
    slug
    url
    shippingType
    price { finalPrice msrp showMsrp getExcludePromo getSale }
    tags {
    allTags
    primaryDealTag
    primaryDealTagVisibility
    secondaryTag
    secondaryTagVisibility
    tertiaryTag
    tertiaryTagVisibility
    __typename
    }
    couponData { discount code }
    images { mainImage { ...fragmentImage } }
    reviews { number rating }
    mattressData { comfort height type top_type label }
    ... on catalogSearchProductDynamicItem {
        dynamicAttribute { ...fragmentDynamicAttribute }
        secondaryDynamicAttribute { ...fragmentDynamicAttribute }
    }
    freewg
}
query getListingData($slug: String!, $request: catalogSearchFilterInput, $zipcode: String) {
    listing {
        listingCategory(slug: $slug, request: $request, zipcode: $zipcode) {
        itemsCount
        perPage
        pages
        page
        header: title
        items {
            ...fragmentCatalogProduct
            ... on catalogSearchProductDynamicItem { items { ...fragmentCatalogProduct } }
        }
        }
    }
}
"""
    
    def __init__(self, config: dict):
        self.config = config
        self.delay_min = config.get('delay_min', 1.0)
        self.delay_max = config.get('delay_max', 3.0)
        self.retry_attempts = config.get('retry_attempts', 3)
        self.timeout = config.get('timeout', 20)
        
        self.stats = {
            'total_products': 0,
            'unique_products': 0,
            'errors': 0,
            'categories_processed': 0
        }
        
        logger.info("1StopBedrooms scraper initialized")
    
    def _random_delay(self):
        """Затримка між запитами"""
        import random
        time.sleep(random.uniform(self.delay_min, self.delay_max))
    
    def _safe_request(self, payload: dict, headers: dict) -> Optional[dict]:
        """Виконує GraphQL запит з retry логікою"""
        for attempt in range(self.retry_attempts):
            try:
                response = requests.post(
                    self.GRAPHQL_URL,
                    headers=headers,
                    json=payload,
                    timeout=self.timeout
                )
                response.raise_for_status()
                return response.json()
            except Exception as e:
                logger.warning(f"Request error (attempt {attempt+1}/{self.retry_attempts}): {e}")
                if attempt < self.retry_attempts - 1:
                    time.sleep(5)
        
        self.stats['errors'] += 1
        return None
    
    def _extract_products(self, items: List[dict], seen_skus: set) -> List[Dict[str, str]]:
        """Витягує товари зі списку items (Simple, Bundle, Dynamic)"""
        products = []
        
        for item in items:
            typename = item.get("__typename")
            
            # Визначаємо тип товару
            if typename == "catalogSearchProductSimpleItem":
                sub_items = [item]
            elif typename == "catalogSearchProductDynamicItem":
                sub_items = item.get("items") or [item]
            elif typename == "catalogSearchProductBundleItem":
                sub_items = [item]
            else:
                logger.warning(f"Unknown product type: {typename}")
                sub_items = []
            
            # Обробляємо кожен під-товар
            for prod in sub_items:
                if not prod:
                    continue
                
                sku = prod.get("sku")
                if not sku or sku in seen_skus:
                    continue
                
                seen_skus.add(sku)
                
                # Витягуємо дані
                brand = prod.get("brand", {})
                price_data = prod.get("price", {})
                
                products.append({
                    "sku": sku,
                    "brand": brand.get("name") if brand else None,
                    "price": price_data.get("finalPrice"),
                    "url": prod.get("url")
                })
        
        return products
    
    def scrape_category(self, category: str, seen_skus: set) -> List[Dict[str, str]]:
        """Парсить всі товари з категорії"""
        logger.info(f"Processing category: {category}")
        
        category_products = []
        page = 1
        
        headers = {
            "Content-Type": "application/json",
            "Accept": "*/*",
            "Origin": self.BASE_URL,
            "Referer": f"{self.BASE_URL}/{category}",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        
        # Перший запит щоб дізнатись кількість сторінок
        payload = {
            "operationName": "getListingData",
            "query": self.GRAPHQL_QUERY,
            "variables": {
                "slug": category,
                "request": {
                    "sortBy": "RELEVANCE",
                    "perPage": "PER_PAGE_48",
                    "page": 1,
                    "facet": []
                },
                "zipcode": None
            }
        }
        
        data = self._safe_request(payload, headers)
        if not data or "data" not in data:
            logger.error(f"Failed to get data for category {category}")
            return []
        
        listing = data["data"]["listing"]["listingCategory"]
        max_page = listing["pages"]
        items_count = listing["itemsCount"]
        
        logger.info(f"Category {category}: {items_count} items, {max_page} pages")
        
        # Парсимо всі сторінки
        for page in range(1, max_page + 1):
            payload["variables"]["request"]["page"] = page
            
            data = self._safe_request(payload, headers)
            if not data:
                continue
            
            try:
                items = data["data"]["listing"]["listingCategory"]["items"]
                products = self._extract_products(items, seen_skus)
                category_products.extend(products)
                
                logger.info(f"  Page {page}/{max_page}: found {len(products)} new products")
                
            except KeyError as e:
                logger.error(f"Missing data on page {page}: {e}")
                continue
            
            # Затримка між сторінками
            if page < max_page:
                self._random_delay()
        
        logger.info(f"Category {category}: collected {len(category_products)} products")
        print(f"Category {category}: collected {len(category_products)} products")
        self.stats['categories_processed'] += 1
        
        return category_products
    
    def scrape_all_products(self) -> List[Dict[str, str]]:
        logger.info("="*60)
        logger.info("Starting 1StopBedrooms scraping")
        logger.info(f"Categories: {len(self.CATEGORIES)}")
        logger.info("="*60)
        
        all_products = []
        seen_skus = set()
        start_time = datetime.now()
        
        for idx, category in enumerate(self.CATEGORIES, 1):
            logger.info(f"\n{'='*60}")
            logger.info(f"📂 CATEGORY {idx}/{len(self.CATEGORIES)}: {category}")
            logger.info(f"{'='*60}")
            
            products = self.scrape_category(category, seen_skus)
            all_products.extend(products)
            
            # 🆕 ЗАГАЛЬНИЙ ПРОГРЕС після кожної категорії
            elapsed = (datetime.now() - start_time).total_seconds() / 60
            speed = len(all_products) / elapsed if elapsed > 0 else 0
            categories_left = len(self.CATEGORIES) - idx
            eta = (categories_left * elapsed / idx) if idx > 0 else 0
            
            logger.info(f"\n{'='*60}")
            logger.info(f"📊 OVERALL PROGRESS")
            logger.info(f"{'='*60}")
            logger.info(f"Categories: {idx}/{len(self.CATEGORIES)} ({idx/len(self.CATEGORIES)*100:.1f}%)")
            logger.info(f"Total products: {len(all_products)} ({len(seen_skus)} unique)")
            logger.info(f"Speed: {speed:.1f} products/min")
            logger.info(f"Elapsed: {elapsed:.1f} min")
            logger.info(f"ETA: {eta:.1f} min (~{eta/60:.1f} hours)")
            logger.info(f"Errors: {self.stats['errors']}")
            logger.info(f"{'='*60}\n")
            
            self.stats['total_products'] = len(all_products)
            self.stats['unique_products'] = len(seen_skus)
            
            # Затримка між категоріями
            time.sleep(2)
        
        logger.info("="*60)
        logger.info(f"Completed: {len(all_products)} products from {len(seen_skus)} unique SKUs")
        logger.info(f"Categories processed: {self.stats['categories_processed']}")
        logger.info(f"Errors: {self.stats['errors']}")
        logger.info("="*60)
        
        return all_products
    
    def get_stats(self) -> dict:
        """Повертає статистику"""
        return self.stats.copy()


def scrape_onestopbedrooms(config: dict) -> List[Dict[str, str]]:
    """Головна функція для парсингу 1StopBedrooms"""
    scraper = OneStopBedroomsScraper(config)
    results = scraper.scrape_all_products()
    return results


if __name__ == "__main__":
    # Тестування
    import logging
    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
    
    test_config = {
        'delay_min': 1.0,
        'delay_max': 2.0,
        'retry_attempts': 3,
        'timeout': 20
    }
    
    print("\n" + "="*60)
    print("ТЕСТ 1STOPBEDROOMS SCRAPER")
    print("="*60 + "\n")
    
    results = scrape_onestopbedrooms(test_config)
    
    print("\n" + "="*60)
    print(f"РЕЗУЛЬТАТ: {len(results)} товарів")
    print("="*60)
    
    if results:
        print("\nПерші 5 товарів:")
        for i, product in enumerate(results[:5], 1):
            print(f"\n{i}. SKU: {product['sku']}")
            print(f"   Brand: {product['brand']}")
            print(f"   Price: ${product['price']}")
            print(f"   URL: {product['url'][:60]}...")
