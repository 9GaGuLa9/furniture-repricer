"""
Emma Mason Production Scraper - CURL_CFFI APPROACH (WORKING!)
Базується на ОРИГІНАЛЬНОМУ робочому коді з curl_cffi
БЕЗ Selenium - простіше, швидше, менше ресурсів!
"""

import json
import time
import random
from typing import List, Dict, Optional
from datetime import datetime
from bs4 import BeautifulSoup
import logging

# Спробувати імпортувати curl_cffi (ОБОВ'ЯЗКОВО для production!)
try:
    from curl_cffi import requests
    CURL_CFFI_AVAILABLE = True
except ImportError:
    import requests
    CURL_CFFI_AVAILABLE = False
    print("❌ curl_cffi not found! Install: pip install curl-cffi")
    print("⚠️  Fallback to standard requests (may fail with 403)")

logger = logging.getLogger("emmamason_production")


class EmmaMasonProductionScraper:
    """Production scraper для emmamason.com - curl_cffi підхід"""
    
    BASE_URL = "https://emmamason.com"
    
    # 5 цільових виробників
    BRANDS = [
        {"name": "ACME", "url": "brands-acme-furniture.html"},
        {"name": "Westwood Design", "url": "brands-by-westwood-design~937124.html.html"},
        {"name": "Legacy Classic", "url": "brands-legacy-classic.html"},
        {"name": "Aspenhome Furniture", "url": "aspenhome-furniture-by-aspenhome~587712.html.html"},
        {"name": "Steve Silver", "url": "steve-silver-by-steve-silver~1804527.html.html"},
        {"name": "Intercon", "url": "intercon-furniture-by-intercon-furniture~1035926.html"},
    ]
    
    USER_AGENTS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    ]
    
    def __init__(self, config: dict):
        self.config = config
        self.delay_min = config.get('delay_min', 2.0)
        self.delay_max = config.get('delay_max', 4.0)
        self.retry_attempts = config.get('retry_attempts', 3)
        self.timeout = config.get('timeout', 30)
        self.per_page = 40  # Products per page
        
        self.stats = {
            'total_products': 0,
            'unique_products': 0,
            'brands_processed': 0,
            'pages_processed': 0,
            'errors': 0
        }
        
        if not CURL_CFFI_AVAILABLE:
            logger.error("curl_cffi not available! Scraper may fail!")
        else:
            logger.info("✓ curl_cffi available - Cloudflare bypass ready")
        
        logger.info("="*60)
        logger.info("Emma Mason Production Scraper (curl_cffi)")
        logger.info(f"Method: HTTP requests (no browser)")
        logger.info(f"Cloudflare bypass: impersonate=chrome120")
        logger.info("="*60)
    
    def _random_delay(self):
        """Затримка між запитами"""
        time.sleep(random.uniform(self.delay_min, self.delay_max))
    
    def _get_random_user_agent(self) -> str:
        """Випадковий User-Agent"""
        return random.choice(self.USER_AGENTS)
    
    def _fetch_page(self, url: str, referer: Optional[str] = None) -> Optional[str]:
        """
        Завантажити сторінку (КЛЮЧОВИЙ МЕТОД!)
        Використовує curl_cffi + impersonate для обходу Cloudflare
        """
        for attempt in range(1, self.retry_attempts + 1):
            try:
                headers = {
                    "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "accept-language": "en-US,en;q=0.9",
                    "accept-encoding": "gzip, deflate, br",
                    "user-agent": self._get_random_user_agent(),
                    "cache-control": "no-cache",
                    "pragma": "no-cache",
                }
                if referer:
                    headers["referer"] = referer
                
                # ═══════════════════════════════════════════════════════
                # КЛЮЧ ДО УСПІХУ: curl_cffi + impersonate="chrome120"
                # ═══════════════════════════════════════════════════════
                if CURL_CFFI_AVAILABLE:
                    response = requests.get(
                        url,
                        headers=headers,
                        impersonate="chrome120",  # ← КРИТИЧНО!
                        timeout=self.timeout
                    )
                else:
                    # Fallback (може не працювати)
                    response = requests.get(
                        url,
                        headers=headers,
                        timeout=self.timeout
                    )
                
                if response.status_code == 200:
                    return response.text
                
                elif response.status_code == 403:
                    logger.warning(f"403 Forbidden (attempt {attempt}/{self.retry_attempts})")
                    time.sleep(random.uniform(5, 10))
                
                else:
                    logger.warning(f"Status {response.status_code} (attempt {attempt})")
                    time.sleep(3)
                    
            except Exception as e:
                logger.error(f"Request error (attempt {attempt}): {e}")
                time.sleep(3)
        
        self.stats['errors'] += 1
        return None
    
    def _extract_products_from_page(self, html: str, brand_name: str) -> List[Dict]:
        """
        Витягти товари зі сторінки бренду
        Парсить product-item-info блоки
        Збирає: product_id, price, url
        """
        products = []

        try:
            soup = BeautifulSoup(html, 'html.parser')

            # Знайти всі product items
            product_items = soup.find_all('div', class_='product-item-info')

            for item in product_items:
                try:
                    # Product ID (з price-box data-product-id)
                    price_box = item.find('div', {'data-role': 'priceBox'})
                    if not price_box:
                        logger.debug("No price-box found, skipping")
                        continue

                    product_id = price_box.get('data-product-id')
                    if not product_id:
                        logger.debug("No product ID found, skipping")
                        continue

                    # URL
                    link = item.find('a', class_='product-item-link')
                    if not link:
                        logger.debug("No link found, skipping")
                        continue
                    url = link.get('href')
                    if not url:
                        logger.debug("No href found, skipping")
                        continue

                    # Ціна
                    price_elem = item.find('span', class_='price')
                    price = None
                    if price_elem:
                        price_text = price_elem.get_text(strip=True)
                        price = price_text.replace('$', '').replace(',', '').strip()
                        try:
                            float(price)  # Перевірити що валідна
                        except:
                            price = None

                    products.append({
                        'product_id': product_id,
                        'brand': brand_name,
                        'url': url,
                        'price': price,
                        'scraped_at': datetime.now().isoformat()
                    })

                except Exception as e:
                    logger.debug(f"Failed to parse product item: {e}")
                    continue

        except Exception as e:
            logger.error(f"Failed to parse page HTML: {e}")

        return products
    
    def scrape_brand(self, brand_info: dict, seen_ids: set) -> List[Dict]:
        """
        Парсити один бренд (всі сторінки)
        """
        brand_name = brand_info['name']
        brand_url = brand_info['url']

        logger.info(f"Processing brand: {brand_name}")

        brand_products = []
        page = 1

        while True:
            # URL з pagination
            if page == 1:
                url = f"{self.BASE_URL}/{brand_url}?product_list_limit={self.per_page}"
            else:
                url = f"{self.BASE_URL}/{brand_url}?p={page}&product_list_limit={self.per_page}"

            logger.debug(f"  Page {page}: {url}")

            # Завантажити сторінку
            html = self._fetch_page(url, referer=self.BASE_URL)

            if not html:
                logger.error(f"  Failed to fetch page {page}")
                break

            # Перевірити Cloudflare challenge
            if "Just a moment" in html or "Checking your browser" in html:
                logger.warning(f"  Cloudflare challenge detected!")
                logger.warning(f"  This should not happen with curl_cffi + impersonate")
                break

            # Витягти товари
            products = self._extract_products_from_page(html, brand_name)

            if not products:
                logger.info(f"  No products on page {page}, end of brand")
                break

            # Додати унікальні
            new_count = 0
            for product in products:
                product_id = product['product_id']
                if product_id not in seen_ids:
                    seen_ids.add(product_id)
                    brand_products.append(product)
                    new_count += 1

            logger.info(f"  Page {page}: {len(products)} products, {new_count} new (total: {len(brand_products)})")

            self.stats['pages_processed'] += 1

            # Остання сторінка?
            if len(products) < self.per_page:
                logger.info(f"  Last page (products < {self.per_page})")
                break

            # Ліміт сторінок
            if page >= 50:
                logger.warning(f"  Page limit reached (50)")
                break

            page += 1

            # Затримка між сторінками
            self._random_delay()

        logger.info(f"Brand {brand_name}: {len(brand_products)} unique products")
        self.stats['brands_processed'] += 1

        return brand_products
    
    def scrape_all_products(self) -> List[Dict]:
        """
        Парсити всі бренди
        Головний метод для production
        """
        logger.info("="*60)
        logger.info("Starting brand-based scraping")
        logger.info(f"Brands: {[b['name'] for b in self.BRANDS]}")
        logger.info("="*60)

        all_products = []
        seen_ids = set()
        start_time = datetime.now()

        for idx, brand_info in enumerate(self.BRANDS, 1):
            logger.info(f"\n{'='*60}")
            logger.info(f"📂 BRAND {idx}/{len(self.BRANDS)}: {brand_info['name']}")
            logger.info(f"{'='*60}")

            products = self.scrape_brand(brand_info, seen_ids)
            all_products.extend(products)

            self.stats['total_products'] = len(all_products)
            self.stats['unique_products'] = len(seen_ids)

            # Прогрес
            elapsed = (datetime.now() - start_time).total_seconds() / 60
            speed = len(all_products) / elapsed if elapsed > 0 else 0
            brands_left = len(self.BRANDS) - idx
            eta = (brands_left * elapsed / idx) if idx > 0 else 0

            logger.info(f"\n{'='*60}")
            logger.info(f"📊 OVERALL PROGRESS")
            logger.info(f"{'='*60}")
            logger.info(f"Brands: {idx}/{len(self.BRANDS)} ({idx/len(self.BRANDS)*100:.1f}%)")
            logger.info(f"Products: {len(all_products)} ({len(seen_ids)} unique)")
            logger.info(f"Speed: {speed:.1f} products/min")
            logger.info(f"Elapsed: {elapsed:.1f} min")
            logger.info(f"ETA: {eta:.1f} min")
            logger.info(f"Pages: {self.stats['pages_processed']}")
            logger.info(f"Errors: {self.stats['errors']}")
            logger.info(f"{'='*60}\n")

            # Затримка між брендами
            if idx < len(self.BRANDS):
                time.sleep(3)

        duration = (datetime.now() - start_time).total_seconds() / 60

        logger.info("="*60)
        logger.info(f"✅ COMPLETED")
        logger.info(f"Products: {len(all_products)} ({len(seen_ids)} unique IDs)")
        logger.info(f"Brands: {self.stats['brands_processed']}")
        logger.info(f"Pages: {self.stats['pages_processed']}")
        logger.info(f"Time: {duration:.1f} minutes")
        logger.info(f"Speed: {len(all_products)/duration:.1f} products/min")
        logger.info(f"Errors: {self.stats['errors']}")
        logger.info("="*60)

        return all_products
    
    def get_stats(self) -> dict:
        """Повернути статистику"""
        return self.stats.copy()


