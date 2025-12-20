"""
AFA Stores Scraper (Vendor Filter Method)
Парсить ціни з afastores.com через Shopify JSON API
Використовує /products.json?vendor=VendorName - НАБАГАТО ШВИДШЕ!
"""

import requests
import time
import logging
from typing import List, Dict, Optional
from datetime import datetime

try:
    import cloudscraper
    CLOUDSCRAPER_AVAILABLE = True
except ImportError:
    CLOUDSCRAPER_AVAILABLE = False
    logging.warning("cloudscraper not available, using standard requests")

logger = logging.getLogger("afa")


class AFAScraper:
    """Scraper для afastores.com через Shopify API"""
    
    BASE_URL = "https://www.afastores.com"
    
    # Список vendors для парсингу
    DEFAULT_VENDORS = {
        "steve-silver": "Steve Silver",
        "martin-furniture": "Martin Furniture",
        "legacy-classic": "Legacy Classic",
        "coaster": "Coaster",
        "homelegance": "Homelegance",
        "lifestyle": "Lifestyle"
    }
    
    def __init__(self, config: dict):
        self.config = config
        self.delay_min = config.get('delay_min', 1.0)
        self.delay_max = config.get('delay_max', 2.0)
        self.retry_attempts = config.get('retry_attempts', 3)
        self.timeout = config.get('timeout', 30)
        self.test_mode = config.get('test_mode', False)
        
        # Vendors для парсингу (можна override в config)
        self.vendors = config.get('vendors', self.DEFAULT_VENDORS)
        
        self.stats = {
            'total_products': 0,
            'unique_products': 0,
            'errors': 0,
            'vendors_processed': 0
        }
        
        # Вибрати scraper
        if CLOUDSCRAPER_AVAILABLE:
            self.scraper = cloudscraper.create_scraper(
                browser={
                    'browser': 'chrome',
                    'platform': 'windows',
                    'mobile': False
                }
            )
            logger.info("AFA Stores scraper initialized (cloudscraper)")
        else:
            self.scraper = requests.Session()
            self.scraper.headers.update({
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept': 'application/json'
            })
            logger.info("AFA Stores scraper initialized (requests)")
    
    def _random_delay(self):
        """Затримка між запитами"""
        import random
        time.sleep(random.uniform(self.delay_min, self.delay_max))
    
    def fetch_products_by_vendor(self, vendor_name: str, vendor_key: str, 
                                 seen_skus: set) -> List[Dict[str, str]]:
        """
        Парсить всі товари для конкретного vendor через Shopify API
        
        Args:
            vendor_name: Назва vendor в Shopify (напр. "Steve Silver")
            vendor_key: Ключ для статистики (напр. "steve-silver")
            seen_skus: Set для відстеження дублікатів
        
        Returns:
            Список товарів з цього vendor
        """
        logger.info(f"Processing vendor: {vendor_key} ({vendor_name})")
        
        products = []
        page = 1
        limit = 250  # Максимум дозволений Shopify
        
        # TEST MODE: тільки 1 сторінка
        max_pages = 1 if self.test_mode else 999
        
        while page <= max_pages:
            url = f"{self.BASE_URL}/products.json"
            params = {
                'vendor': vendor_name,
                'limit': limit,
                'page': page
            }
            
            try:
                logger.debug(f"  Fetching page {page}...")
                response = self.scraper.get(url, params=params, timeout=self.timeout)
                response.raise_for_status()
                
                data = response.json()
                page_products = data.get('products', [])
                
                if not page_products:
                    logger.info(f"  Page {page} is empty, stopping")
                    break
                
                # Обробити товари
                new_products = 0
                for product in page_products:
                    # Витягти дані з кожного варіанту
                    for variant in product.get('variants', []):
                        sku = variant.get('sku', '').strip()
                        
                        if not sku or sku in seen_skus:
                            continue
                        
                        seen_skus.add(sku)
                        new_products += 1
                        
                        # Зберегти товар
                        products.append({
                            'sku': sku,
                            'price': variant.get('price', ''),
                            'url': f"{self.BASE_URL}/products/{product.get('handle')}",
                            'title': product.get('title', ''),
                            'vendor': product.get('vendor', ''),
                            'product_type': product.get('product_type', ''),
                            'available': variant.get('available', False),
                            'compare_at_price': variant.get('compare_at_price'),
                            'vendor_key': vendor_key
                        })
                
                logger.info(f"  Page {page}: {len(page_products)} products, {new_products} new variants")
                
                # Якщо отримали менше ніж limit - це остання сторінка
                if len(page_products) < limit:
                    logger.info(f"  Received less than {limit} products, this is the last page")
                    break
                
                page += 1
                self._random_delay()
                
            except requests.exceptions.HTTPError as e:
                if e.response.status_code == 404:
                    logger.info(f"  Page {page} not found (404), stopping")
                    break
                else:
                    logger.error(f"HTTP error on page {page}: {e}")
                    self.stats['errors'] += 1
                    break
            except Exception as e:
                logger.error(f"Error on page {page} of {vendor_key}: {e}")
                self.stats['errors'] += 1
                break
        
        logger.info(f"Vendor {vendor_key}: collected {len(products)} products")
        self.stats['vendors_processed'] += 1
        
        return products
    
    def scrape_all_products(self) -> List[Dict[str, str]]:
        """Парсить всі товари з усіх vendors"""
        logger.info("="*60)
        logger.info("Starting AFA Stores scraping (Vendor Filter Method)")
        
        # TEST MODE: тільки 1 vendor
        vendors_to_scrape = self.vendors
        if self.test_mode:
            # Взяти перший vendor
            first_key = list(self.vendors.keys())[0]
            vendors_to_scrape = {first_key: self.vendors[first_key]}
            logger.info(f"TEST MODE: Limited to 1 vendor ({first_key})")
        
        logger.info(f"Vendors: {len(vendors_to_scrape)}")
        logger.info("="*60)
        
        all_products = []
        seen_skus = set()
        
        for vendor_key, vendor_name in vendors_to_scrape.items():
            logger.info(f"[{self.stats['vendors_processed']+1}/{len(vendors_to_scrape)}] Processing: {vendor_key}")
            
            products = self.fetch_products_by_vendor(vendor_name, vendor_key, seen_skus)
            all_products.extend(products)
            
            self.stats['total_products'] = len(all_products)
            self.stats['unique_products'] = len(seen_skus)
            
            # Затримка між vendors
            time.sleep(2)
        
        logger.info("="*60)
        logger.info(f"Completed: {len(all_products)} products from {len(seen_skus)} unique SKUs")
        logger.info(f"Vendors processed: {self.stats['vendors_processed']}")
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


