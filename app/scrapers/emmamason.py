"""
Emma Mason Scraper - ВИПРАВЛЕНА ВЕРСІЯ
Парсить ціни з emmamason.com
"""

import json
import time
import random
from typing import List, Dict, Optional
from datetime import datetime
from bs4 import BeautifulSoup
import sys
from pathlib import Path

# ВИПРАВЛЕННЯ: Додати root до path якщо запускаємо напряму
if __name__ == "__main__":
    project_root = Path(__file__).parent.parent.parent
    sys.path.insert(0, str(project_root))

# Спробувати імпортувати curl_cffi
try:
    from curl_cffi import requests
    CURL_CFFI_AVAILABLE = True
except ImportError:
    import requests
    CURL_CFFI_AVAILABLE = False
    print("⚠️  curl_cffi not found, using standard requests")

# ВИПРАВЛЕННЯ: Гнучкий імпорт logger
try:
    from ..modules.logger import get_logger
except (ImportError, ValueError):
    from app.modules.logger import get_logger

import logging
logger = logging.getLogger("emmamason")


class EmmaMasonScraper:
    """Scraper для emmamason.com"""
    
    BASE_URL = "https://emmamason.com"
    USER_AGENTS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    ]
    
    def __init__(self, config: dict):
        self.config = config
        self.delay_min = config.get('delay_min', 2.0)
        self.delay_max = config.get('delay_max', 5.0)
        self.retry_attempts = config.get('retry_attempts', 3)
        self.timeout = config.get('timeout', 30)
        
        self.session_stats = {'success': 0, 'errors': 0, 'skipped': 0}
        logger.info(f"Emma Mason scraper initialized")
    
    def _random_delay(self):
        time.sleep(random.uniform(self.delay_min, self.delay_max))
    
    def _get_random_user_agent(self) -> str:
        return random.choice(self.USER_AGENTS)
    
    def _fetch_page(self, url: str, referer: Optional[str] = None) -> Optional[str]:
        for attempt in range(1, self.retry_attempts + 1):
            try:
                headers = {
                    "accept": "text/html,application/xhtml+xml",
                    "user-agent": self._get_random_user_agent(),
                }
                if referer:
                    headers["referer"] = referer
                
                if CURL_CFFI_AVAILABLE:
                    response = requests.get(url, headers=headers, impersonate="chrome120", timeout=self.timeout)
                else:
                    response = requests.get(url, headers=headers, timeout=self.timeout)
                
                if response.status_code == 200:
                    return response.text
                elif response.status_code == 403:
                    logger.warning(f"403 Forbidden (attempt {attempt})")
                    time.sleep(random.uniform(5, 10))
                else:
                    logger.warning(f"Status {response.status_code}")
                    time.sleep(3)
            except Exception as e:
                logger.error(f"Error: {e}")
                time.sleep(3)
        return None
    
    def _extract_product_data(self, html: str, url: str) -> Optional[Dict[str, str]]:
        try:
            soup = BeautifulSoup(html, 'html.parser')
            scripts = soup.find_all('script', type='application/ld+json')
            
            for script in scripts:
                try:
                    data = json.loads(script.string)
                    if data.get('@type') == 'Product':
                        sku = data.get('sku', '')
                        if ';' in sku:
                            sku = sku.split(';')[0].strip()
                        
                        price = None
                        offers = data.get('offers', {})
                        if isinstance(offers, dict):
                            price = offers.get('price', '')
                        
                        if sku and price:
                            price_str = str(price).replace('$', '').strip()
                            try:
                                float(price_str)
                                return {'sku': sku, 'price': price_str, 'url': url}
                            except ValueError:
                                continue
                except:
                    continue
        except Exception as e:
            logger.error(f"Extract error: {e}")
        return None
    
    def scrape_product(self, url: str) -> Optional[Dict[str, str]]:
        if not url or not url.strip():
            self.session_stats['skipped'] += 1
            return None
        
        self._random_delay()
        html = self._fetch_page(url)
        
        if not html:
            self.session_stats['errors'] += 1
            return None
        
        product_data = self._extract_product_data(html, url)
        
        if product_data:
            self.session_stats['success'] += 1
            logger.info(f"✓ SKU: {product_data['sku']}, Price: ${product_data['price']}")
        else:
            self.session_stats['errors'] += 1
            logger.warning(f"✗ No data from: {url[:60]}")
        
        return product_data
    
    def scrape_products(self, urls: List[str]) -> List[Dict[str, str]]:
        results = []
        total = len(urls)
        
        logger.info(f"Starting scrape of {total} products")
        logger.info("="*60)
        
        for idx, url in enumerate(urls, 1):
            if not url or not url.strip():
                self.session_stats['skipped'] += 1
                continue
            
            logger.info(f"[{idx}/{total}] Scraping: {url[:60]}...")
            product_data = self.scrape_product(url)
            
            if product_data:
                results.append(product_data)
            
            if idx % 10 == 0 and idx < total:
                time.sleep(random.uniform(5, 8))
        
        logger.info("="*60)
        logger.info(f"Completed: ✓ {self.session_stats['success']}, "
                   f"✗ {self.session_stats['errors']}, "
                   f"⊘ {self.session_stats['skipped']}")
        
        return results
    
    def get_stats(self) -> Dict[str, int]:
        return self.session_stats.copy()


def scrape_emmamason(our_urls: List[str], config: dict) -> List[Dict[str, str]]:
    """Головна функція для парсингу"""
    scraper = EmmaMasonScraper(config)
    results = scraper.scrape_products(our_urls)
    return results


# ТЕСТУВАННЯ
if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
    
    test_config = {'delay_min': 1.0, 'delay_max': 2.0, 'retry_attempts': 3, 'timeout': 30}
    test_urls = [
        "https://emmamason.com/lighting.html",
        "https://emmamason.com/bedroom-furniture-dresser.html",
    ]
    
    print("\n" + "="*60)
    print("ТЕСТ EMMA MASON SCRAPER")
    print("="*60 + "\n")
    
    results = scrape_emmamason(test_urls, test_config)
    
    print("\n" + "="*60)
    print("РЕЗУЛЬТАТИ:")
    print("="*60)
    
    if results:
        for product in results:
            print(f"\nSKU: {product['sku']}")
            print(f"  Price: ${product['price']}")
            print(f"  URL: {product['url'][:60]}...")
    else:
        print("\n❌ Немає результатів")
    
    print("\n" + "="*60)
