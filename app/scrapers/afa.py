"""
AFA Stores Scraper - CLOUDFLARE BYPASS + CATEGORY-BASED SCRAPING
Використовує cloudscraper для обходу Cloudflare + проходить по категоріях виробників
"""

import time
import logging
import json
from pathlib import Path
from typing import List, Dict, Optional, Set
from datetime import datetime
from ..modules.error_logger import ScraperErrorMixin

try:
    from curl_cffi import requests as curl_requests
    CURL_CFFI_AVAILABLE = True
except ImportError:
    CURL_CFFI_AVAILABLE = False
    try:
        import cloudscraper
        CLOUDSCRAPER_AVAILABLE = True
    except ImportError:
        CLOUDSCRAPER_AVAILABLE = False
        import requests
        logging.error("Neither curl_cffi nor cloudscraper installed! Install: pip install curl-cffi")

logger = logging.getLogger("afa")


class AFAScraper(ScraperErrorMixin):
    """Scraper для afastores.com через Shopify collections - category-based"""

    BASE_URL = "https://www.afastores.com"
    PRODUCTS_PER_PAGE = 30  # AFA показує 30 товарів на сторінку
    
    # Mapping виробників до їх slug для завантаження категорій
    MANUFACTURER_SLUGS = {
        "Steve Silver": "steve-silver",
        "Legacy Classic Furniture": "legacy-classic-furniture",
        "Legacy Classic Kids": "legacy-classic-kids",
        "Martin Furniture": "martin-furniture",
        "ACME Furniture": "acme-furniture",
        "Intercon Furniture": "intercon-furniture",
        "Westwood Design": "westwood-design"
    }

    def __init__(self, config: dict, error_logger=None):
        self.config = config
        self.error_logger = error_logger
        self.scraper_name = "AFAScraper"
        self.delay_min = config.get('delay_min', 1.0)
        self.delay_max = config.get('delay_max', 2.0)
        self.retry_attempts = config.get('retry_attempts', 3)
        self.timeout = config.get('timeout', 30)
        self.proxies = config.get('proxies', None)
        
        self.stats = {
            'total_products': 0,
            'unique_products': 0,
            'errors': 0,
            'manufacturers_processed': 0,
            'categories_processed': 0,
            'empty_categories': 0
        }

        # Завантажити категорії з JSON
        self.manufacturer_categories = self._load_categories()
        
        # Initialize session with best available method
        self.session_type = None
        self.impersonate = None

        if CURL_CFFI_AVAILABLE:
            self.session_type = 'curl_cffi'
            self.impersonate = 'chrome110'
            self.scraper = None
            logger.info(f"AFA Stores scraper initialized with curl_cffi (impersonate={self.impersonate})")

        elif CLOUDSCRAPER_AVAILABLE:
            import cloudscraper
            self.session_type = 'cloudscraper'
            self.scraper = cloudscraper.create_scraper(
                browser={
                    'browser': 'chrome',
                    'platform': 'windows',
                    'mobile': False
                },
                delay=10
            )

            self.scraper.headers.update({
                'Accept': 'application/json, text/plain, */*',
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept-Encoding': 'gzip, deflate, br',
                'Referer': 'https://www.afastores.com/',
                'Origin': 'https://www.afastores.com',
                'DNT': '1',
                'Connection': 'keep-alive',
                'Sec-Fetch-Dest': 'empty',
                'Sec-Fetch-Mode': 'cors',
                'Sec-Fetch-Site': 'same-origin',
                'Cache-Control': 'no-cache',
                'Pragma': 'no-cache'
            })

            logger.info("AFA Stores scraper initialized with cloudscraper")
            self._warm_up_session()

        else:
            import requests
            self.session_type = 'requests'
            self.scraper = requests.Session()
            self.scraper.headers.update({
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            })
            logger.warning("AFA Stores scraper initialized with basic requests - will likely fail!")

    def _load_categories(self) -> dict:
        """Завантажити категорії виробників з JSON файлу"""
        try:
            # Використати helper функцію з app.data
            # Спробувати імпортувати якщо запускається як модуль
            try:
                from ..data import load_manufacturer_categories
                categories = load_manufacturer_categories()
            except (ImportError, ValueError):
                # Fallback - завантажити напряму
                from pathlib import Path
                import json
                
                data_dir = Path(__file__).parent.parent / "data"
                categories_file = data_dir / "manufacturer_categories.json"
                
                if not categories_file.exists():
                    logger.error(f"Categories file not found: {categories_file}")
                    return {}
                
                logger.info(f"Loading categories from: {categories_file}")
                with open(categories_file, 'r', encoding='utf-8') as f:
                    categories = json.load(f)
            
            logger.info(f"✓ Loaded categories for {len(categories)} manufacturers")
            return categories
            
        except Exception as e:
            logger.error(f"Failed to load categories: {e}")
            return {}

    def _warm_up_session(self):
        """Отримує початкові cookies, відвідуючи головну сторінку"""
        if self.session_type == 'curl_cffi':
            logger.debug("Skipping warm-up for curl_cffi (not needed)")
            return

        try:
            logger.info("Warming up session by visiting homepage...")
            response = self.scraper.get(
                self.BASE_URL,
                timeout=self.timeout,
                proxies=self.proxies
            )
            response.raise_for_status()
            logger.info(f"Session warmed up. Cookies: {len(self.scraper.cookies)} items")
            time.sleep(2)
        except Exception as e:
            logger.warning(f"Failed to warm up session: {e}")

    def _random_delay(self):
        """Затримка між запитами"""
        import random
        time.sleep(random.uniform(self.delay_min, self.delay_max))

    def _fetch_category_products(self, category_slug: str, page: int) -> Optional[dict]:
        """
        Отримує товари з конкретної категорії через Shopify JSON API

        Args:
            category_slug: Slug категорії (напр. "counter-stools-by-steve-silver")
            page: Номер сторінки

        Returns:
            JSON response або None у разі помилки
        """
        url = f"{self.BASE_URL}/collections/{category_slug}/products.json"
        params = {'page': page}

        for attempt in range(self.retry_attempts):
            try:
                if self.session_type == 'curl_cffi':
                    response = curl_requests.get(
                        url,
                        params=params,
                        timeout=self.timeout,
                        impersonate=self.impersonate,
                        proxies=self.proxies
                    )
                else:
                    response = self.scraper.get(
                        url,
                        params=params,
                        timeout=self.timeout,
                        proxies=self.proxies
                    )

                response.raise_for_status()
                return response.json()

            except Exception as e:
                logger.warning(f"Request error (attempt {attempt+1}/{self.retry_attempts}): {e}")

                if attempt < self.retry_attempts - 1:
                    time.sleep(5)

        self.stats['errors'] += 1
        return None
    
    def _extract_products_from_json(self, json_data: dict, manufacturer_name: str) -> List[Dict[str, str]]:
        """
        Витягує товари з Shopify JSON API response

        Args:
            json_data: JSON response from /collections/.../products.json
            manufacturer_name: Назва виробника

        Returns:
            Список товарів
        """
        products = []

        try:
            for product in json_data.get('products', []):
                # Обробити кожен варіант товару
                for variant in product.get('variants', []):
                    sku = variant.get('sku', '').strip()

                    if not sku:
                        continue

                    # Зберегти товар
                    products.append({
                        'sku': sku,
                        'price': variant.get('price', ''),
                        'url': f"{self.BASE_URL}/products/{product.get('handle', '')}",
                        'title': product.get('title', ''),
                        'vendor': product.get('vendor', manufacturer_name),
                        'available': variant.get('available', False)
                    })

        except Exception as e:
            logger.error(f"Failed to extract products from JSON: {e}")

        return products
    
    def scrape_category(self, category_slug: str, manufacturer_name: str, seen_skus: Set[str]) -> List[Dict[str, str]]:
        """
        Парсить всі товари з однієї категорії

        Args:
            category_slug: Slug категорії (напр. "counter-stools-by-steve-silver")
            manufacturer_name: Назва виробника для логування
            seen_skus: Set для відстеження дублікатів

        Returns:
            Список товарів з цієї категорії
        """
        category_products = []
        page = 1
        
        while True:
            logger.debug(f"    Page {page}...")

            # Отримати JSON з API
            json_data = self._fetch_category_products(category_slug, page)

            if not json_data:
                logger.debug(f"    No data on page {page}")
                break

            # Витягти products з JSON
            page_products = self._extract_products_from_json(json_data, manufacturer_name)

            # Перевірка на пустий список - зупинка
            if not page_products:
                logger.debug(f"    Empty products list on page {page} - stopping")
                break

            # Додати тільки унікальні SKU
            new_count = 0
            for product in page_products:
                sku = product['sku']
                if sku not in seen_skus:
                    seen_skus.add(sku)
                    category_products.append(product)
                    new_count += 1

            logger.debug(f"    Page {page}: {len(page_products)} products, {new_count} new")

            # Якщо менше 30 товарів - це остання сторінка
            if len(page_products) < self.PRODUCTS_PER_PAGE:
                logger.debug(f"    Got {len(page_products)} products (< {self.PRODUCTS_PER_PAGE}) - last page")
                break

            page += 1

            # Захист від нескінченного циклу
            if page > 100:
                logger.warning(f"    Reached page limit (100) for category {category_slug}")
                break

            self._random_delay()

        return category_products
    
    def scrape_manufacturer(self, manufacturer_name: str, manufacturer_slug: str, 
                           seen_skus: Set[str]) -> List[Dict[str, str]]:
        """
        Парсить всі категорії одного виробника

        Args:
            manufacturer_name: Назва виробника (напр. "Steve Silver")
            manufacturer_slug: Slug виробника для отримання категорій
            seen_skus: Set для відстеження дублікатів

        Returns:
            Список товарів від цього виробника
        """
        logger.info(f"\n{'='*60}")
        logger.info(f"Processing manufacturer: {manufacturer_name}")
        logger.info(f"{'='*60}")

        # Отримати список категорій для цього виробника
        categories = self.manufacturer_categories.get(manufacturer_slug, [])
        
        if not categories:
            logger.warning(f"No categories found for {manufacturer_name} (slug: {manufacturer_slug})")
            return []

        logger.info(f"Found {len(categories)} categories for {manufacturer_name}")
        
        manufacturer_products = []
        start_time = datetime.now()
        
        for idx, category_slug in enumerate(categories, 1):
            logger.info(f"  [{idx}/{len(categories)}] Category: {category_slug}")
            
            # Парсити категорію
            category_products = self.scrape_category(category_slug, manufacturer_name, seen_skus)
            
            if category_products:
                manufacturer_products.extend(category_products)
                logger.info(f"    ✓ Collected {len(category_products)} new products (total: {len(manufacturer_products)})")
            else:
                logger.info(f"    ⊘ Empty category")
                self.stats['empty_categories'] += 1
            
            self.stats['categories_processed'] += 1
            
            # Progress update кожні 10 категорій
            if idx % 10 == 0:
                elapsed = (datetime.now() - start_time).total_seconds() / 60
                speed = idx / elapsed if elapsed > 0 else 0
                remaining = len(categories) - idx
                eta = remaining / speed if speed > 0 else 0
                
                logger.info(f"\n  📊 Progress: {idx}/{len(categories)} ({idx/len(categories)*100:.1f}%)")
                logger.info(f"     Products: {len(manufacturer_products)}")
                logger.info(f"     Speed: {speed:.1f} cat/min")
                logger.info(f"     ETA: {eta:.1f} min\n")
            
            # Затримка між категоріями
            if idx < len(categories):
                self._random_delay()
        
        elapsed = (datetime.now() - start_time).total_seconds() / 60
        logger.info(f"\n✓ Manufacturer {manufacturer_name} completed:")
        logger.info(f"  Categories processed: {len(categories)}")
        logger.info(f"  Products collected: {len(manufacturer_products)}")
        logger.info(f"  Time: {elapsed:.1f} minutes")
        
        self.stats['manufacturers_processed'] += 1
        
        return manufacturer_products
    
    def scrape_all_products(self) -> List[Dict[str, str]]:
        """Парсить всі товари від всіх виробників"""
        
        all_products = []
        seen_skus: Set[str] = set()
        
        try:
            for manufacturer_name, manufacturer_slug in self.MANUFACTURER_SLUGS.items():
                try:
                    products = self.scrape_manufacturer(
                        manufacturer_name, 
                        manufacturer_slug, 
                        seen_skus
                    )
                    all_products.extend(products)
                    
                except Exception as e:
                    # ✅ LOG ERROR
                    self.log_scraping_error(
                        error=e,
                        context={'manufacturer': manufacturer_name}
                    )
                    logger.error(f"Failed {manufacturer_name}: {e}")
                    continue
                
                time.sleep(3)
        
        except Exception as e:
            # ✅ LOG GLOBAL ERROR
            self.log_scraping_error(error=e, context={'stage': 'main'})
            raise
        
        return all_products
    
    def get_stats(self) -> dict:
        """Повертає статистику"""
        return self.stats.copy()

    def test_connection(self) -> dict:
        """Тестує з'єднання з сайтом для діагностики"""
        results = {
            'homepage': False,
            'products_api': False,
            'ip_blocked': False,
            'cloudflare': False,
            'session_type': self.session_type,
            'details': []
        }

        # Тест 1: Доступ до головної сторінки
        try:
            logger.info("Testing homepage access...")

            if self.session_type == 'curl_cffi':
                resp = curl_requests.get(
                    self.BASE_URL,
                    timeout=self.timeout,
                    impersonate=self.impersonate,
                    proxies=self.proxies
                )
            else:
                resp = self.scraper.get(self.BASE_URL, timeout=self.timeout, proxies=self.proxies)

            results['homepage'] = resp.status_code == 200
            results['details'].append(f"Homepage: {resp.status_code}")

            if 'cloudflare' in resp.text.lower() or 'cf-ray' in resp.headers:
                results['cloudflare'] = True
                results['details'].append("Cloudflare detected")
        except Exception as e:
            results['details'].append(f"Homepage error: {e}")

        # Тест 2: Products JSON API (test category)
        try:
            logger.info("Testing products API...")
            
            # Використати першу категорію першого виробника
            first_mfr_slug = list(self.MANUFACTURER_SLUGS.values())[0] if self.MANUFACTURER_SLUGS else None
            if first_mfr_slug and first_mfr_slug in self.manufacturer_categories:
                test_category = self.manufacturer_categories[first_mfr_slug][0]
                test_url = f"{self.BASE_URL}/collections/{test_category}/products.json"

                if self.session_type == 'curl_cffi':
                    resp = curl_requests.get(
                        test_url,
                        params={'page': 1},
                        timeout=self.timeout,
                        impersonate=self.impersonate,
                        proxies=self.proxies
                    )
                else:
                    resp = self.scraper.get(
                        test_url,
                        params={'page': 1},
                        timeout=self.timeout,
                        proxies=self.proxies
                    )

                results['products_api'] = resp.status_code == 200
                results['details'].append(f"Products API: {resp.status_code}")

                if resp.status_code == 403:
                    results['ip_blocked'] = True
                    results['details'].append("403 Forbidden - possible IP block")
        except Exception as e:
            results['details'].append(f"Products API error: {e}")
            if '403' in str(e):
                results['ip_blocked'] = True

        return results


