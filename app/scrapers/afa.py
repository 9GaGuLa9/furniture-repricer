"""
AFA Stores Scraper
Парсить ціни з afastores.com через cloudscraper (Cloudflare bypass)
"""

import time
import logging
from typing import List, Dict, Optional
from datetime import datetime
from urllib.parse import urljoin
from bs4 import BeautifulSoup

try:
    import cloudscraper
    CLOUDSCRAPER_AVAILABLE = True
except ImportError:
    CLOUDSCRAPER_AVAILABLE = False
    import requests
    logging.warning("cloudscraper not available, using standard requests")

logger = logging.getLogger("afa")


class AFAScraper:
    """Scraper для afastores.com"""
    
    BASE_URL = "https://www.afastores.com"
    
    def __init__(self, config: dict):
        self.config = config
        self.delay_min = config.get('delay_min', 2.0)
        self.delay_max = config.get('delay_max', 5.0)
        self.retry_attempts = config.get('retry_attempts', 3)
        self.timeout = config.get('timeout', 30)
        
        self.stats = {
            'total_products': 0,
            'unique_products': 0,
            'errors': 0,
            'categories_processed': 0,
            'collections_found': 0
        }
        
        if CLOUDSCRAPER_AVAILABLE:
            self.scraper = cloudscraper.create_scraper(
                browser={
                    'browser': 'chrome',
                    'platform': 'windows',
                    'mobile': False
                },
                delay=10
            )
        else:
            self.scraper = requests.Session()
            self.scraper.headers.update({
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            })
        
        logger.info("AFA Stores scraper initialized")
        logger.info(f"Using {'cloudscraper' if CLOUDSCRAPER_AVAILABLE else 'requests'}")
    
    def _random_delay(self):
        """Затримка між запитами"""
        import random
        time.sleep(random.uniform(self.delay_min, self.delay_max))
    
    def get_collections(self) -> List[str]:
        """Отримати список всіх колекцій (категорій)"""
        logger.info(f"Fetching collections from {self.BASE_URL}")
        
        try:
            resp = self.scraper.get(self.BASE_URL, timeout=self.timeout)
            resp.raise_for_status()
            
            soup = BeautifulSoup(resp.text, "html.parser")
            
            collections = []
            for a in soup.find_all("a", href=True):
                href = a["href"]
                # Знаходимо всі посилання на колекції
                if href.startswith("/collections/") and not href.startswith("/collections/steve-silver"):
                    full_url = urljoin(self.BASE_URL, href)
                    collections.append(full_url)
            
            collections = sorted(set(collections))
            self.stats['collections_found'] = len(collections)
            
            logger.info(f"Found {len(collections)} collections")
            return collections
            
        except Exception as e:
            logger.error(f"Failed to get collections: {e}")
            self.stats['errors'] += 1
            return []
    
    def _extract_product_data(self, product_element) -> Optional[Dict[str, str]]:
        """Витягти дані товару з HTML елемента"""
        try:
            # Знайти посилання на товар
            link = product_element.find('a', class_='product-card__link')
            if not link:
                return None
            
            url = urljoin(self.BASE_URL, link.get('href', ''))
            
            # Знайти назву товару (часто містить SKU)
            title_elem = product_element.find('h3', class_='product-card__title')
            title = title_elem.text.strip() if title_elem else ''
            
            # Витягти SKU з назви або атрибутів
            sku = None
            sku_elem = product_element.find(attrs={'data-sku': True})
            if sku_elem:
                sku = sku_elem.get('data-sku')
            elif title:
                # Спробувати витягти SKU з назви (часто в кінці)
                # Наприклад: "Product Name - SKU123"
                parts = title.split('-')
                if len(parts) > 1:
                    sku = parts[-1].strip()
                else:
                    sku = title.split()[0] if title.split() else None
            
            # Знайти ціну
            price = None
            price_elem = product_element.find('span', class_='price')
            if not price_elem:
                price_elem = product_element.find(class_='product-card__price')
            
            if price_elem:
                price_text = price_elem.text.strip()
                # Видалити $ та інші символи
                price_text = price_text.replace('$', '').replace(',', '').strip()
                try:
                    price = float(price_text)
                except ValueError:
                    pass
            
            if sku and price:
                return {
                    'sku': sku,
                    'price': str(price),
                    'url': url,
                    'title': title
                }
            
            return None
            
        except Exception as e:
            logger.debug(f"Error extracting product data: {e}")
            return None
    
    def scrape_collection(self, collection_url: str, seen_skus: set) -> List[Dict[str, str]]:
        """Парсить всі товари з колекції"""
        collection_name = collection_url.split('/')[-1]
        logger.info(f"Processing collection: {collection_name}")
        
        products = []
        page = 1
        
        while True:
            # URL з пагінацією
            url = f"{collection_url}?page={page}"
            
            try:
                logger.debug(f"  Fetching page {page}...")
                resp = self.scraper.get(url, timeout=self.timeout)
                resp.raise_for_status()
                
                soup = BeautifulSoup(resp.text, "html.parser")
                
                # Знайти всі товари на сторінці
                # Різні сайти використовують різні класи, шукаємо декілька варіантів
                product_elements = soup.find_all('div', class_='product-card')
                if not product_elements:
                    product_elements = soup.find_all('div', class_='product-item')
                if not product_elements:
                    product_elements = soup.find_all('article', class_='product')
                
                if not product_elements:
                    logger.info(f"  Collection {collection_name}: no products on page {page}")
                    break
                
                # Витягти дані з кожного товару
                page_products = 0
                for elem in product_elements:
                    product_data = self._extract_product_data(elem)
                    if product_data:
                        sku = product_data['sku']
                        if sku not in seen_skus:
                            seen_skus.add(sku)
                            products.append(product_data)
                            page_products += 1
                
                logger.info(f"  Page {page}: found {page_products} new products (total: {len(products)})")
                
                # Перевірити чи є наступна сторінка
                next_page = soup.find('a', class_='next')
                if not next_page or not next_page.get('href'):
                    break
                
                page += 1
                self._random_delay()
                
            except Exception as e:
                logger.error(f"Error on page {page} of {collection_name}: {e}")
                self.stats['errors'] += 1
                break
        
        logger.info(f"Collection {collection_name}: collected {len(products)} products")
        self.stats['categories_processed'] += 1
        
        return products
    
    def scrape_all_products(self) -> List[Dict[str, str]]:
        """Парсить всі товари з усіх колекцій"""
        logger.info("="*60)
        logger.info("Starting AFA Stores scraping")
        logger.info("="*60)
        
        # Отримати список колекцій
        collections = self.get_collections()
        
        if not collections:
            logger.error("No collections found!")
            return []
        
        logger.info(f"Will process {len(collections)} collections")
        
        all_products = []
        seen_skus = set()
        
        for idx, collection_url in enumerate(collections, 1):
            logger.info(f"[{idx}/{len(collections)}] Processing collection")
            
            products = self.scrape_collection(collection_url, seen_skus)
            all_products.extend(products)
            
            self.stats['total_products'] = len(all_products)
            self.stats['unique_products'] = len(seen_skus)
            
            # Затримка між колекціями
            time.sleep(3)
        
        logger.info("="*60)
        logger.info(f"Completed: {len(all_products)} products from {len(seen_skus)} unique SKUs")
        logger.info(f"Collections processed: {self.stats['categories_processed']}")
        logger.info(f"Errors: {self.stats['errors']}")
        logger.info("="*60)
        
        return all_products
    
    def get_stats(self) -> dict:
        """Повертає статистику"""
        return self.stats.copy()


