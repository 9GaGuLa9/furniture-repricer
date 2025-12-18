"""
Emma Mason Scraper
Парсить актуальні ціни (Our Sales Price) з сайту клієнта emmamason.com
"""

import json
import time
import random
import logging
from typing import List, Dict, Optional
from datetime import datetime
from bs4 import BeautifulSoup

try:
    from curl_cffi import requests
except ImportError:
    import requests
    print("⚠️  Warning: curl_cffi not installed, using standard requests")

from ..modules.logger import get_logger

logger = get_logger("emmamason")


class EmmaMasonScraper:
    """Scraper для emmamason.com - сайт клієнта"""
    
    BASE_URL = "https://emmamason.com"
    
    USER_AGENTS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) Gecko/20100101 Firefox/122.0",
    ]
    
    def __init__(self, config: dict):
        """
        Ініціалізація scraper
        
        Args:
            config: Конфігурація з config.yaml секція 'scrapers.emmamason'
        """
        self.config = config
        self.delay_min = config.get('delay_min', 2.0)
        self.delay_max = config.get('delay_max', 5.0)
        self.retry_attempts = config.get('retry_attempts', 3)
        self.timeout = config.get('timeout', 30)
        
        self.session_stats = {
            'success': 0,
            'errors': 0,
            'skipped': 0
        }
        
        logger.info(f"Initialized Emma Mason scraper (delay: {self.delay_min}-{self.delay_max}s)")
    
    def _random_delay(self):
        """Рандомна затримка між запитами"""
        delay = random.uniform(self.delay_min, self.delay_max)
        time.sleep(delay)
    
    def _get_random_user_agent(self) -> str:
        """Повертає випадковий User-Agent"""
        return random.choice(self.USER_AGENTS)
    
    def _fetch_page(self, url: str, referer: Optional[str] = None) -> Optional[str]:
        """
        Завантажує сторінку з повторними спробами
        
        Args:
            url: URL для завантаження
            referer: Referer заголовок
            
        Returns:
            HTML контент або None
        """
        for attempt in range(1, self.retry_attempts + 1):
            try:
                headers = {
                    "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "accept-language": "en-US,en;q=0.9",
                    "accept-encoding": "gzip, deflate, br",
                    "user-agent": self._get_random_user_agent(),
                    "sec-fetch-dest": "document",
                    "sec-fetch-mode": "navigate",
                    "sec-fetch-site": "same-origin" if referer else "none",
                    "upgrade-insecure-requests": "1",
                }
                
                if referer:
                    headers["referer"] = referer
                
                # Використовуємо curl_cffi якщо доступний
                try:
                    response = requests.get(
                        url,
                        headers=headers,
                        impersonate="chrome120",
                        timeout=self.timeout
                    )
                except:
                    # Fallback на звичайний requests
                    response = requests.get(url, headers=headers, timeout=self.timeout)
                
                if response.status_code == 200:
                    return response.text
                
                elif response.status_code == 403:
                    logger.warning(f"403 Forbidden (attempt {attempt}/{self.retry_attempts}): {url[:60]}")
                    if attempt < self.retry_attempts:
                        time.sleep(random.uniform(5, 10))
                
                else:
                    logger.warning(f"Status {response.status_code} (attempt {attempt}/{self.retry_attempts}): {url[:60]}")
                    if attempt < self.retry_attempts:
                        time.sleep(random.uniform(3, 6))
            
            except Exception as e:
                logger.error(f"Error fetching page (attempt {attempt}/{self.retry_attempts}): {e}")
                if attempt < self.retry_attempts:
                    time.sleep(random.uniform(3, 6))
        
        logger.error(f"Failed to fetch after {self.retry_attempts} attempts: {url[:60]}")
        return None
    
    def _extract_product_data(self, html: str, url: str) -> Optional[Dict[str, str]]:
        """
        Витягує дані товару з JSON-LD structured data
        
        Args:
            html: HTML контент сторінки
            url: URL товару
            
        Returns:
            Dict з sku та price або None
        """
        try:
            soup = BeautifulSoup(html, 'html.parser')
            
            # Шукаємо всі JSON-LD scripts
            scripts = soup.find_all('script', type='application/ld+json')
            
            for script in scripts:
                try:
                    data = json.loads(script.string)
                    
                    # Перевіряємо чи це Product schema
                    if data.get('@type') == 'Product':
                        sku = data.get('sku', '')
                        
                        # SKU може містити кілька значень через ";"
                        if ';' in sku:
                            sku = sku.split(';')[0].strip()
                        
                        if not sku:
                            continue
                        
                        # Витягуємо ціну з offers
                        price = None
                        offers = data.get('offers', {})
                        
                        if isinstance(offers, dict):
                            price = offers.get('price', '')
                        
                        if sku and price:
                            # Нормалізуємо ціну
                            price_str = str(price).replace('$', '').strip()
                            
                            try:
                                float(price_str)  # Перевірка валідності
                                return {
                                    'sku': sku,
                                    'price': price_str,
                                    'url': url
                                }
                            except ValueError:
                                logger.warning(f"Invalid price format: {price_str}")
                                continue
                
                except json.JSONDecodeError:
                    continue
                except Exception as e:
                    logger.debug(f"Error parsing JSON-LD: {e}")
                    continue
        
        except Exception as e:
            logger.error(f"Error extracting product data: {e}")
        
        return None
    
    def scrape_product(self, url: str) -> Optional[Dict[str, str]]:
        """
        Парсить один товар за URL
        
        Args:
            url: URL товару
            
        Returns:
            Dict з даними або None
            Format: {'sku': 'XXX', 'price': '599.99', 'url': 'https://...'}
        """
        if not url or not url.strip():
            logger.debug("Empty URL provided")
            self.session_stats['skipped'] += 1
            return None
        
        # Затримка перед запитом
        self._random_delay()
        
        # Завантажуємо сторінку
        html = self._fetch_page(url)
        
        if not html:
            self.session_stats['errors'] += 1
            return None
        
        # Витягуємо дані
        product_data = self._extract_product_data(html, url)
        
        if product_data:
            self.session_stats['success'] += 1
            logger.debug(f"✓ SKU: {product_data['sku']}, Price: ${product_data['price']}")
        else:
            self.session_stats['errors'] += 1
            logger.warning(f"✗ No data extracted from: {url[:60]}")
        
        return product_data
    
    def scrape_products(self, urls: List[str]) -> List[Dict[str, str]]:
        """
        Парсить кілька товарів за списком URL
        
        Args:
            urls: Список URL товарів з Google Sheets (колонка Our URL)
            
        Returns:
            List[Dict] з даними товарів
            Format: [{'sku': 'XXX', 'price': '599.99', 'url': 'https://...'}, ...]
        """
        results = []
        total = len(urls)
        
        logger.info(f"Starting scrape of {total} Emma Mason products")
        logger.info("="*60)
        
        for idx, url in enumerate(urls, 1):
            if not url or not url.strip():
                logger.debug(f"[{idx}/{total}] Skipping empty URL")
                self.session_stats['skipped'] += 1
                continue
            
            logger.info(f"[{idx}/{total}] Scraping: {url[:60]}...")
            
            product_data = self.scrape_product(url)
            
            if product_data:
                results.append(product_data)
            
            # Довша затримка кожні 10 товарів
            if idx % 10 == 0 and idx < total:
                logger.debug(f"Checkpoint: {idx}/{total} completed")
                time.sleep(random.uniform(5, 8))
        
        # Статистика
        logger.info("="*60)
        logger.info(f"Emma Mason scraping completed:")
        logger.info(f"  ✓ Success: {self.session_stats['success']}")
        logger.info(f"  ✗ Errors: {self.session_stats['errors']}")
        logger.info(f"  ⊘ Skipped: {self.session_stats['skipped']}")
        logger.info(f"  Total: {total}")
        
        return results
    
    def get_stats(self) -> Dict[str, int]:
        """Повертає статистику поточної сесії"""
        return self.session_stats.copy()


