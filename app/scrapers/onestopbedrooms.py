"""
1StopBedrooms Scraper - BRAND-BASED VERSION (OPTIMIZED!)
Парсить ціни з 1stopbedrooms.com через GraphQL API по конкретних виробниках
НАБАГАТО ШВИДШЕ ніж по категоріях - ~5-10 хвилин замість 30-40!
"""

import requests
import time
import logging
from typing import List, Dict, Optional
from datetime import datetime
from ..modules.error_logger import ScraperErrorMixin

logger = logging.getLogger("onestopbedrooms")


class OneStopBedroomsScraper(ScraperErrorMixin):
    """Scraper для 1stopbedrooms.com - збирає по виробниках"""
    
    BASE_URL = "https://www.1stopbedrooms.com"
    GRAPHQL_URL = "https://www.1stopbedrooms.com/graphql/1"
    
    # ✅ Цільові виробники (ті самі що в Coleman і AFA)
    BRANDS = [
        {"name": "Steve Silver", "slug": "brand/steve-silver"},
        {"name": "Martin Furniture", "slug": "brand/martin-furniture"},
        {"name": "Legacy Classic", "slug": "brand/legacy-classic"},
        {"name": "Aspenhome", "slug": "brand/aspenhome"},
        {"name": "ACME", "slug": "brand/acme"},
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
    outOfStock
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
        topSellerProducts(categorySlug: $slug) {
            webId
            title
            brand { name }
            url
            slug
            labels
            outOfStock
            price { price regularPrice finalPrice msrp showMsrp }
            reviews { number rating }
            images {
                mainImage {
                    style
                    alt
                    src
                    sources { media srcset }
                    classes
                }
            }
        }
    }
}
"""
    
    def __init__(self, config: dict, error_logger=None):
        self.config = config
        self.error_logger = error_logger
        self.scraper_name = "OneStopBedroomsScraper"
        self.delay_min = config.get('delay_min', 1.0)
        self.delay_max = config.get('delay_max', 3.0)
        self.retry_attempts = config.get('retry_attempts', 3)
        self.timeout = config.get('timeout', 20)
        
        self.stats = {
            'total_products': 0,
            'unique_products': 0,
            'errors': 0,
            'brands_processed': 0
        }
        
        logger.info("1StopBedrooms scraper initialized (brand-based - FAST!)")
    
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
        """Витягує товари зі списку items"""
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
                logger.debug(f"Unknown product type: {typename}")
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
    
    def scrape_brand(self, brand_info: dict, seen_skus: set) -> List[Dict[str, str]]:
        """Парсить всі товари одного виробника"""
        brand_name = brand_info["name"]
        brand_slug = brand_info["slug"]
        
        logger.info(f"Processing brand: {brand_name} ({brand_slug})")
        
        brand_products = []
        page = 1
        
        headers = {
            "Content-Type": "application/json",
            "Accept": "*/*",
            "Origin": self.BASE_URL,
            "Referer": f"{self.BASE_URL}/{brand_slug}",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        
        # Перший запит щоб дізнатись кількість сторінок
        payload = {
            "operationName": "getListingData",
            "query": self.GRAPHQL_QUERY,
            "variables": {
                "slug": brand_slug,
                "request": {
                    "sortBy": "RELEVANCE",
                    "perPage": "PER_PAGE_48",
                    "page": 1,
                    "facet": []
                },
                "zipcode": "11229"  # Можна залишити або змінити
            }
        }
        
        data = self._safe_request(payload, headers)
        if not data or "data" not in data:
            logger.error(f"Failed to get data for brand {brand_name}")
            return []
        
        try:
            listing = data["data"]["listing"]["listingCategory"]
            max_page = listing["pages"]
            items_count = listing["itemsCount"]
            
            logger.info(f"Brand {brand_name}: {items_count} items, {max_page} pages")
            
            # Витягти товари з першої сторінки
            items = listing.get("items", [])
            products = self._extract_products(items, seen_skus)
            brand_products.extend(products)
            
            logger.info(f"  Page 1/{max_page}: found {len(products)} new products (total: {len(brand_products)})")
            
        except KeyError as e:
            logger.error(f"Missing data in response: {e}")
            return []
        
        # Парсимо решту сторінок
        for page in range(2, max_page + 1):
            payload["variables"]["request"]["page"] = page
            
            data = self._safe_request(payload, headers)
            if not data:
                logger.warning(f"Failed to load page {page}, skipping...")
                continue
            
            try:
                items = data["data"]["listing"]["listingCategory"]["items"]
                products = self._extract_products(items, seen_skus)
                brand_products.extend(products)
                
                logger.info(f"  Page {page}/{max_page}: found {len(products)} new products (total: {len(brand_products)})")
                
            except KeyError as e:
                logger.error(f"Missing data on page {page}: {e}")
                continue
            
            # Затримка між сторінками
            if page < max_page:
                self._random_delay()
        
        logger.info(f"Brand {brand_name}: collected {len(brand_products)} unique products")
        self.stats['brands_processed'] += 1
        
        return brand_products
    
    def scrape_all_products(self) -> List[Dict[str, str]]:
        """Парсить всі товари"""
        
        all_products = []
        seen_skus = set()
        
        try:
            for idx, brand_info in enumerate(self.BRANDS, 1):
                try:
                    products = self.scrape_brand(brand_info, seen_skus)
                    all_products.extend(products)
                    
                except Exception as e:
                    # ✅ LOG ERROR
                    self.log_scraping_error(
                        error=e,
                        context={'brand': brand_info['name']}
                    )
                    logger.error(f"Failed {brand_info['name']}: {e}")
                    continue
                
                time.sleep(2)
        
        except Exception as e:
            # ✅ LOG GLOBAL ERROR
            self.log_scraping_error(error=e, context={'stage': 'main'})
            raise
        
        return all_products
    
    def get_stats(self) -> dict:
        """Повертає статистику"""
        return self.stats.copy()


def scrape_onestopbedrooms(config: dict, error_logger=None) -> List[Dict[str, str]]:
    """Головна функція для парсингу 1StopBedrooms"""
    scraper = OneStopBedroomsScraper(config, error_logger=error_logger)
    results = scraper.scrape_all_products()
    return results


# if __name__ == "__main__":
#     # Тестування
#     import logging
#     logging.basicConfig(
#         level=logging.INFO,
#         format='%(asctime)s | %(levelname)-8s | %(message)s',
#         datefmt='%H:%M:%S'
#     )
    
#     test_config = {
#         'delay_min': 1.0,
#         'delay_max': 2.0,
#         'retry_attempts': 3,
#         'timeout': 20
#     }
    
#     print("\n" + "="*60)
#     print("ТЕСТ 1STOPBEDROOMS SCRAPER (BRAND-BASED - FAST!)")
#     print("="*60 + "\n")
    
#     results = scrape_onestopbedrooms(test_config)
    
#     print("\n" + "="*60)
#     print(f"РЕЗУЛЬТАТ: {len(results)} товарів")
#     print("="*60)
    
#     if results:
#         # Показати статистику по виробниках
#         brands = {}
#         for product in results:
#             brand = product['brand']
#             if brand:
#                 brands[brand] = brands.get(brand, 0) + 1
        
#         print("\nПо виробниках:")
#         for brand, count in sorted(brands.items()):
#             print(f"  {brand}: {count} товарів")
        
#         print("\nПерші 5 товарів:")
#         for i, product in enumerate(results[:5], 1):
#             print(f"\n{i}. SKU: {product['sku']}")
#             print(f"   Brand: {product['brand']}")
#             print(f"   Price: ${product['price']}")
#             print(f"   URL: {product['url'][:60]}...")
#     else:
#         print("\n❌ Немає результатів")
    
#     print("\n" + "="*60)