def scrape_afa(config: dict) -> List[Dict[str, str]]:
    """Головна функція для парсингу AFA Stores"""
    scraper = AFAScraper(config)
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

    if not CURL_CFFI_AVAILABLE and not CLOUDSCRAPER_AVAILABLE:
        print("\nERROR: Neither curl_cffi nor cloudscraper installed!")
        print("\nPreferred: pip install curl-cffi")
        print("Fallback: pip install cloudscraper")
        print("\nWithout one of these, AFA scraper will fail due to Cloudflare protection.\n")
        exit(1)

    if CURL_CFFI_AVAILABLE:
        print("\nUsing curl_cffi (best TLS fingerprint)")
    else:
        print("\nUsing cloudscraper (may not work on all systems)")
    
    test_config = {
        'delay_min': 1.0,
        'delay_max': 2.0,
        'retry_attempts': 3,
        'timeout': 30
    }
    
    print("\n" + "="*60)
    print("ТЕСТ AFA STORES SCRAPER (CATEGORY-BASED)")
    print("="*60 + "\n")
    
    results = scrape_afa(test_config)
    
    print("\n" + "="*60)
    print(f"РЕЗУЛЬТАТ: {len(results)} товарів")
    print("="*60)
    
    if results:
        # Показати статистику по виробниках
        vendors = {}
        for product in results:
            vendor = product['vendor']
            vendors[vendor] = vendors.get(vendor, 0) + 1
        
        print("\nПо виробниках:")
        for vendor, count in vendors.items():
            print(f"  {vendor}: {count} товарів")
        
        print("\nПерші 5 товарів:")
        for i, product in enumerate(results[:5], 1):
            print(f"\n{i}. SKU: {product['sku']}")
            print(f"   Vendor: {product['vendor']}")
            print(f"   Price: ${product['price']}")
            if product.get('title'):
                print(f"   Title: {product['title'][:50]}...")
            if product.get('url'):
                print(f"   URL: {product['url'][:60]}...")
    else:
        print("\n❌ Немає результатів")
        print("\nПеревірте:")
        print("1. Чи існує файл manufacturer_categories.json")
        print("2. Чи Cloudflare не блокує ваш IP")
        print("3. Логи вище для деталей")
