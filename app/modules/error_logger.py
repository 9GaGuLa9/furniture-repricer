"""
ErrorLogger - Збереження помилок scraping в Google Sheets

Створює аркуш "Scraping_Errors" та записує всі помилки з timestamp,
scraper name, error message, traceback, та URL якщо є.
"""

import traceback
from datetime import datetime
from typing import Optional, Dict, Any
from .logger import get_logger

logger = get_logger("error_logger")


class ErrorLogger:
    """
    Логування помилок scraping в Google Sheets
    
    Створює аркуш "Scraping_Errors" з колонками:
    - Timestamp
    - Scraper
    - Error Type
    - Error Message
    - URL (якщо є)
    - Traceback
    """
    
    def __init__(self, sheets_client, sheet_id: str, enabled: bool = True):
        """
        Args:
            sheets_client: GoogleSheetsClient instance
            sheet_id: ID Google Sheets таблиці
            enabled: Чи увімкнено збереження помилок
        """
        self.client = sheets_client
        self.sheet_id = sheet_id
        self.enabled = enabled
        self.logger = logger
        self.error_sheet_name = "Scraping_Errors"
        
        # Створити аркуш якщо не існує
        if self.enabled:
            self._ensure_error_sheet_exists()
    
    def _ensure_error_sheet_exists(self):
        """Створити аркуш Scraping_Errors якщо не існує"""
        try:
            if not self.client.worksheet_exists(self.sheet_id, self.error_sheet_name):
                self.logger.info(f"Creating {self.error_sheet_name} sheet...")
                
                worksheet = self.client.create_worksheet(
                    self.sheet_id,
                    self.error_sheet_name,
                    rows=1000,
                    cols=6
                )
                
                # Headers
                headers = [
                    'Timestamp',
                    'Scraper',
                    'Error Type',
                    'Error Message',
                    'URL',
                    'Traceback'
                ]
                
                worksheet.update('A1', [headers])
                self.logger.info(f"✓ Created {self.error_sheet_name} sheet")
        
        except Exception as e:
            self.logger.error(f"Failed to create {self.error_sheet_name} sheet: {e}")
            self.enabled = False
    
    def log_error(
        self,
        scraper_name: str,
        error: Exception,
        url: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ):
        """
        Записати помилку в Google Sheets
        
        Args:
            scraper_name: Назва scraper (напр. "EmmaMansonScraper")
            error: Exception об'єкт
            url: URL де сталась помилка (опціонально)
            context: Додатковий контекст (опціонально)
        """
        if not self.enabled:
            return
        
        try:
            # Підготувати дані
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            error_type = type(error).__name__
            error_message = str(error)
            
            # Traceback
            tb = ''.join(traceback.format_tb(error.__traceback__))
            
            # Обмежити довжину для Google Sheets
            error_message = error_message[:500]
            tb = tb[:1000]
            
            # Додати context якщо є
            if context:
                context_str = str(context)[:200]
                error_message = f"{error_message} | Context: {context_str}"
            
            # Підготувати рядок
            row = [
                timestamp,
                scraper_name,
                error_type,
                error_message,
                url or '',
                tb
            ]
            
            # Записати в Google Sheets
            worksheet = self.client.open_sheet(self.sheet_id, self.error_sheet_name)
            worksheet.append_row(row, value_input_option='USER_ENTERED')
            
            self.logger.warning(
                f"Error logged to {self.error_sheet_name}: {scraper_name} - {error_type}"
            )
        
        except Exception as e:
            self.logger.error(f"Failed to log error to sheet: {e}")
            # Не рейзити помилку - це fallback logging


class ScraperErrorMixin:
    """
    Mixin для scrapers щоб додати error logging
    
    Використання:
        class MyS craper(ScraperErrorMixin):
            def __init__(self, error_logger):
                self.error_logger = error_logger
                self.scraper_name = "MyScraper"
            
            def scrape(self):
                try:
                    # ... scraping ...
                except Exception as e:
                    self.log_scraping_error(e, url="http://...")
    """
    
    def log_scraping_error(
        self,
        error: Exception,
        url: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ):
        """
        Логувати помилку scraping
        
        Args:
            error: Exception
            url: URL де сталась помилка
            context: Додатковий контекст
        """
        if hasattr(self, 'error_logger') and self.error_logger:
            scraper_name = getattr(self, 'scraper_name', self.__class__.__name__)
            self.error_logger.log_error(scraper_name, error, url, context)
        else:
            # Fallback на звичайний logger
            logger.error(f"Scraping error in {self.__class__.__name__}: {error}")


# ============================================================
# INTEGRATION EXAMPLES
# ============================================================

"""
# ПРИКЛАД 1: В main.py

from .modules.error_logger import ErrorLogger

class FurnitureRepricer:
    def __init__(self, config_path):
        # ... існуючий код ...
        
        # ✅ ДОДАТИ: Error Logger
        save_errors = self.runtime_config.get('save_scraping_errors', True)
        
        self.error_logger = ErrorLogger(
            sheets_client=self.sheets_client,
            sheet_id=self.base_config['main_sheet']['id'],
            enabled=save_errors
        )
        
        self.logger.info(f"Error logging: {'enabled' if save_errors else 'disabled'}")


# ПРИКЛАД 2: Передати error_logger в scrapers

def _scrape_competitors(self):
    # Coleman
    if self.config_manager.is_enabled('scraper_coleman'):
        scraper_config = self.config_manager.get_scraper_config('coleman')
        
        coleman_scraper = ColemanScraper(
            max_products=scraper_config['max_products'],
            timeout_minutes=scraper_config['timeout_minutes'],
            error_logger=self.error_logger  # ← ПЕРЕДАТИ!
        )
        
        competitor_data['coleman'] = coleman_scraper.scrape()


# ПРИКЛАД 3: В scraper (Coleman, Emma Mason, etc.)

from ..modules.error_logger import ScraperErrorMixin

class ColemanScraper(ScraperErrorMixin):  # ← Додати mixin
    def __init__(
        self,
        max_products: int = 2000,
        timeout_minutes: int = 45,
        error_logger = None  # ← Додати параметр
    ):
        self.max_products = max_products
        self.timeout_minutes = timeout_minutes
        self.error_logger = error_logger  # ← Зберегти
        self.scraper_name = "ColemanScraper"  # ← Для error logging
        
        self.logger = get_logger("coleman_scraper")
    
    def scrape(self) -> List[Dict]:
        products = []
        
        try:
            # ... scraping logic ...
            
            for product_url in product_urls:
                try:
                    # Scrape product
                    product_data = self._scrape_product(product_url)
                    products.append(product_data)
                
                except Exception as e:
                    # ✅ Логувати помилку для конкретного URL
                    self.log_scraping_error(
                        error=e,
                        url=product_url,
                        context={'products_scraped': len(products)}
                    )
                    continue
        
        except Exception as e:
            # ✅ Логувати глобальну помилку scraper
            self.log_scraping_error(
                error=e,
                context={'stage': 'main_scraping_loop'}
            )
        
        finally:
            self.logger.info(f"Scraped {len(products)} products")
        
        return products


# ПРИКЛАД 4: Простий try/catch БЕЗ mixin

class SimpleS craper:
    def __init__(self, error_logger=None):
        self.error_logger = error_logger
    
    def scrape(self):
        try:
            # ... scraping ...
            pass
        except Exception as e:
            # ✅ Простий виклик якщо є error_logger
            if self.error_logger:
                self.error_logger.log_error(
                    scraper_name="SimpleScraper",
                    error=e,
                    url="http://example.com"
                )
            raise
"""
