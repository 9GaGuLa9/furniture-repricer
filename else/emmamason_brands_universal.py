"""
Emma Mason Universal Scraper v4.1
✅ Підтримує ОБА формати: search page (ais-InfiniteHits) + brand page (product-item-info)
✅ Автоматично визначає який формат використовувати
"""

import time
import random
import logging
import sys
from pathlib import Path
from typing import List, Dict, Optional, Set
from datetime import datetime
from bs4 import BeautifulSoup

# Smart imports
try:
    from ..modules.error_logger import ScraperErrorMixin
except ImportError:
    project_root = Path(__file__).parent.parent.parent
    sys.path.insert(0, str(project_root))
    
    try:
        from app.modules.error_logger import ScraperErrorMixin
    except ImportError:
        class ScraperErrorMixin:
            def log_scraping_error(self, error, url=None, context=None):
                logger = logging.getLogger("emmamason_brands")
                logger.error(f"Scraping error: {error}")

# curl_cffi
try:
    from curl_cffi import requests
    CURL_CFFI_AVAILABLE = True
except ImportError:
    import requests
    CURL_CFFI_AVAILABLE = False

logger = logging.getLogger("emmamason_brands")


class EmmaMasonUniversalScraper(ScraperErrorMixin):
    """
    Universal scraper - працює з обома форматами HTML
    
    Формат 1: Search page (ais-InfiniteHits-list)
    Формат 2: Brand page (product-item-info)
    """
    
    BASE_URL = "https://emmamason.com"
    
    BRANDS = [
        {
            "name": "Intercon Furniture", 
            "search_url": "/?q=intercon-furniture&brand=Intercon%20Furniture"
        },
        {
            "name": "ACME", 
            "search_url": "/brands-acme-furniture.html?q=Acme&brand=ACME"
        },
        {
            "name": "Aspenhome", 
            "search_url": "/?q=Aspenhome%20&brand=Aspenhome"
        },
        {
            "name": "Steve Silver", 
            "search_url": "/?q=Steve%20Silver&brand=Steve%20Silver"
        },
        {
            "name": "Westwood Design", 
            "search_url": "/?q=Westwood%20Design&brand=Westwood%20Design"
        },
        {
            "name": "Legacy Classic", 
            "search_url": "/?q=Legacy%20Classic&brand=Legacy%20Classic~Legacy%20Classic%20Kids"
        },
    ]
    
    USER_AGENTS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    ]
    
    def __init__(self, config: dict, error_logger=None):
        self.config = config
        self.error_logger = error_logger
        self.scraper_name = "EmmaMasonScraper"
        self.delay_min = config.get('delay_min', 2.0)
        self.delay_max = config.get('delay_max', 4.0)
        self.retry_attempts = config.get('retry_attempts', 3)
        self.timeout = config.get('timeout', 45)
        
        logger.info("="*60)
        logger.info("Emma Mason Universal Scraper v4.1")
        logger.info("="*60)
    
    def _random_delay(self):
        time.sleep(random.uniform(self.delay_min, self.delay_max))
    
    def _get_random_user_agent(self) -> str:
        return random.choice(self.USER_AGENTS)
    
    def _fetch_page(self, url: str, referer: Optional[str] = None) -> Optional[str]:
        """Завантажити сторінку"""
        for attempt in range(1, self.retry_attempts + 1):
            try:
                headers = {
                    "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "accept-language": "en-US,en;q=0.9",
                    "user-agent": self._get_random_user_agent(),
                }
                if referer:
                    headers["referer"] = referer
                
                if CURL_CFFI_AVAILABLE:
                    response = requests.get(
                        url, headers=headers,
                        impersonate="chrome120", timeout=self.timeout
                    )
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
                logger.error(f"Request error: {e}")
                time.sleep(3)
        
        return None
    
    def _parse_price(self, price_text: str) -> Optional[str]:
        """Парсити ціну з конвертацією коми в крапку"""
        if not price_text:
            return None
        
        try:
            cleaned = price_text.replace('$', '').replace(' ', '').strip()
            
            if not cleaned:
                return None
            
            # Конвертувати кому в крапку
            if ',' in cleaned and '.' not in cleaned:
                cleaned = cleaned.replace(',', '.')
            elif ',' in cleaned and '.' in cleaned:
                comma_pos = cleaned.index(',')
                dot_pos = cleaned.index('.')
                if dot_pos > comma_pos:
                    cleaned = cleaned.replace(',', '')
                else:
                    cleaned = cleaned.replace('.', '').replace(',', '.')
            
            float(cleaned)  # Validate
            return cleaned
                
        except Exception as e:
            logger.warning(f"Price parse failed: '{price_text}'")
            return None
    
    def _detect_html_format(self, soup: BeautifulSoup) -> str:
        """
        Визначити формат HTML
        
        Returns:
            'search' - ais-InfiniteHits format
            'brand' - product-item-info format
            'unknown' - невідомий формат
        """
        if soup.find('ol', class_='ais-InfiniteHits-list'):
            return 'search'
        elif soup.find('div', class_='product-item-info'):
            return 'brand'
        else:
            return 'unknown'
    
    def _extract_search_format(self, soup: BeautifulSoup, brand_name: str) -> List[Dict]:
        """
        Формат 1: Search page (ais-InfiniteHits)
        """
        products = []
        
        hits_list = soup.find('ol', class_='ais-InfiniteHits-list')
        if not hits_list:
            return []
        
        items = hits_list.find_all('li', class_='ais-InfiniteHits-item')
        
        for item in items:
            try:
                result_link = item.find('a', class_='result')
                if not result_link:
                    continue
                
                product_id = result_link.get('data-objectid')
                url = result_link.get('href')
                
                if not product_id or not url:
                    continue
                
                # Ціна
                price_elem = (item.find('span', class_='after_special') or
                             item.find('span', class_='price'))
                
                price = None
                if price_elem:
                    price = self._parse_price(price_elem.get_text(strip=True))
                
                products.append({
                    'id': product_id,
                    'url': url,
                    'price': price,
                    'brand': brand_name,
                    'scraped_at': datetime.now().isoformat()
                })
            
            except Exception as e:
                logger.debug(f"Failed to parse item: {e}")
                continue
        
        return products
    
    def _extract_brand_format(self, soup: BeautifulSoup, brand_name: str) -> List[Dict]:
        """
        Формат 2: Brand page (product-item-info)
        """
        products = []
        
        product_items = soup.find_all('div', class_='product-item-info')
        
        for item in product_items:
            try:
                # Product ID
                price_box = item.find('div', {'data-role': 'priceBox'})
                if not price_box:
                    continue
                
                product_id = price_box.get('data-product-id')
                if not product_id:
                    continue
                
                # URL
                link = item.find('a', class_='product-item-link')
                url = link.get('href') if link else None
                
                if not url:
                    continue
                
                # Ціна
                price_elem = item.find('span', class_='price')
                price = None
                if price_elem:
                    price = self._parse_price(price_elem.get_text(strip=True))
                
                products.append({
                    'id': product_id,
                    'url': url,
                    'price': price,
                    'brand': brand_name,
                    'scraped_at': datetime.now().isoformat()
                })
            
            except Exception as e:
                logger.debug(f"Failed to parse item: {e}")
                continue
        
        return products
    
    def _extract_products_universal(self, html: str, brand_name: str) -> tuple:
        """
        Універсальний метод - визначає формат і парсить
        
        Returns:
            (products, format_used)
        """
        soup = BeautifulSoup(html, 'html.parser')
        
        # Визначити формат
        html_format = self._detect_html_format(soup)
        
        if html_format == 'search':
            products = self._extract_search_format(soup, brand_name)
            return products, 'search'
        
        elif html_format == 'brand':
            products = self._extract_brand_format(soup, brand_name)
            return products, 'brand'
        
        else:
            logger.warning(f"  Unknown HTML format for {brand_name}")
            return [], 'unknown'
    
    def _has_more_pages(self, soup: BeautifulSoup, html_format: str) -> bool:
        """Перевірити чи є наступна сторінка"""
        if html_format == 'search':
            # Search format - шукати кнопку "Show more"
            button = soup.find('button', class_='ais-InfiniteHits-loadMore')
            return button is not None
        
        elif html_format == 'brand':
            # Brand format - шукати next page link
            next_link = soup.find('a', class_='action next')
            return next_link is not None
        
        return False
    
    def scrape_brand(self, brand_info: dict, seen_ids: Set[str]) -> List[Dict]:
        """Парсити бренд (універсально)"""
        brand_name = brand_info['name']
        search_url = brand_info['search_url']
        
        logger.info(f"Processing brand: {brand_name}")
        
        brand_products = []
        page = 1
        html_format = None
        
        while True:
            # URL
            if '?' in search_url:
                url = f"{self.BASE_URL}{search_url}&page={page}"
            else:
                url = f"{self.BASE_URL}{search_url}?page={page}"
            
            logger.debug(f"  Page {page}: {url}")
            
            # Fetch
            html = self._fetch_page(url, referer=self.BASE_URL)
            
            if not html:
                logger.error(f"  Failed to fetch page {page}")
                break
            
            # Cloudflare check
            if "Just a moment" in html or "Checking your browser" in html:
                logger.warning(f"  Cloudflare detected")
                break
            
            # Parse (universal)
            products, detected_format = self._extract_products_universal(html, brand_name)
            
            # Запам'ятати формат
            if html_format is None and detected_format != 'unknown':
                html_format = detected_format
                logger.info(f"  Detected HTML format: {html_format}")
            
            # Якщо немає товарів - остання сторінка
            if not products:
                logger.info(f"  No products on page {page}")
                break
            
            # Дедуплікація
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
            
            logger.info(f"  Page {page}: {new_count} new, {duplicate_count} dup (total: {len(brand_products)})")
            
            # Перевірити чи є наступна сторінка
            soup = BeautifulSoup(html, 'html.parser')
            has_more = self._has_more_pages(soup, html_format or 'unknown')
            
            if not has_more:
                logger.info(f"  Last page reached")
                break
            
            # Захист
            if page >= 100:
                logger.warning(f"  Page limit (100)")
                break
            
            page += 1
            self._random_delay()
        
        logger.info(f"✓ Brand {brand_name}: {len(brand_products)} products")
        
        return brand_products
    
    def scrape_all_brands(self) -> List[Dict]:
        """Парсити всі бренди"""
        all_products = []
        seen_ids = set()
        
        try:
            for brand_info in self.BRANDS:
                try:
                    products = self.scrape_brand(brand_info, seen_ids)
                    all_products.extend(products)
                    
                except Exception as e:
                    self.log_scraping_error(error=e, context={'brand': brand_info['name']})
                    logger.error(f"Failed {brand_info['name']}: {e}")
                    continue
                
                time.sleep(3)
        
        except Exception as e:
            self.log_scraping_error(error=e, context={'stage': 'main'})
            raise
        
        # Stats
        logger.info("\n" + "="*60)
        logger.info("SCRAPING COMPLETED")
        logger.info("="*60)
        logger.info(f"Total products: {len(all_products)}")
        logger.info(f"Unique IDs: {len(seen_ids)}")
        
        brands_stats = {}
        for p in all_products:
            brand = p['brand']
            brands_stats[brand] = brands_stats.get(brand, 0) + 1
        
        logger.info("\nBy brand:")
        for brand, count in brands_stats.items():
            logger.info(f"  {brand}: {count}")
        logger.info("="*60)
        
        return all_products


def scrape_emmamason_brands(config: dict, error_logger=None) -> List[Dict]:
    """Main function"""
    scraper = EmmaMasonUniversalScraper(config, error_logger)
    return scraper.scrape_all_brands()


if __name__ == "__main__":
    import logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s | %(levelname)-8s | %(message)s',
        datefmt='%H:%M:%S'
    )
    
    config = {
        'delay_min': 2.0,
        'delay_max': 4.0,
        'retry_attempts': 3,
        'timeout': 45
    }
    
    print("\n" + "="*60)
    print("ТЕСТ UNIVERSAL SCRAPER v4.1")
    print("="*60 + "\n")
    
    results = scrape_emmamason_brands(config)
    
    print(f"\n✅ РЕЗУЛЬТАТ: {len(results)} products")
