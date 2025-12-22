"""
Coleman Furniture Scraper - FIXED VERSION
Парсить тільки 3 конкретних виробників через manufacturer API endpoint
"""

import requests
import time
import logging
from typing import List, Dict, Optional
from datetime import datetime

logger = logging.getLogger("coleman")


class ColemanScraper:
    """Scraper для colemanfurniture.com - Тільки 3 виробників"""
    
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
    
    def __init__(self, config: dict):
        self.config = config
        self.delay_min = config.get('delay_min', 0.5)
        self.delay_max = config.get('delay_max', 2.0)
        self.retry_attempts = config.get('retry_attempts', 3)
        self.timeout = config.get('timeout', 20)
        
        self.stats = {
            'total_products': 0,
            'unique_products': 0,
            'errors': 0,
            'manufacturers_processed': 0
        }
        
        logger.info("Coleman Furniture scraper initialized (3 manufacturers)")
    
    def _random_delay(self):
        """Затримка між запитами"""
        import random
        time.sleep(random.uniform(self.delay_min, self.delay_max))
    
    def _safe_request(self, url: str, params: dict, headers: dict) -> Optional[dict]:
        """Виконує запит з retry логікою"""
        for attempt in range(self.retry_attempts):
            try:
                response = requests.get(
                    url,
                    params=params,
                    headers=headers,
                    timeout=self.timeout
                )
                response.raise_for_status()
                
                # Перевірка Content-Type
                content_type = response.headers.get('Content-Type', '')
                if 'application/json' not in content_type:
                    logger.warning(f"Non-JSON response (attempt {attempt+1})")
                    if attempt < self.retry_attempts - 1:
                        time.sleep(3)
                        continue
                    return None
                
                return response.json()
                
            except requests.exceptions.HTTPError as e:
                if e.response.status_code == 404:
                    logger.debug(f"404 Not Found")
                    return None
                logger.warning(f"HTTP error (attempt {attempt+1}/{self.retry_attempts}): {e}")
            except Exception as e:
                logger.warning(f"Request error (attempt {attempt+1}/{self.retry_attempts}): {e}")
            
            if attempt < self.retry_attempts - 1:
                time.sleep(5)
        
        self.stats['errors'] += 1
        return None
    
    def _extract_products(self, products_data: List[dict], manufacturer_name: str) -> List[Dict[str, str]]:
        """Витягує дані товарів зі списку"""
        products = []
        
        for product in products_data:
            if not product:
                continue
            
            sku = product.get("sku")
            if not sku:
                continue
            
            # Витягуємо дані
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
        """Парсить всі товари виробника"""
        logger.info(f"Processing manufacturer: {manufacturer_name} (ID: {manufacturer_id})")
        
        manufacturer_products = []
        page = 1
        
        headers = {
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36",
            "Referer": f"{self.BASE_URL}/martin-furniture.html"
        }
        
        # Перший запит щоб дізнатись кількість сторінок
        url = f"{self.BASE_URL}/manufacturer/detail/{manufacturer_id}"
        params = {
            "order": "recommended",
            "p": 1,
            "storeid": 1
        }
        
        data = self._safe_request(url, params, headers)
        if not data or "data" not in data:
            logger.error(f"Failed to get data for {manufacturer_name}")
            return []
        
        # Отримати інфо про пагінацію
        try:
            content = data["data"]["content"]
            pager = content.get("pager", {})
            
            max_page = pager.get("total", 1)
            items_count = pager.get("items", 0)
            
            logger.info(f"Manufacturer {manufacturer_name}: {items_count} items, {max_page} pages")
            
            # Витягти товари з першої сторінки
            products_data = content.get("products", [])
            products = self._extract_products(products_data, manufacturer_name)
            
            # Додати тільки унікальні SKU
            for product in products:
                sku = product["sku"]
                if sku not in seen_skus:
                    seen_skus.add(sku)
                    manufacturer_products.append(product)
            
            logger.info(f"  Page 1/{max_page}: found {len(products)} products")
            
        except KeyError as e:
            logger.error(f"Missing data in response: {e}")
            return []
        
        # Парсимо решту сторінок (якщо є)
        for page in range(2, max_page + 1):
            params["p"] = page
            
            data = self._safe_request(url, params, headers)
            if not data:
                logger.warning(f"Failed to load page {page}, skipping...")
                continue
            
            try:
                products_data = data["data"]["content"]["products"]
                products = self._extract_products(products_data, manufacturer_name)
                
                # Додати тільки унікальні SKU
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
            
            # Затримка між сторінками
            if page < max_page:
                self._random_delay()
        
        logger.info(f"Manufacturer {manufacturer_name}: collected {len(manufacturer_products)} unique products")
        self.stats['manufacturers_processed'] += 1
        
        return manufacturer_products
    
    def scrape_all_products(self) -> List[Dict[str, str]]:
        """Парсить всі товари з 3 виробників"""
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
            
            # Затримка між виробниками
            time.sleep(2)
        
        logger.info("="*60)
        logger.info(f"Completed: {len(all_products)} products from {len(seen_skus)} unique SKUs")
        logger.info(f"Manufacturers processed: {self.stats['manufacturers_processed']}")
        logger.info(f"Errors: {self.stats['errors']}")
        logger.info("="*60)
        
        return all_products
    
    def get_stats(self) -> dict:
        """Повертає статистику"""
        return self.stats.copy()


def scrape_coleman(config: dict) -> List[Dict[str, str]]:
    """Головна функція для парсингу Coleman Furniture"""
    scraper = ColemanScraper(config)
    results = scraper.scrape_all_products()
    return results


if __name__ == "__main__":
    # Тестування
    import logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s | %(levelname)-8s | %(message)s',
        datefmt='%H:%M:%S'
    )
    
    test_config = {
        'delay_min': 0.5,
        'delay_max': 1.5,
        'retry_attempts': 3,
        'timeout': 20
    }
    
    print("\n" + "="*60)
    print("ТЕСТ COLEMAN FURNITURE SCRAPER (3 MANUFACTURERS)")
    print("="*60 + "\n")
    
    results = scrape_coleman(test_config)
    
    print("\n" + "="*60)
    print(f"РЕЗУЛЬТАТ: {len(results)} товарів")
    print("="*60)
    
    if results:
        # Показати статистику по виробниках
        manufacturers = {}
        for product in results:
            mfr = product['manufacturer']
            manufacturers[mfr] = manufacturers.get(mfr, 0) + 1
        
        print("\nПо виробниках:")
        for mfr, count in manufacturers.items():
            print(f"  {mfr}: {count} товарів")
        
        print("\nПерші 5 товарів:")
        for i, product in enumerate(results[:5], 1):
            print(f"\n{i}. SKU: {product['sku']}")
            print(f"   Manufacturer: {product['manufacturer']}")
            print(f"   Price: ${product['price']}")
            print(f"   URL: {product['url'][:60]}...")