def scrape_emmamason_production(config: dict) -> List[Dict]:
    """
    Головна функція для production
    Використовує curl_cffi підхід (БЕЗ Selenium!)
    """
    scraper = EmmaMasonProductionScraper(config)
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
    
    if not CURL_CFFI_AVAILABLE:
        print("\n" + "="*60)
        print("❌ curl_cffi NOT INSTALLED!")
        print("="*60)
        print("\nInstall it:")
        print("  pip install curl-cffi")
        print("\nWithout curl_cffi, scraper will fail with 403 Forbidden!")
        print("="*60 + "\n")
        exit(1)
    
    # Production config
    config = {
        'delay_min': 2.0,
        'delay_max': 4.0,
        'retry_attempts': 3,
        'timeout': 30
    }
    
    print("\n" + "="*60)
    print("PRODUCTION SCRAPER TEST (curl_cffi approach)")
    print("="*60 + "\n")
    
    results = scrape_emmamason_production(config)
    
    print("\n" + "="*60)
    print(f"RESULT: {len(results)} products")
    print("="*60)
    
    if results:
        # Зберегти
        output_file = f"emmamason_production_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        
        print(f"\n✓ Saved: {output_file}")
        
        # Статистика
        brands = {}
        for p in results:
            brand = p['brand']
            brands[brand] = brands.get(brand, 0) + 1
        
        print("\nBy brand:")
        for brand, count in brands.items():
            print(f"  {brand}: {count}")
        
        print(f"\nSample (first 3):")
        for i, p in enumerate(results[:3], 1):
            print(f"\n{i}. SKU: {p['sku']}")
            print(f"   Brand: {p['brand']}")
            print(f"   Price: ${p.get('price', 'N/A')}")
            print(f"   URL: {p['url'][:60]}...")
    else:
        print("\n❌ No products scraped")
    
    print("\n" + "="*60)
