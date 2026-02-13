"""
Emma Mason Smart Scraper Wrapper
Try Algolia API (fast, 7000+ products)
    If key expired -> auto-refresh via Playwright
    If failed -> fallback to HTML v3 (slow, 600+ products)
    Telegram notifications
    Fully autonomous for hosting
    Playwright opens search URL (emmamason.com/?q=...)
    Correct regex for replacing API key in file
"""

import logging
import time
import re
from typing import List, Dict, Optional
from datetime import datetime
from pathlib import Path

# Import scrapers
from .emmamason_algolia_v5_1 import (
    EmmaMasonAlgoliaScraperV5_1,
    AlgoliaAPIKeyExpired
)
from .emmamason_brands import EmmaMasonBrandsScraper as EmmaMasonHTMLScraper

logger = logging.getLogger("emmamason_smart")

class EmmaMasonSmartScraper:
    """
    Smart wrapper for Emma Mason scraping

    Strategy:
        1. Algolia API (primary) - fast, 7000+ products
        2. Auto-refresh API key (if expired)
        3. HTML v3 fallback (if everything else fails) - slow, 600+ products
    """

    def __init__(self, config: dict, error_logger=None, telegram_bot=None):
        """
        Initialization

        Args:
            config: Scraper configuration
            error_logger: ErrorLogger instance (optional)
            telegram_bot: Telegram bot for notifications (optional)
        """
        self.config = config
        self.error_logger = error_logger
        self.telegram_bot = telegram_bot

        self.api_key_last_update = None
        self.scraping_method = None  # 'algolia' or 'html'

        logger.info("="*60)
        logger.info("Emma Mason Smart Scraper v5.2 (FIXED)")
        logger.info("="*60)
        logger.info("Strategy: Algolia API → Auto-refresh → HTML Fallback")

    def scrape_all_brands(self) -> List[Dict]:
        """
        Main scraping method with automatic fallback

        Returns:
            List of products
        """
        start_time = time.time()


        # Step 1: Try Algolia API

        logger.info("\n[STEP 1] Attempting Algolia API v5.1...")

        try:
            products = self._try_algolia_api()

            # Check result
            if products and len(products) >= 5000:
                duration = time.time() - start_time
                self.scraping_method = 'algolia'

                logger.info("="*60)
                logger.info(f"[OK] SUCCESS: Algolia API")
                logger.info(f"Products: {len(products)}")
                logger.info(f"Time: {duration:.1f}s")
                logger.info("="*60)

                self._send_notification(
                    "[OK] Emma Mason: Algolia API Success",
                    f"Products: {len(products)}\n"
                    f"Time: {duration:.1f}s\n"
                    f"Method: Algolia API v5.1"
                )

                return products

            else:
                # Few products - possibly expired key
                logger.warning(f"[!]  Low product count: {len(products) if products else 0}")
                raise AlgoliaAPIKeyExpired(f"Low count: {len(products) if products else 0}")

        except AlgoliaAPIKeyExpired as e:
            logger.warning(f"Algolia API key issue detected: {e}")

    
            # Step 2: Try auto-refresh API key
    
            logger.info("\n[STEP 2] Attempting API key auto-refresh...")

            if self._try_auto_refresh_api_key():
                logger.info("[OK] API key refreshed successfully, retrying Algolia...")

                # Retry with a new key
                try:
                    products = self._try_algolia_api()

                    if products and len(products) >= 5000:
                        duration = time.time() - start_time
                        self.scraping_method = 'algolia'

                        logger.info("="*60)
                        logger.info(f"[OK] SUCCESS: Algolia API (after refresh)")
                        logger.info(f"Products: {len(products)}")
                        logger.info(f"Time: {duration:.1f}s")
                        logger.info("="*60)

                        self._send_notification(
                            "Emma Mason: API Key Auto-Refreshed",
                            f"API key was automatically updated!\n\n"
                            f"Products: {len(products)}\n"
                            f"Time: {duration:.1f}s\n"
                            f"Method: Algolia API"
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

            # If it's not AlgoliaAPIKeyExpired - possibly a network issue
            # Try refreshing just in case
            if "timeout" not in str(e).lower() and "connection" not in str(e).lower():
                logger.info("Attempting refresh as precaution...")
                self._try_auto_refresh_api_key()


        # STEP 3: Fallback to HTML v3 scraping

        logger.warning("\n[STEP 3] Falling back to HTML scraping v3...")

        self._send_notification(
            "Emma Mason: Fallback to HTML",
            "Algolia API is not working (possibly expired key).\n"
            "Auto-refresh failed or Playwright is not installed.\n\n"
            "HTML scraping v3 is used.\n\n"
            "[!] Recommendation: Update the Algolia API key manually for better speed."
        )

        try:
            products = self._try_html_scraping()
            duration = time.time() - start_time
            self.scraping_method = 'html'

            logger.info("="*60)
            logger.info(f"[OK] SUCCESS: HTML Fallback")
            logger.info(f"Products: {len(products)}")
            logger.info(f"Time: {duration:.1f}s")
            logger.info("="*60)

            self._send_notification(
                "Emma Mason: HTML Fallback Success",
                f"Products: {len(products)}\n"
                f"Time: {duration:.1f}s\n"
                f"Method: HTML Scraping v3\n\n"
                f"Note: Slower than API, but it works.\n"
                f"For better speed, update your API key."
            )

            return products

        except Exception as e:
            logger.error(f"[X] HTML scraping also failed: {e}")

            self._send_notification(
                "Emma Mason: CRITICAL ERROR",
                f"Algolia API failed\n"
                f"Auto-refresh failed\n"
                f"HTML scraping failed: {e}\n\n"
                f"[!] IMMEDIATE ATTENTION REQUIRED!"
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
        Try Algolia API v5.1

        Returns:
            List of products

        Raises:
            AlgoliaAPIKeyExpired: If the key has expired
            Exception: Other errors
        """
        # AlgoliaAPIKeyExpired exception automatically transferred upwards
        scraper = EmmaMasonAlgoliaScraperV5_1(self.config, self.error_logger)
        products = scraper.scrape_all_brands()
        return products

    def _try_auto_refresh_api_key(self) -> bool:
        """
        Try to automatically refresh API key via Playwright

        Returns:
            True if successful
        """
        try:
            # Check if Playwright is installed
            try:
                from playwright.sync_api import sync_playwright
            except ImportError:
                logger.error("Playwright not installed!")
                logger.error("Install: pip install playwright")
                logger.error("Then: playwright install chromium")
                return False

            # Get new key
            new_key = self._fetch_api_key_playwright()

            if not new_key:
                logger.error("Failed to fetch new API key")
                return False

            # Update in file
            if self._update_api_key_in_file(new_key):
                self.api_key_last_update = datetime.now()
                logger.info(f"[OK] API key updated at {self.api_key_last_update}")

                # Update key in current scraper class
                EmmaMasonAlgoliaScraperV5_1.ALGOLIA_API_KEY = new_key
                logger.info("[OK] API key reloaded in memory")

                return True

            return False

        except Exception as e:
            logger.error(f"Auto-refresh failed: {e}")
            return False

    def _fetch_api_key_playwright(self) -> Optional[str]:
        """
        Get new API key via Playwright

        Algolia is used ONLY for search!
        Therefore, you must trigger a search query.

        Returns:
        New API key or None
        """
        try:
            from playwright.sync_api import sync_playwright

            with sync_playwright() as p:
                logger.info("Launching browser...")
                browser = p.chromium.launch(headless=True)

                # User agent for bypass detection
                context = browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36"
                )

                page = context.new_page()

                api_key = None
                request_count = 0

                def handle_request(request):
                    nonlocal api_key, request_count

                    # Intercept all Algolia requests
                    if 'algolia.net' in request.url:
                        request_count += 1
                        logger.debug(f"Algolia request #{request_count}: {request.url[:80]}...")

                        headers = request.headers
                        if 'x-algolia-api-key' in headers:
                            key = headers['x-algolia-api-key']
                            if key and len(key) > 20:  # Valid key
                                api_key = key
                                logger.info(f"[OK] Found API key: {api_key[:30]}...")

                page.on('request', handle_request)

                try:
                    # METHOD 1: Direct URL with search query (best!)
                    logger.info("Method 1: Loading search URL directly...")

                    # Load page with search query
                    page.goto('https://emmamason.com/?q=furniture', timeout=40000)

                    logger.info("Waiting for search results...")
                    page.wait_for_load_state('domcontentloaded', timeout=30000)

                    # Wait for Algolia to make a request
                    time.sleep(3)

                    if api_key:
                        logger.info(f"[OK] Method 1 (direct search URL) succeeded!")
                        logger.info(f"   Captured after {request_count} Algolia requests")
                        return api_key

                    # METHOD 2: Trigger search via input
                    logger.info("Method 1 failed, trying Method 2 (trigger search input)...")

                    # Try to find search input
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

                                # Try to find search input
                                search_input.click(timeout=2000)
                                search_input.fill('furniture', timeout=2000)

                                # You may need to press Enter.
                                search_input.press('Enter', timeout=2000)

                                # wait until Algolia makes a request
                                time.sleep(3)

                                if api_key:
                                    logger.info(f"[OK] Method 2 (search input) succeeded!")
                                    return api_key

                        except Exception:
                            continue

                    # METHOD 3: JavaScript eval window object
                    logger.info("Method 2 failed, trying Method 3 (JavaScript eval)...")

                    try:
                        js_code = """
                        () => {
                            // Search in various possible locations
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
                            logger.info(f"[OK] Method 3 (JavaScript) succeeded: {api_key[:30]}...")
                            return api_key

                    except Exception as e:
                        logger.debug(f"JavaScript eval failed: {e}")

                    # Search in different METHOD 4: Try different search URLs
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
                                logger.info(f"[OK] Method 4 (alternative URL) succeeded!")
                                return api_key

                        except Exception:
                            continue

                    # Search in different METHOD 4: Try different sear All methods failed
                    logger.error(f"[X] All 4 methods failed to capture API key")
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
        Update the API key in emmamason_algolia_v5_1.py

        Args:
            new_key: New API key

        Returns:
            True if successful
        """
        try:
            file_path = Path(__file__).parent / 'emmamason_algolia_v5_1.py'

            if not file_path.exists():
                logger.error(f"File not found: {file_path}")
                return False

            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # Backup
            backup_path = file_path.with_suffix('.py.backup')
            with open(backup_path, 'w', encoding='utf-8') as f:
                f.write(content)

            logger.info(f"Created backup: {backup_path}")
                # Correct regex pattern
                # Searches for: ALGOLIA_API_KEY = “anything”
                # Important: (?!.*#) - there should be no # before the string (not commented out)

            pattern = r'^(\s*ALGOLIA_API_KEY\s*=\s*)"[^"]+"'
            replacement = r'\1"' + new_key + '"'

            # Replace only the first active (uncommented) line
            lines = content.split('\n')
            replaced = False

            for i, line in enumerate(lines):
                # Search for an active line (without # at the beginning)
                if 'ALGOLIA_API_KEY' in line and not line.strip().startswith('#'):
                    # Replace
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

            # Replace
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(new_content)

            logger.info(f"[OK] API key updated in {file_path}")

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
            List of products
        """
        try:
            # HTML config (longer delays for bypassing Cloudflare)
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
        Send Telegram notification

        Args:
            title:
            message: 
        """
        if not self.telegram_bot:
            logger.debug("Telegram bot not configured")
            return

        try:
            full_message = f"*{title}*\n\n{message}"

            # If there is a send_message method
            if hasattr(self.telegram_bot, 'send_message'):
                self.telegram_bot.send_message(full_message)
            # If it's just a function
            elif callable(self.telegram_bot):
                self.telegram_bot(full_message)

            logger.info(f"[OK] Telegram notification sent: {title}")

        except Exception as e:
            logger.error(f"Failed to send notification: {e}")

# Compatibility wrapper for existing code
class EmmaMasonBrandsScraper:
    """
    Compatibility wrapper - looks like an old scraper
    but uses a smart wrapper
    """

    def __init__(self, config: dict, error_logger=None, telegram_bot=None):
        """
        Initialization

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
        Scrape all brands (compatibility method)

        Returns:
            List of products
        """
        return self.smart_scraper.scrape_all_brands()

if __name__ == "__main__":
    pass