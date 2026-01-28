"""
Emma Mason Smart Scraper Wrapper v5.2.1 - FIXED
✅ Спробує Algolia API v5.1 (швидко, 7000+ товарів)
✅ Якщо key expired → auto-refresh через Playwright
✅ Якщо не вдалося → fallback на HTML v3 (повільно, 600+ товарів)
✅ Telegram notifications
✅ Повністю автономний для хостингу
✅ ВИПРАВЛЕНО v2.1: Playwright відкриває search URL (emmamason.com/?q=...)
✅ ВИПРАВЛЕНО v2.1: Правильний regex для заміни API key в файлі
"""

import logging
import time
import re
from typing import List, Dict, Optional
from datetime import datetime
from pathlib import Path

# Импорти scrapers
from .emmamason_algolia_v5_1 import (
    EmmaMasonAlgoliaScraperV5_1,
    AlgoliaAPIKeyExpired
)
from .emmamason_brands import EmmaMasonBrandsScraper as EmmaMasonHTMLScraper

logger = logging.getLogger("emmamason_smart")


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
        logger.info("Emma Mason Smart Scraper v5.2 (FIXED)")
        logger.info("="*60)
        logger.info("Strategy: Algolia API → Auto-refresh → HTML Fallback")
    
    def scrape_all_brands(self) -> List[Dict]:
        """
        Головний метод scraping з автоматичним fallback
        
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
            
            # Перевірка результату
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
                # Мало товарів - можливо expired key
                logger.warning(f"⚠️  Low product count: {len(products) if products else 0}")
                raise AlgoliaAPIKeyExpired(f"Low count: {len(products) if products else 0}")
        
        except AlgoliaAPIKeyExpired as e:
            logger.warning(f"Algolia API key issue detected: {e}")
            
            # ══════════════════════════════════════════════════════════
            # КРОК 2: Спробувати auto-refresh API key
            # ══════════════════════════════════════════════════════════
            logger.info("\n[STEP 2] Attempting API key auto-refresh...")
            
            if self._try_auto_refresh_api_key():
                logger.info("✅ API key refreshed successfully, retrying Algolia...")
                
                # Повторна спроба з новим ключем
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
                    
                    else:
                        logger.warning(f"Still low count after refresh: {len(products) if products else 0}")
                
                except Exception as e2:
                    logger.error(f"Algolia failed after refresh: {e2}")
            
            else:
                logger.warning("Auto-refresh failed or Playwright not available")
        
        except Exception as e:
            logger.error(f"Algolia API failed: {e}")
            
            # Якщо це не AlgoliaAPIKeyExpired - можливо network issue
            # Спробувати refresh на всяк випадок
            if "timeout" not in str(e).lower() and "connection" not in str(e).lower():
                logger.info("Attempting refresh as precaution...")
                self._try_auto_refresh_api_key()
        
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
        # AlgoliaAPIKeyExpired exception автоматично передається вгору
        scraper = EmmaMasonAlgoliaScraperV5_1(self.config, self.error_logger)
        products = scraper.scrape_all_brands()
        return products
    
    def _try_auto_refresh_api_key(self) -> bool:
        """
        Спробувати автоматично оновити API key через Playwright
        
        Returns:
            True якщо успішно
        """
        try:
            # Перевірити чи встановлено Playwright
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
                
                # ✅ КРИТИЧНО: Оновити ключ в поточному scraper class
                EmmaMasonAlgoliaScraperV5_1.ALGOLIA_API_KEY = new_key
                logger.info("✅ API key reloaded in memory")
                
                return True
            
            return False
        
        except Exception as e:
            logger.error(f"Auto-refresh failed: {e}")
            return False
    
    def _fetch_api_key_playwright(self) -> Optional[str]:
        """
        Отримати новий API key через Playwright
        
        ✅ ВАЖЛИВО: Algolia використовується ТІЛЬКИ для search!
        Тому треба обов'язково тригернути search запит.
        
        Returns:
            Новий API key або None
        """
        try:
            from playwright.sync_api import sync_playwright
            
            with sync_playwright() as p:
                logger.info("Launching browser...")
                browser = p.chromium.launch(headless=True)
                
                # User agent для bypass detection
                context = browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36"
                )
                
                page = context.new_page()
                
                api_key = None
                request_count = 0
                
                def handle_request(request):
                    nonlocal api_key, request_count
                    
                    # Перехопити всі Algolia запити
                    if 'algolia.net' in request.url:
                        request_count += 1
                        logger.debug(f"Algolia request #{request_count}: {request.url[:80]}...")
                        
                        headers = request.headers
                        if 'x-algolia-api-key' in headers:
                            key = headers['x-algolia-api-key']
                            if key and len(key) > 20:  # Валідний ключ
                                api_key = key
                                logger.info(f"✅ Found API key: {api_key[:30]}...")
                
                page.on('request', handle_request)
                
                try:
                    # ═══════════════════════════════════════════════════════
                    # МЕТОД 1: Прямий URL з search query (найкраще!)
                    # ═══════════════════════════════════════════════════════
                    logger.info("Method 1: Loading search URL directly...")
                    
                    # Завантажити сторінку з search query
                    page.goto('https://emmamason.com/?q=furniture', timeout=40000)
                    
                    logger.info("Waiting for search results...")
                    page.wait_for_load_state('domcontentloaded', timeout=30000)
                    
                    # Почекати щоб Algolia зробив запит
                    time.sleep(3)
                    
                    if api_key:
                        logger.info(f"✅ Method 1 (direct search URL) succeeded!")
                        logger.info(f"   Captured after {request_count} Algolia requests")
                        return api_key
                    
                    # ═══════════════════════════════════════════════════════
                    # МЕТОД 2: Тригернути search через input
                    # ═══════════════════════════════════════════════════════
                    logger.info("Method 1 failed, trying Method 2 (trigger search input)...")
                    
                    # Спробувати знайти search input
                    selectors = [
                        'input[type="search"]',
                        'input[name="q"]',
                        'input.search-field',
                        '#search',
                        '[placeholder*="Search"]',
                        '[placeholder*="search"]'
                    ]
                    
                    for selector in selectors:
                        try:
                            search_input = page.locator(selector).first
                            
                            if search_input.is_visible(timeout=2000):
                                logger.debug(f"Found search input: {selector}")
                                
                                # Ввести текст і почекати
                                search_input.click(timeout=2000)
                                search_input.fill('furniture', timeout=2000)
                                
                                # Можливо потрібно натиснути Enter
                                search_input.press('Enter', timeout=2000)
                                
                                # Почекати поки Algolia зробить запит
                                time.sleep(3)
                                
                                if api_key:
                                    logger.info(f"✅ Method 2 (search input) succeeded!")
                                    return api_key
                        
                        except Exception:
                            continue
                    
                    # ═══════════════════════════════════════════════════════
                    # МЕТОД 3: JavaScript eval window object
                    # ═══════════════════════════════════════════════════════
                    logger.info("Method 2 failed, trying Method 3 (JavaScript eval)...")
                    
                    try:
                        js_code = """
                        () => {
                            // Шукати в різних можливих місцях
                            if (window.algoliaConfig && window.algoliaConfig.apiKey) {
                                return window.algoliaConfig.apiKey;
                            }
                            
                            if (window.algoliaBundle && window.algoliaBundle.config) {
                                return window.algoliaBundle.config.apiKey;
                            }
                            
                            if (window.algoliasearch && window.algoliasearch._config) {
                                return window.algoliasearch._config.apiKey;
                            }
                            
                            return null;
                        }
                        """
                        
                        js_api_key = page.evaluate(js_code)
                        
                        if js_api_key and len(js_api_key) > 20:
                            api_key = js_api_key
                            logger.info(f"✅ Method 3 (JavaScript) succeeded: {api_key[:30]}...")
                            return api_key
                    
                    except Exception as e:
                        logger.debug(f"JavaScript eval failed: {e}")
                    
                    # ═══════════════════════════════════════════════════════
                    # МЕТОД 4: Спробувати різні search URLs
                    # ═══════════════════════════════════════════════════════
                    logger.info("Method 3 failed, trying Method 4 (alternative search URLs)...")
                    
                    search_urls = [
                        'https://emmamason.com/?q=table',
                        'https://emmamason.com/?q=bed',
                        'https://emmamason.com/?q=chair',
                    ]
                    
                    for url in search_urls:
                        try:
                            logger.debug(f"Trying: {url}")
                            page.goto(url, timeout=30000)
                            page.wait_for_load_state('domcontentloaded', timeout=20000)
                            time.sleep(3)
                            
                            if api_key:
                                logger.info(f"✅ Method 4 (alternative URL) succeeded!")
                                return api_key
                        
                        except Exception:
                            continue
                    
                    # ═══════════════════════════════════════════════════════
                    # Всі методи не вдалися
                    # ═══════════════════════════════════════════════════════
                    logger.error(f"❌ All 4 methods failed to capture API key")
                    logger.error(f"   Total Algolia requests intercepted: {request_count}")
                    logger.error("")
                    logger.error("Possible reasons:")
                    logger.error("  1. Cloudflare blocking headless browser")
                    logger.error("  2. JavaScript not loading properly")
                    logger.error("  3. Algolia search temporarily disabled")
                    logger.error("")
                    logger.error("Solution: Get API key manually from browser DevTools")
                    logger.error("See: MANUAL_API_KEY_UPDATE.md")
                    
                    return None
                
                finally:
                    browser.close()
        
        except Exception as e:
            logger.error(f"Playwright error: {e}")
            import traceback
            logger.debug(traceback.format_exc())
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
            
            if not file_path.exists():
                logger.error(f"File not found: {file_path}")
                return False
            
            # Читати файл
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Backup
            backup_path = file_path.with_suffix('.py.backup')
            with open(backup_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            logger.info(f"Created backup: {backup_path}")
            
            # ✅ ВИПРАВЛЕНО: Правильний regex pattern
            # Шукає: ALGOLIA_API_KEY = "будь-що"
            # Важливо: (?!.*#) - не має бути # перед рядком (не закоментовано)
            pattern = r'^(\s*ALGOLIA_API_KEY\s*=\s*)"[^"]+"'
            replacement = r'\1"' + new_key + '"'
            
            # Замінити тільки першу активну (не закоментовану) лінію
            lines = content.split('\n')
            replaced = False
            
            for i, line in enumerate(lines):
                # Шукати активну лінію (без # на початку)
                if 'ALGOLIA_API_KEY' in line and not line.strip().startswith('#'):
                    # Замінити
                    new_line = re.sub(
                        r'(ALGOLIA_API_KEY\s*=\s*)"[^"]+"',
                        r'\1"' + new_key + '"',
                        line
                    )
                    
                    if new_line != line:
                        lines[i] = new_line
                        replaced = True
                        logger.info(f"Replaced line {i+1}: ALGOLIA_API_KEY = \"{new_key[:30]}...\"")
                        break
            
            if not replaced:
                logger.error("Failed to find ALGOLIA_API_KEY line (not commented)")
                return False
            
            new_content = '\n'.join(lines)
            
            # Записати
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(new_content)
            
            logger.info(f"✅ API key updated in {file_path}")
            
            return True
        
        except Exception as e:
            logger.error(f"Failed to update file: {e}")
            import traceback
            logger.debug(traceback.format_exc())
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


# if __name__ == "__main__":
#     import logging
#     logging.basicConfig(
#         level=logging.INFO,
#         format='%(asctime)s | %(levelname)-8s | %(message)s',
#         datefmt='%H:%M:%S'
#     )
    
#     config = {
#         'delay_min': 0.5,
#         'delay_max': 1.5,
#         'retry_attempts': 3,
#         'timeout': 30,
#         'hits_per_page': 1000
#     }
    
#     print("\n" + "="*60)
#     print("SMART SCRAPER TEST (FIXED)")
#     print("="*60 + "\n")
    
#     scraper = EmmaMasonBrandsScraper(config)
#     results = scraper.scrape_all_brands()
    
#     print(f"\n✅ RESULT: {len(results)} products")
#     print(f"Method: {scraper.smart_scraper.scraping_method}")
