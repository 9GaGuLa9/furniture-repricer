"""
Emma Mason Brands Scraper - OPTIMIZED VERSION v3.0
✅ FIXED: Price parsing - converts "887,84" → 887.84 (comma to dot)
✅ URL consistency for matching
✅ Error handling for price conversion
✅ OPTIMIZED: Removed redundant conditions and unused methods
"""

import time
import random
import logging
from typing import List, Dict, Optional, Set
from datetime import datetime
from bs4 import BeautifulSoup
from ..modules.error_logger import ScraperErrorMixin

# Спробувати імпортувати curl_cffi
try:
    from curl_cffi import requests
    CURL_CFFI_AVAILABLE = True
except ImportError:
    import requests
    CURL_CFFI_AVAILABLE = False
    logging.warning("⚠️ curl_cffi not found, using standard requests")

logger = logging.getLogger("emmamason_brands")


class EmmaMasonBrandsScraper(ScraperErrorMixin):
    """Scraper для emmamason.com - збирає по брендах"""
    
    BASE_URL = "https://emmamason.com"
    
    # Цільові бренди
    BRANDS = [
        {"name": "ACME", "url": "brands-by-acme~129973.html"},
        {"name": "Westwood Design", "url": "brands-by-westwood-design~937124.html"},
        {"name": "Legacy Classic", "url": "brands-by-legacy-classic~130027.html"},
        {"name": "Legacy Classic", "url": "brands-by-legacy-classic-kids~130028.html"},
        {"name": "Aspenhome Furniture", "url": "brands-by-aspenhome~129985.html"},
        {"name": "Steve Silver", "url": "brands-by-steve-silver~1242933.html"},
        {"name": "Intercon furniture", "url": "brands-intercon-furniture.html"},
        {"name": "by Intercon", "url": "brands-by-intercon~130018.html"},
    ]
    
    USER_AGENTS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    ]
    
    def __init__(self, config: dict, error_logger=None):
        self.config = config
        self.error_logger = error_logger
        self.scraper_name = "EmmaMasonScraper"
        self.delay_min = config.get('delay_min', 2.0)
        self.delay_max = config.get('delay_max', 4.0)
        self.retry_attempts = config.get('retry_attempts', 3)
        self.timeout = config.get('timeout', 45)
        self.per_page = 40
        
        if not CURL_CFFI_AVAILABLE:
            logger.error("curl_cffi not available! Scraper may fail!")
        else:
            logger.info("✓ curl_cffi available")
        
        logger.info("="*60)
        logger.info("Emma Mason Brands Scraper v3.0 (Optimized)")
        logger.info("="*60)
    
    def _random_delay(self):
        """Затримка між запитами"""
        time.sleep(random.uniform(self.delay_min, self.delay_max))
    
    def _get_random_user_agent(self) -> str:
        """Випадковий User-Agent"""
        return random.choice(self.USER_AGENTS)
    
    def _fetch_page(self, url: str, referer: Optional[str] = None) -> Optional[str]:
        """Завантажити сторінку (curl_cffi + impersonate)"""
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
                
                if CURL_CFFI_AVAILABLE:
                    response = requests.get(
                        url,
                        headers=headers,
                        impersonate="chrome120",
                        timeout=self.timeout
                    )
                else:
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
                error_msg = str(e)
                
                if "timed out" in error_msg.lower() or "timeout" in error_msg.lower():
                    logger.warning(f"Timeout (attempt {attempt}/{self.retry_attempts})")
                    time.sleep(random.uniform(5, 10))
                else:
                    logger.error(f"Request error (attempt {attempt}): {e}")
                    time.sleep(3)
        
        return None
    
    def _parse_price(self, price_text: str) -> Optional[str]:
        """
        ✅ CRITICAL FIX: Правильно парсити ціну
        
        Emma Mason може повертати:
        - "$887.84" (крапка) - ОК
        - "$887,84" (кома) - треба замінити на крапку!
        - "887,84" (без $, з комою)
        - "887.84" (без $, з крапкою)
        
        Returns:
            String з ціною у форматі "887.84" або None
        """
        if not price_text:
            return None
        
        try:
            # Видалити $, пробіли
            cleaned = price_text.replace('$', '').replace(' ', '').strip()
            
            if not cleaned:
                return None
            
            # ✅ КЛЮЧОВИЙ МОМЕНТ: Визначити роздільник
            # Якщо є кома і НЕМАЄ крапки - це європейський формат
            if ',' in cleaned and '.' not in cleaned:
                # "887,84" → "887.84"
                cleaned = cleaned.replace(',', '.')
                logger.debug(f"Converted comma price: {price_text} → {cleaned}")
            
            elif ',' in cleaned and '.' in cleaned:
                # Якщо є обидва - залежить від позиції
                # "1,234.56" - кома для тисяч, крапка для десяткових
                # "1.234,56" - крапка для тисяч, кома для десяткових
                
                comma_pos = cleaned.index(',')
                dot_pos = cleaned.index('.')
                
                if dot_pos > comma_pos:
                    # "1,234.56" - американський формат, видалити кому
                    cleaned = cleaned.replace(',', '')
                else:
                    # "1.234,56" - європейський формат
                    cleaned = cleaned.replace('.', '').replace(',', '.')
            
            # Спробувати конвертувати щоб перевірити
            try:
                float(cleaned)
                return cleaned
            except ValueError:
                logger.warning(f"Failed to parse price '{price_text}' → '{cleaned}'")
                return None
                
        except Exception as e:
            logger.error(f"Price parsing error for '{price_text}': {e}")
            return None
    
    def _extract_products_from_page(self, html: str, brand_name: str) -> List[Dict]:
        """
        Витягти товари зі сторінки бренду
        
        Returns:
            List[Dict]: [{id, url, price, brand}, ...]
        """
        products = []
        
        try:
            soup = BeautifulSoup(html, 'html.parser')
            product_items = soup.find_all('div', class_='product-item-info')
            
            for item in product_items:
                try:
                    # Product ID з price-box data-product-id
                    price_box = item.find('div', {'data-role': 'priceBox'})
                    if not price_box:
                        continue
                    
                    product_id = price_box.get('data-product-id')
                    if not product_id:
                        continue
                    
                    # URL
                    link = item.find('a', class_='product-item-link')
                    url = link['href'] if link else None
                    
                    if not url:
                        continue
                    
                    # ✅ FIXED: Ціна з правильною обробкою коми
                    price = None
                    price_elem = item.find('span', class_='price')
                    if price_elem:
                        price_text = price_elem.get_text(strip=True)
                        price = self._parse_price(price_text)
                    
                    products.append({
                        'id': product_id,
                        'url': url,
                        'price': price,
                        'brand': brand_name,
                        'scraped_at': datetime.now().isoformat()
                    })
                
                except Exception as e:
                    logger.debug(f"Failed to parse product: {e}")
                    continue
        
        except Exception as e:
            logger.error(f"Failed to parse page: {e}")
        
        return products
    
    def scrape_brand(self, brand_info: dict, seen_ids: Set[str]) -> List[Dict]:
        """Парсити один бренд"""
        brand_name = brand_info['name']
        brand_url = brand_info['url']
        
        logger.info(f"Processing brand: {brand_name}")
        
        brand_products = []
        page = 1
        
        while True:
            # Побудувати URL
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
            
            # Перевірка Cloudflare
            if "Just a moment" in html or "Checking your browser" in html:
                logger.warning(f"  Cloudflare challenge detected")
                break
            
            # Парсити товари
            products = self._extract_products_from_page(html, brand_name)
            
            # ═══════════════════════════════════════════════════════════
            # ✅ OPTIMIZED: Зупинка тільки коли товарів НЕМАЄ
            # ═══════════════════════════════════════════════════════════
            if not products:
                logger.info(f"  No products on page {page} - last page")
                break
            
            # Додати унікальні
            new_count = 0
            duplicate_count = 0
            
            for product in products:
                product_id = product['id']
                
                if product_id not in seen_ids:
                    seen_ids.add(product_id)
                    brand_products.append(product)
                    new_count += 1
                else:
                    duplicate_count += 1
            
            logger.info(f"  Page {page}: {new_count} new, {duplicate_count} duplicates (total: {len(brand_products)})")
            
            # ═══════════════════════════════════════════════════════════
            # Захист від нескінченного циклу
            # ═══════════════════════════════════════════════════════════
            if page >= 100:
                logger.warning(f"  Page limit reached (100)")
                break
            
            page += 1
            self._random_delay()
        
        logger.info(f"✓ Brand {brand_name}: {len(brand_products)} unique products")
        
        return brand_products
    
    def scrape_all_brands(self) -> List[Dict]:
        """Парсити всі бренди"""
        
        all_products = []
        seen_ids = set()
        
        try:
            for idx, brand_info in enumerate(self.BRANDS, 1):
                try:
                    products = self.scrape_brand(brand_info, seen_ids)
                    all_products.extend(products)
                    
                except Exception as e:
                    # ✅ LOG ERROR
                    self.log_scraping_error(
                        error=e,
                        context={'brand': brand_info['name']}
                    )
                    logger.error(f"Failed {brand_info['name']}: {e}")
                    continue
                
                time.sleep(3)
        
        except Exception as e:
            # ✅ LOG GLOBAL ERROR
            self.log_scraping_error(error=e, context={'stage': 'main'})
            raise
        
        # ═══════════════════════════════════════════════════════════
        # Final statistics
        # ═══════════════════════════════════════════════════════════
        logger.info("\n" + "="*60)
        logger.info("SCRAPING COMPLETED")
        logger.info("="*60)
        logger.info(f"Total products: {len(all_products)}")
        logger.info(f"Unique IDs: {len(seen_ids)}")
        
        # Статистика по брендах
        brands_stats = {}
        for p in all_products:
            brand = p['brand']
            brands_stats[brand] = brands_stats.get(brand, 0) + 1
        
        logger.info("\nBy brand:")
        for brand, count in brands_stats.items():
            logger.info(f"  {brand}: {count}")
        logger.info("="*60)
        
        return all_products