# ==================== ГОЛОВНА ФУНКЦІЯ ====================

def scrape_emmamason(our_urls: List[str], config: dict) -> List[Dict[str, str]]:
    """
    Головна функція для парсингу Emma Mason (викликається з main.py)
    
    Args:
        our_urls: Список URL з Google Sheets (колонка "Our URL")
        config: Конфігурація з config.yaml
        
    Returns:
        List[Dict]: [{'sku': 'XXX', 'price': '599.99', 'url': '...'}, ...]
    """
    scraper = EmmaMasonScraper(config)
    results = scraper.scrape_products(our_urls)
    return results


# ==================== ТЕСТУВАННЯ ====================

if __name__ == "__main__":
    import logging
    
    # Налаштування логування для тесту
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s | %(name)-12s | %(levelname)-8s | %(message)s',
        datefmt='%H:%M:%S'
    )
    
    # Тестові дані
    test_config = {
        'delay_min': 1.0,
        'delay_max': 2.0,
        'retry_attempts': 3,
        'timeout': 30
    }
    
    test_urls = [
        "https://emmamason.com/lighting.html",
        "https://emmamason.com/bedroom-furniture-dresser.html",
        "https://emmamason.com/dining-rooms-dining-chairs-arm-chairs.html"
    ]
    
    print("="*60)
    print("ТЕСТ EMMA MASON SCRAPER")
    print("="*60)
    print()
    
    # Запуск
    results = scrape_emmamason(test_urls, test_config)
    
    # Виведення результатів
    print()
    print("="*60)
    print("РЕЗУЛЬТАТИ:")
    print("="*60)
    
    if results:
        for product in results:
            print(f"\nSKU: {product['sku']}")
            print(f"  Price: ${product['price']}")
            print(f"  URL: {product['url'][:60]}...")
    else:
        print("❌ Немає результатів")
    
    print()
    print("="*60)
