"""
Emma Mason Smart Scraper Wrapper v5.2
✅ Спробує Algolia API v5.1 (швидко, 7000+ товарів)
✅ Якщо key expired → auto-refresh через Playwright
✅ Якщо не вдалося → fallback на HTML v3 (повільно, 600+ товарів)
✅ Telegram notifications
✅ Повністю автономний для хостингу
"""

import logging
import time
import re
from typing import List, Dict, Optional
from datetime import datetime
from pathlib import Path

# Импорти scrapers
from .emmamason_algolia_v5_1 import EmmaMasonAlgoliaScraperV5_1
from .emmamason_brands import EmmaMasonBrandsScraper as EmmaMasonHTMLScraper

logger = logging.getLogger("emmamason_smart")


class AlgoliaAPIKeyExpired(Exception):
    """Exception коли Algolia API key expired"""
    pass


class EmmaMasonSmartScraper:
    """
    Розумний wrapper для Emma Mason scraping
    
    Стратегія:
    1. Algolia API v5.1 (primary) - швидко, 7000+ товарів
    2. Auto-refresh API key (якщо expired)
    3. HTML v3 fallback (якщо все не працює) - повільно, 600+ товарів
    """
    
    def __init__(self, config: dict, error_logger=None, telegram_bot=None):
        """
        Ініціалізація
        
        Args:
            config: Scraper configuration
            error_logger: ErrorLogger instance (optional)
            telegram_bot: Telegram bot для notifications (optional)
        """
        self.config = config
        self.error_logger = error_logger
        self.telegram_bot = telegram_bot
        
        self.api_key_last_update = None
        self.scraping_method = None  # 'algolia' або 'html'
        
        logger.info("="*60)
        logger.info("Emma Mason Smart Scraper v5.2")
        logger.info("="*60)
        logger.info("Strategy: Algolia API → Auto-refresh → HTML Fallback")
    
    def scrape_all_brands(self) -> List[Dict]:
        """
        Головний метод scraping
        
        Returns:
            Список товарів
        """
        start_time = time.time()
        
        # ══════════════════════════════════════════════════════════
        # КРОК 1: Спробувати Algolia API v5.1
        # ══════════════════════════════════════════════════════════
        logger.info("\n[STEP 1] Attempting Algolia API v5.1...")
        
        try:
            products = self._try_algolia_api()
            
            if products and len(products) >= 5000:
                duration = time.time() - start_time
                self.scraping_method = 'algolia'
                
                logger.info("="*60)
                logger.info(f"✅ SUCCESS: Algolia API")
                logger.info(f"Products: {len(products)}")
                logger.info(f"Time: {duration:.1f}s")
                logger.info("="*60)
                
                self._send_notification(
                    "✅ Emma Mason: Algolia API Success",
                    f"Products: {len(products)}\n"
                    f"Time: {duration:.1f}s\n"
                    f"Method: Algolia API v5.1"
                )
                
                return products
            
            else:
                logger.warning(f"⚠️  Low product count: {len(products) if products else 0}")
                raise AlgoliaAPIKeyExpired("Possible expired key (low count)")
        
        except AlgoliaAPIKeyExpired as e:
            logger.warning(f"Algolia API key issue detected: {e}")
            
            # ══════════════════════════════════════════════════════════
            # КРОК 2: Спробувати auto-refresh API key
            # ══════════════════════════════════════════════════════════
            logger.info("\n[STEP 2] Attempting API key auto-refresh...")
            
            if self._try_auto_refresh_api_key():
                logger.info("✅ API key refreshed successfully, retrying Algolia...")
                
                try:
                    products = self._try_algolia_api()
                    
                    if products and len(products) >= 5000:
                        duration = time.time() - start_time
                        self.scraping_method = 'algolia'
                        
                        logger.info("="*60)
                        logger.info(f"✅ SUCCESS: Algolia API (after refresh)")
                        logger.info(f"Products: {len(products)}")
                        logger.info(f"Time: {duration:.1f}s")
                        logger.info("="*60)
                        
                        self._send_notification(
                            "✅ Emma Mason: API Key Auto-Refreshed",
                            f"API key було автоматично оновлено!\n\n"
                            f"Products: {len(products)}\n"
                            f"Time: {duration:.1f}s\n"
                            f"Method: Algolia API v5.1"
                        )
                        
                        return products
                
                except Exception as e2:
                    logger.error(f"Algolia failed after refresh: {e2}")
        
        except Exception as e:
            logger.error(f"Algolia API failed: {e}")
        
        # ══════════════════════════════════════════════════════════
        # КРОК 3: Fallback на HTML v3 scraping
        # ══════════════════════════════════════════════════════════
        logger.warning("\n[STEP 3] Falling back to HTML scraping v3...")
        
        self._send_notification(
            "⚠️ Emma Mason: Fallback to HTML",
            "Algolia API не працює (можливо expired key).\n"
            "Auto-refresh не вдався або Playwright не встановлено.\n\n"
            "Використовується HTML scraping v3 (повільніше).\n\n"
            "❗ Рекомендація: Оновити Algolia API key вручну для кращої швидкості."
        )
        
        try:
            products = self._try_html_scraping()
            duration = time.time() - start_time
            self.scraping_method = 'html'
            
            logger.info("="*60)
            logger.info(f"✅ SUCCESS: HTML Fallback")
            logger.info(f"Products: {len(products)}")
            logger.info(f"Time: {duration:.1f}s")
            logger.info("="*60)
            
            self._send_notification(
                "✅ Emma Mason: HTML Fallback Success",
                f"Products: {len(products)}\n"
                f"Time: {duration:.1f}s\n"
                f"Method: HTML Scraping v3\n\n"
                f"Note: Повільніше за API, але працює.\n"
                f"Для кращої швидкості оновіть API key."
            )
            
            return products
        
        except Exception as e:
            logger.error(f"❌ HTML scraping also failed: {e}")
            
            self._send_notification(
                "🚨 Emma Mason: CRITICAL ERROR",
                f"Algolia API failed\n"
                f"Auto-refresh failed\n"
                f"HTML scraping failed: {e}\n\n"
                f"❗ ПОТРІБНА НЕГАЙНА УВАГА!"
            )
            
            # Log error
            if self.error_logger:
                self.error_logger.log_error(
                    "EmmaMasonSmartScraper",
                    e,
                    context={'all_methods_failed': True}
                )
            
            return []
    
    def _try_algolia_api(self) -> List[Dict]:
        """
        Спробувати Algolia API v5.1
        
        Returns:
            Список товарів
        
        Raises:
            AlgoliaAPIKeyExpired: Якщо ключ expired
            Exception: Інші помилки
        """
        try:
            scraper = EmmaMasonAlgoliaScraperV5_1(self.config, self.error_logger)
            products = scraper.scrape_all_brands()
            
            # Перевірити результат
            if not products:
                raise AlgoliaAPIKeyExpired("No products returned")
            
            if len(products) < 1000:
                logger.warning(f"Low product count: {len(products)} (expected >5000)")
                raise AlgoliaAPIKeyExpired(f"Low count: {len(products)}")
            
            return products
        
        except Exception as e:
            error_str = str(e).lower()
            
            # Детектувати expired key
            if any(keyword in error_str for keyword in [
                '403', 'forbidden', 'invalid api key', 'unauthorized',
                'low count', 'no products'
            ]):
                raise AlgoliaAPIKeyExpired(f"API key issue: {e}")
            
            # Інша помилка
            raise
    
    def _try_auto_refresh_api_key(self) -> bool:
        """
        Спробувати автоматично оновити Algolia API key через Playwright
        
        Returns:
            True якщо успішно
        """
        logger.info("Attempting to auto-refresh API key via Playwright...")
        
        try:
            # Імпортувати Playwright
            try:
                from playwright.sync_api import sync_playwright
            except ImportError:
                logger.error("Playwright not installed!")
                logger.error("Install: pip install playwright")
                logger.error("Then: playwright install chromium")
                return False
            
            # Отримати новий ключ
            new_key = self._fetch_api_key_playwright()
            
            if not new_key:
                logger.error("Failed to fetch new API key")
                return False
            
            # Оновити в файлі
            if self._update_api_key_in_file(new_key):
                self.api_key_last_update = datetime.now()
                logger.info(f"✅ API key updated at {self.api_key_last_update}")
                return True
            
            return False
        
        except Exception as e:
            logger.error(f"Auto-refresh failed: {e}")
            return False
    
    def _fetch_api_key_playwright(self) -> Optional[str]:
        """
        Отримати новий API key через Playwright
        
        Returns:
            Новий API key або None
        """
        try:
            from playwright.sync_api import sync_playwright
            
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                context = browser.new_context()
                page = context.new_page()
                
                api_key = None
                
                def handle_request(request):
                    nonlocal api_key
                    if 'algolia.net' in request.url:
                        headers = request.headers
                        if 'x-algolia-api-key' in headers:
                            api_key = headers['x-algolia-api-key']
                            logger.info(f"✅ Found API key: {api_key[:20]}...")
                
                page.on('request', handle_request)
                
                try:
                    logger.info("Loading emmamason.com...")
                    page.goto('https://emmamason.com/', timeout=30000)
                    page.wait_for_load_state('networkidle')
                    
                    # Trigger search
                    logger.info("Triggering search to get API key...")
                    search = page.locator('input[type="search"], input.search-field').first
                    
                    if search.is_visible():
                        search.fill('furniture')
                        time.sleep(2)
                    
                    time.sleep(1)
                    
                    return api_key
                
                finally:
                    browser.close()
        
        except Exception as e:
            logger.error(f"Playwright error: {e}")
            return None
    
    def _update_api_key_in_file(self, new_key: str) -> bool:
        """
        Оновити API key в emmamason_algolia_v5_1.py
        
        Args:
            new_key: Новий API key
        
        Returns:
            True якщо успішно
        """
        try:
            file_path = Path(__file__).parent / 'emmamason_algolia_v5_1.py'
            
            # Читати файл
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Backup
            backup_path = file_path.with_suffix('.py.backup')
            with open(backup_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            logger.info(f"Created backup: {backup_path}")
            
            # Замінити ключ
            pattern = r'ALGOLIA_API_KEY = "[^"]+"'
            replacement = f'ALGOLIA_API_KEY = "{new_key}"'
            
            new_content = re.sub(pattern, replacement, content)
            
            if new_content == content:
                logger.error("Failed to replace API key (pattern not found)")
                return False
            
            # Записати
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(new_content)
            
            logger.info(f"✅ API key updated in {file_path}")
            
            return True
        
        except Exception as e:
            logger.error(f"Failed to update file: {e}")
            return False
    
    def _try_html_scraping(self) -> List[Dict]:
        """
        Fallback: HTML scraping v3
        
        Returns:
            Список товарів
        """
        try:
            # HTML config (більші затримки для bypass Cloudflare)
            html_config = self.config.copy()
            html_config['delay_min'] = 3.0
            html_config['delay_max'] = 6.0
            
            scraper = EmmaMasonHTMLScraper(html_config, self.error_logger)
            products = scraper.scrape_all_brands()
            
            return products
        
        except Exception as e:
            logger.error(f"HTML scraping failed: {e}")
            raise
    
    def _send_notification(self, title: str, message: str):
        """
        Відправити Telegram notification
        
        Args:
            title: Заголовок
            message: Повідомлення
        """
        if not self.telegram_bot:
            logger.debug("Telegram bot not configured")
            return
        
        try:
            full_message = f"*{title}*\n\n{message}"
            
            # Якщо є метод send_message
            if hasattr(self.telegram_bot, 'send_message'):
                self.telegram_bot.send_message(full_message)
            # Якщо це просто функція
            elif callable(self.telegram_bot):
                self.telegram_bot(full_message)
            
            logger.info(f"✅ Telegram notification sent: {title}")
        
        except Exception as e:
            logger.error(f"Failed to send notification: {e}")


# ══════════════════════════════════════════════════════════════════
# Compatibility wrapper для існуючого коду
# ══════════════════════════════════════════════════════════════════

class EmmaMasonBrandsScraper:
    """
    Compatibility wrapper - виглядає як старий scraper
    але використовує smart wrapper
    """
    
    def __init__(self, config: dict, error_logger=None, telegram_bot=None):
        """
        Ініціалізація
        
        Args:
            config: Configuration dict
            error_logger: ErrorLogger instance (optional)
            telegram_bot: Telegram bot (optional)
        """
        self.smart_scraper = EmmaMasonSmartScraper(
            config=config,
            error_logger=error_logger,
            telegram_bot=telegram_bot
        )
    
    def scrape_all_brands(self) -> List[Dict]:
        """
        Scrape всі бренди (compatibility method)
        
        Returns:
            Список товарів
        """
        return self.smart_scraper.scrape_all_brands()


if __name__ == "__main__":
    import logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s | %(levelname)-8s | %(message)s',
        datefmt='%H:%M:%S'
    )
    
    config = {
        'delay_min': 0.5,
        'delay_max': 1.5,
        'retry_attempts': 3,
        'timeout': 30,
        'hits_per_page': 1000
    }
    
    print("\n" + "="*60)
    print("SMART SCRAPER TEST")
    print("="*60 + "\n")
    
    scraper = EmmaMasonBrandsScraper(config)
    results = scraper.scrape_all_brands()
    
    print(f"\n✅ RESULT: {len(results)} products")
    print(f"Method: {scraper.smart_scraper.scraping_method}")