def scrape_emmamason_brands(config: dict) -> List[Dict]:
    """
    Головна функція для парсингу Emma Mason
    
    ✅ ВИКОРИСТОВУЄТЬСЯ В app/main.py:
    from app.scrapers.emmamason_brands import scrape_emmamason_brands
    results = scrape_emmamason_brands(config)
    
    Returns:
        List[Dict]: [{id, url, price, brand}, ...]
    """
    scraper = EmmaMasonBrandsScraper(config)
    results = scraper.scrape_all_brands()
    return results


# if __name__ == "__main__":
#     # Тестування
#     import logging
#     logging.basicConfig(
#         level=logging.INFO,
#         format='%(asctime)s | %(levelname)-8s | %(message)s',
#         datefmt='%H:%M:%S'
#     )
    
#     if not CURL_CFFI_AVAILABLE:
#         print("\n⚠️ Warning: curl_cffi not installed!")
#         print("Install: pip install curl-cffi")
#         print("Continuing with standard requests (may fail)\n")
    
#     config = {
#         'delay_min': 2.0,
#         'delay_max': 4.0,
#         'retry_attempts': 3,
#         'timeout': 45
#     }
    
#     print("\n" + "="*60)
#     print("ТЕСТ EMMA MASON BRANDS SCRAPER v3.0 (OPTIMIZED)")
#     print("="*60 + "\n")
    
#     results = scrape_emmamason_brands(config)
    
#     print("\n" + "="*60)
#     print(f"РЕЗУЛЬТАТ: {len(results)} products")
#     print("="*60)
    
#     if results:
#         print(f"\nSample (first 3):")
#         for i, p in enumerate(results[:3], 1):
#             print(f"\n{i}. ID: {p['id']}")
#             print(f"   Brand: {p['brand']}")
#             print(f"   Price: {p.get('price', 'N/A')}")
#             print(f"   URL: {p['url'][:60]}...")
#     else:
#         print("\n❌ No products scraped")
    
#     print("\n" + "="*60)
