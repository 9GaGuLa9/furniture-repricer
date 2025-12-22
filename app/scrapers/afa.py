"""
AFA Stores Scraper - CLOUDFLARE BYPASS + VENDOR FILTERING
Використовує cloudscraper для обходу Cloudflare + Shopify collections
"""

import time
import logging
from typing import List, Dict, Optional
from datetime import datetime

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


class AFAScraper:
    """Scraper для afastores.com через Shopify collections з vendor filtering"""

    BASE_URL = "https://www.afastores.com"

    # Пріоритетні виробники
    PRIORITY_VENDORS = [
        "Steve Silver",
        "Martin Furniture", 
        "Legacy Classic Furniture",
        "Legacy Classic Kids",
        "ACME Furniture",
        "Intercon Furniture",
        "Westwood Design",
    ]

    def __init__(self, config: dict):
        self.config = config
        self.delay_min = config.get('delay_min', 2.0)
        self.delay_max = config.get('delay_max', 4.0)
        self.retry_attempts = config.get('retry_attempts', 3)
        self.timeout = config.get('timeout', 30)
        self.proxies = config.get('proxies', None)  # {'http': 'http://proxy:port', 'https': 'http://proxy:port'}
        
        self.stats = {
            'total_products': 0,
            'unique_products': 0,
            'errors': 0,
            'vendors_processed': 0
        }

        # Initialize session with best available method
        self.session_type = None
        self.impersonate = None

        if CURL_CFFI_AVAILABLE:
            # curl_cffi - best TLS fingerprint, works most reliably
            self.session_type = 'curl_cffi'
            self.impersonate = 'chrome110'  # Verified working
            self.scraper = None  # Will use curl_requests directly
            logger.info(f"AFA Stores scraper initialized with curl_cffi (impersonate={self.impersonate})")

        elif CLOUDSCRAPER_AVAILABLE:
            # Fallback to cloudscraper
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
            # Last resort - regular requests (will likely fail)
            import requests
            self.session_type = 'requests'
            self.scraper = requests.Session()
            self.scraper.headers.update({
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            })
            logger.warning("AFA Stores scraper initialized with basic requests - will likely fail!")

    def _warm_up_session(self):
        """Отримує початкові cookies, відвідуючи головну сторінку"""
        # curl_cffi doesn't need warm-up - it handles TLS perfectly
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
            time.sleep(2)  # Затримка після початкового візиту
        except Exception as e:
            logger.warning(f"Failed to warm up session: {e}")

    def _random_delay(self):
        """Затримка між запитами"""
        import random
        time.sleep(random.uniform(self.delay_min, self.delay_max))

    def _fetch_products_json(self, vendor_name: str, page: int, limit: int = 250) -> Optional[dict]:
        """
        Отримує товари через Shopify JSON API

        Args:
            vendor_name: Назва виробника (напр. "Steve Silver")
            page: Номер сторінки
            limit: Кількість товарів на сторінку (макс 250)

        Returns:
            JSON response або None у разі помилки
        """
        url = f"{self.BASE_URL}/products.json"
        params = {
            'vendor': vendor_name,
            'limit': limit,
            'page': page
        }

        for attempt in range(self.retry_attempts):
            try:
                if self.session_type == 'curl_cffi':
                    # Use curl_cffi for best TLS fingerprint
                    response = curl_requests.get(
                        url,
                        params=params,
                        timeout=self.timeout,
                        impersonate=self.impersonate,
                        proxies=self.proxies
                    )
                else:
                    # Use cloudscraper or requests
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
    
    def _extract_products_from_json(self, json_data: dict, vendor_name: str) -> List[Dict[str, str]]:
        """
        Витягує товари з Shopify JSON API response

        Args:
            json_data: JSON response from /products.json
            vendor_name: Назва виробника

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
                        'vendor': product.get('vendor', vendor_name),
                        'available': variant.get('available', False)
                    })

        except Exception as e:
            logger.error(f"Failed to extract products from JSON: {e}")

        return products
    
    def scrape_vendor(self, vendor_name: str, seen_skus: set) -> List[Dict[str, str]]:
        """
        Парсить всі товари одного виробника через Shopify JSON API

        Args:
            vendor_name: Назва виробника (напр. "Steve Silver")
            seen_skus: Set для відстеження дублікатів

        Returns:
            Список товарів від цього виробника
        """
        logger.info(f"Processing vendor: {vendor_name}")

        vendor_products = []
        page = 1
        limit = 250  # Максимум дозволений Shopify

        while True:
            logger.debug(f"  Fetching page {page}...")

            # Отримати JSON з API
            json_data = self._fetch_products_json(vendor_name, page, limit)

            if not json_data:
                logger.debug(f"  No data on page {page}")
                break

            # Витягти products з JSON
            page_products = self._extract_products_from_json(json_data, vendor_name)

            if not page_products:
                logger.info(f"  Vendor {vendor_name}: no products on page {page}")
                break

            # Додати тільки унікальні SKU
            new_count = 0
            for product in page_products:
                sku = product['sku']
                if sku not in seen_skus:
                    seen_skus.add(sku)
                    vendor_products.append(product)
                    new_count += 1

            logger.info(f"  Page {page}: {len(page_products)} products, {new_count} new (total: {len(vendor_products)})")

            # Якщо нічого нового - всі товари вже були додані раніше
            if new_count == 0:
                logger.info(f"  Vendor {vendor_name}: no new products on page {page}, stopping")
                break

            # Якщо отримали менше ніж limit - це остання сторінка
            products_on_page = len(json_data.get('products', []))
            if products_on_page < limit:
                logger.info(f"  Received {products_on_page} products (< {limit}), this is the last page")
                break

            page += 1

            # Максимум 50 сторінок (запобігання нескінченному циклу)
            if page > 50:
                logger.warning(f"  Vendor {vendor_name}: reached page limit (50)")
                break

            self._random_delay()

        logger.info(f"Vendor {vendor_name}: collected {len(vendor_products)} unique products")
        self.stats['vendors_processed'] += 1

        return vendor_products
    
    def scrape_all_products(self) -> List[Dict[str, str]]:
        """Парсить всі товари від пріоритетних виробників"""
        logger.info("="*60)
        logger.info(f"Starting AFA Stores scraping (method: {self.session_type})")
        logger.info(f"Priority vendors: {self.PRIORITY_VENDORS}")
        logger.info("="*60)

        if self.session_type == 'requests':
            logger.error("Neither curl_cffi nor cloudscraper available!")
            logger.error("Install curl_cffi: pip install curl-cffi")
            return []
        
        all_products = []
        seen_skus = set()
        
        for vendor_name in self.PRIORITY_VENDORS:
            logger.info(f"\nProcessing vendor: {vendor_name}")
            
            products = self.scrape_vendor(vendor_name, seen_skus)
            all_products.extend(products)
            
            self.stats['total_products'] = len(all_products)
            self.stats['unique_products'] = len(seen_skus)
            
            # Затримка між виробниками
            time.sleep(3)
        
        logger.info("="*60)
        logger.info(f"Completed: {len(all_products)} products from {len(seen_skus)} unique SKUs")
        logger.info(f"Vendors processed: {self.stats['vendors_processed']}")
        logger.info(f"Errors: {self.stats['errors']}")
        logger.info("="*60)
        
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

        # Тест 2: Products JSON API
        try:
            logger.info("Testing products API...")
            test_url = f"{self.BASE_URL}/products.json"

            if self.session_type == 'curl_cffi':
                resp = curl_requests.get(
                    test_url,
                    params={'limit': 1},
                    timeout=self.timeout,
                    impersonate=self.impersonate,
                    proxies=self.proxies
                )
            else:
                resp = self.scraper.get(
                    test_url,
                    params={'limit': 1},
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
        'delay_min': 2.0,
        'delay_max': 4.0,
        'retry_attempts': 3,
        'timeout': 30
    }
    
    print("\n" + "="*60)
    print("ТЕСТ AFA STORES SCRAPER (CLOUDSCRAPER + VENDOR COLLECTIONS)")
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
        print("\nМожливі причини:")
        print("1. Cloudflare блокує запити")
        print("2. Vendor collection URLs змінились")
        print("3. HTML структура змінилась")
        print("\nПеревірте логи вище для деталей.")