# ============================================================================
# STANDALONE EXECUTION - Детальне тестування з збереженням у файли
# ============================================================================

if __name__ == "__main__":
    import sys
    from pathlib import Path
    import json
    import csv
    
    # Додати project root до path
    project_root = Path(__file__).parent.parent.parent
    sys.path.insert(0, str(project_root))
    
    # Налаштування логування
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s | %(name)-8s | %(levelname)-8s | %(message)s',
        datefmt='%H:%M:%S'
    )
    
    print("\n" + "="*70)
    print("AFA STORES SCRAPER - STANDALONE TEST")
    print("Vendor Filter Method (Shopify API)")
    print("="*70)
    print()
    
    if not CLOUDSCRAPER_AVAILABLE:
        print("⚠️  WARNING: cloudscraper not installed!")
        print("For better Cloudflare bypass: pip install cloudscraper")
        print("Continuing with standard requests...\n")
    
    # Вибір режиму
    print("Choose mode:")
    print("1. Test mode (1 vendor, 1 page) - ШВИДКО ⚡")
    print("2. Full mode (all vendors, all pages) - ПОВІЛЬНО ⏱")
    choice = input("Enter choice [1/2, default=1]: ").strip() or "1"
    
    test_mode = (choice == "1")
    
    # Конфігурація
    test_config = {
        'delay_min': 1.0,
        'delay_max': 2.0,
        'retry_attempts': 3,
        'timeout': 30,
        'test_mode': test_mode
    }
    
    print()
    print("="*70)
    if test_mode:
        print("⚡ TEST MODE: 1 vendor, 1 page (~30-60 seconds)")
    else:
        print("🔥 FULL MODE: All vendors, all pages (~5-10 minutes)")
    print("="*70)
    print()
    
    # Запустити scraper
    start_time = datetime.now()
    results = scrape_afa(test_config)
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()
    
    print()
    print("="*70)
    print("SCRAPING COMPLETED!")
    print("="*70)
    print(f"Duration: {duration:.1f} seconds ({duration/60:.1f} minutes)")
    print(f"Total products: {len(results)}")
    print()
    
    if results:
        # Показати приклади
        print("="*70)
        print("SAMPLE PRODUCTS (First 5):")
        print("="*70)
        for i, product in enumerate(results[:5], 1):
            print(f"\n{i}. SKU: {product['sku']}")
            print(f"   Vendor: {product['vendor']} ({product['vendor_key']})")
            print(f"   Price: ${product['price']}")
            print(f"   Title: {product['title'][:60]}...")
            print(f"   URL: {product['url'][:60]}...")
        
        # Статистика по vendors
        print()
        print("="*70)
        print("BREAKDOWN BY VENDOR:")
        print("="*70)
        vendor_counts = {}
        for product in results:
            vendor = product['vendor_key']
            vendor_counts[vendor] = vendor_counts.get(vendor, 0) + 1
        
        for vendor, count in sorted(vendor_counts.items()):
            print(f"  {vendor}: {count} products")
        
        # Зберегти результати
        save = input("\nSave results to files? [y/N]: ").strip().lower()
        
        if save == 'y':
            output_dir = project_root / "output" / "afa"
            output_dir.mkdir(parents=True, exist_ok=True)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            # JSON
            json_path = output_dir / f"afa_products_{timestamp}.json"
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(results, f, indent=2, ensure_ascii=False)
            print(f"✓ Saved JSON: {json_path}")
            
            # CSV
            csv_path = output_dir / f"afa_products_{timestamp}.csv"
            if results:
                keys = results[0].keys()
                with open(csv_path, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.DictWriter(f, fieldnames=keys)
                    writer.writeheader()
                    writer.writerows(results)
                print(f"✓ Saved CSV: {csv_path}")
            
            print()
            print(f"Files saved to: {output_dir}")
    else:
        print("\n❌ No products found!")
        print("Possible reasons:")
        print("  - Cloudflare blocking (install cloudscraper)")
        print("  - Network issues")
        print("  - Vendor names changed")
    
    print()
    print("="*70)