def scrape_afa(config: dict) -> List[Dict[str, str]]:
    """Головна функція для парсингу AFA Stores"""
    scraper = AFAScraper(config)
    results = scraper.scrape_all_products()
    return results


if __name__ == "__main__":
    # Тестування
    import logging
    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
    
    if not CLOUDSCRAPER_AVAILABLE:
        print("\n⚠️  WARNING: cloudscraper not installed!")
        print("Install it with: pip install cloudscraper")
        print("Continuing with standard requests (may fail due to Cloudflare)...\n")
    
    test_config = {
        'delay_min': 2.0,
        'delay_max': 4.0,
        'retry_attempts': 3,
        'timeout': 30
    }
    
    print("\n" + "="*60)
    print("ТЕСТ AFA STORES SCRAPER")
    print("="*60 + "\n")
    
    results = scrape_afa(test_config)
    
    print("\n" + "="*60)
    print(f"РЕЗУЛЬТАТ: {len(results)} товарів")
    print("="*60)
    
    if results:
        print("\nПерші 5 товарів:")
        for i, product in enumerate(results[:5], 1):
            print(f"\n{i}. SKU: {product['sku']}")
            print(f"   Title: {product['title'][:50]}...")
            print(f"   Price: ${product['price']}")
            print(f"   URL: {product['url'][:60]}...")
