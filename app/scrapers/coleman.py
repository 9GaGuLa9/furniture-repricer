"""
Coleman Furniture Scraper
Парсить ціни з colemanfurniture.com через REST API
"""

import requests
import time
import re
import logging
from typing import List, Dict, Optional
from datetime import datetime

logger = logging.getLogger("coleman")


class ColemanScraper:
    """Scraper для colemanfurniture.com"""
    
    BASE_URL = "https://colemanfurniture.com"
    HEADER_API = "https://colemanfurniture.com/api/v2/header?storeid=1"
    
    def __init__(self, config: dict):
        self.config = config
        self.delay_min = config.get('delay_min', 0.5)
        self.delay_max = config.get('delay_max', 2.0)
        self.retry_attempts = config.get('retry_attempts', 3)
        self.timeout = config.get('timeout', 20)
        
        self.category_ids = {}
        self.stats = {
            'total_products': 0,
            'unique_products': 0,
            'errors': 0,
            'categories_processed': 0
        }
        
        logger.info("Coleman Furniture scraper initialized")
        self._load_category_ids()
    
    def _load_category_ids(self):
        """Завантажити ID категорій з API"""
        try:
            logger.info("Loading category IDs...")
            response = requests.get(self.HEADER_API, timeout=self.timeout)
            response.raise_for_status()
            data = response.json()
            
            header = data.get("data", data).get("header", {})
            menu_data = header.get("menu", [])
            
            self.category_ids = self._extract_ids(menu_data)
            logger.info(f"Loaded {len(self.category_ids)} categories")
            
        except Exception as e:
            logger.error(f"Failed to load category IDs: {e}")
            self.category_ids = {}
    
    def _extract_ids(self, menu: List[dict]) -> dict:
        """Рекурсивно витягує ID категорій з меню"""
        ids = {}
        
        for item in menu:
            # Пропускаємо Brands та інші непотрібні розділи
            if item.get("title") == "Brands" or item.get("menuType") == "raw":
                continue
            
            # Обробляємо підменю
            if "subMenu" in item and item["subMenu"]:
                for sub in item["subMenu"]:
                    route = sub.get("route", "")
                    match = re.search(r"id/(\d+)", route)
                    if match:
                        ids[sub.get("title")] = int(match.group(1))
                    
                    # Рекурсивно обробляємо вкладені підменю
                    ids.update(self._extract_ids([sub]))
        
        return ids
    
    def _random_delay(self):
        """Затримка між запитами"""
        import random
        time.sleep(random.uniform(self.delay_min, self.delay_max))
    
    def scrape_category(self, category_id: int, category_name: str, 
                       seen_skus: set) -> List[Dict[str, str]]:
        """Парсить всі товари з категорії"""
        logger.info(f"Processing category: {category_name} (ID: {category_id})")
        
        products = []
        page = 1
        
        headers = {
            'Accept': 'application/json',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        while True:
            url = f"{self.BASE_URL}/catalog/category/view/id/{category_id}"
            params = {
                "order": "recommended",
                "p": page,
                "storeid": 1
            }
            
            try:
                response = requests.get(url, params=params, headers=headers, 
                                       timeout=self.timeout)
                response.raise_for_status()
                
                # Перевірка Content-Type
                content_type = response.headers.get('Content-Type', '')
                if 'application/json' not in content_type:
                    logger.warning(f"Non-JSON response for {category_name} page {page}")
                    break
                
                data = response.json()
                
                # Перевірка наявності товарів
                page_products = data.get("data", {}).get("content", {}).get("products", [])
                
                if not page_products:
                    logger.info(f"  Category {category_name}: collected {len(products)} products from {page-1} pages")
                    break
                
                # Витягуємо дані товарів
                for product in page_products:
                    sku = product.get("sku")
                    
                    # Перевірка на дублікати
                    if not sku or sku in seen_skus:
                        continue
                    
                    seen_skus.add(sku)
                    
                    # Витягуємо дані
                    manufacturer = product.get("manufacturer", {})
                    price_data = product.get("price", {})
                    
                    product_data = {
                        "sku": sku,
                        "manufacturer": manufacturer.get("title") if manufacturer else None,
                        "price": price_data.get("final"),
                        "url": product.get("url"),
                        "category_name": category_name,
                        "category_id": category_id
                    }
                    
                    products.append(product_data)
                
                logger.info(f"  Page {page}: found {len(page_products)} products (total: {len(products)})")
                
                page += 1
                self._random_delay()
                
            except requests.exceptions.HTTPError as e:
                if e.response.status_code == 404:
                    logger.info(f"  Category {category_name}: no more pages")
                    break
                else:
                    logger.error(f"HTTP error on page {page}: {e}")
                    self.stats['errors'] += 1
                    break
            except Exception as e:
                logger.error(f"Error on page {page} of {category_name}: {e}")
                self.stats['errors'] += 1
                break
        
        logger.info(f"Category {category_name}: collected {len(products)} products")
        self.stats['categories_processed'] += 1
        
        return products
    
    def scrape_all_products(self) -> List[Dict[str, str]]:
        logger.info("="*60)
        logger.info("Starting Coleman Furniture scraping")
        logger.info(f"Categories: {len(self.category_ids)}")
        logger.info("="*60)
        
        if not self.category_ids:
            logger.error("No categories loaded!")
            return []
        
        all_products = []
        seen_skus = set()
        start_time = datetime.now()
        last_progress_count = 0
        
        for idx, (category_name, category_id) in enumerate(self.category_ids.items(), 1):
            logger.info(f"\n{'='*60}")
            logger.info(f"📂 [{idx}/{len(self.category_ids)}] {category_name}")
            logger.info(f"{'='*60}")
            
            products = self.scrape_category(category_id, category_name, seen_skus)
            all_products.extend(products)
            
            self.stats['total_products'] = len(all_products)
            self.stats['unique_products'] = len(seen_skus)
            
            # 🆕 ПРОГРЕС кожні 1000 товарів (або після кожної категорії)
            if len(all_products) - last_progress_count >= 1000 or idx % 5 == 0:
                elapsed = (datetime.now() - start_time).total_seconds() / 60
                speed = len(all_products) / elapsed if elapsed > 0 else 0
                
                # Оцінка скільки ще категорій
                categories_left = len(self.category_ids) - idx
                avg_per_category = len(all_products) / idx if idx > 0 else 0
                estimated_remaining = categories_left * avg_per_category
                eta = estimated_remaining / speed if speed > 0 else 0
                
                logger.info(f"\n{'🔥'*30}")
                logger.info(f"📊 COLEMAN PROGRESS")
                logger.info(f"{'🔥'*30}")
                logger.info(f"Categories: {idx}/{len(self.category_ids)} ({idx/len(self.category_ids)*100:.1f}%)")
                logger.info(f"Products: {len(all_products):,} ({len(seen_skus):,} unique)")
                logger.info(f"Speed: {speed:.1f} products/min")
                logger.info(f"Elapsed: {elapsed:.1f} min ({elapsed/60:.1f} hours)")
                logger.info(f"ETA: {eta:.1f} min (~{eta/60:.1f} hours)")
                logger.info(f"Errors: {self.stats['errors']}")
                logger.info(f"{'🔥'*30}\n")
                
                last_progress_count = len(all_products)
            
            # Затримка між категоріями
            time.sleep(1)
        
        logger.info("="*60)
        logger.info(f"Completed: {len(all_products)} products from {len(seen_skus)} unique SKUs")
        logger.info(f"Categories processed: {self.stats['categories_processed']}")
        logger.info(f"Errors: {self.stats['errors']}")
        logger.info("="*60)
        
        return all_products

    def remove_duplicates(self, products: List[dict]) -> List[dict]:
        """Видаляє дублікати по SKU"""
        seen_skus = set()
        unique_products = []
        duplicates_count = 0
        
        for product in products:
            sku = product.get("sku")
            if sku and sku not in seen_skus:
                seen_skus.add(sku)
                unique_products.append(product)
            elif sku:
                duplicates_count += 1
        
        logger.info(f"Removed {duplicates_count} duplicates")
        return unique_products
    
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
    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
    
    test_config = {
        'delay_min': 0.5,
        'delay_max': 1.5,
        'retry_attempts': 3,
        'timeout': 20
    }
    
    print("\n" + "="*60)
    print("ТЕСТ COLEMAN FURNITURE SCRAPER")
    print("="*60 + "\n")
    
    results = scrape_coleman(test_config)
    
    print("\n" + "="*60)
    print(f"РЕЗУЛЬТАТ: {len(results)} товарів")
    print("="*60)
    
    if results:
        print("\nПерші 5 товарів:")
        for i, product in enumerate(results[:5], 1):
            print(f"\n{i}. SKU: {product['sku']}")
            print(f"   Manufacturer: {product['manufacturer']}")
            print(f"   Price: ${product['price']}")
            print(f"   Category: {product['category_name']}")
            print(f"   URL: {product['url'][:60]}...")
