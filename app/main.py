"""
Furniture Repricer - Main Script
Головний скрипт для автоматичного оновлення цін
"""

import sys
import argparse
from datetime import datetime
from pathlib import Path
from scrapers.emmamason import scrape_emmamason

# Додати app до Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import get_config
from app.modules import (
    setup_logging,
    get_logger,
    LogBlock,
    GoogleSheetsClient,
    RepricerSheetsManager,
    TelegramNotifier,
    TelegramNotifierManager,
    PricingEngine,
    BatchPricingProcessor,
    SKUMatcher
)

# TODO: Import scrapers after they are created
# from app.scrapers import (
#     EmmaMasonScraper,
#     OneStopBedroomsScraper,
#     ColemanScraper,
#     AFAScraper
# )


class FurnitureRepricer:
    """Головний клас репрайсера"""
    
    def __init__(self, test_mode: bool = False):
        """
        Ініціалізація репрайсера
        
        Args:
            test_mode: Тестовий режим (обмежена кількість товарів)
        """
        self.test_mode = test_mode
        self.config = get_config()
        
        # Налаштувати логування
        log_config = self.config.get('logging', {})
        self.logger = setup_logging(log_config)
        
        self.logger.info("="*60)
        self.logger.info("Furniture Repricer Started")
        self.logger.info(f"Mode: {'TEST' if test_mode else 'PRODUCTION'}")
        self.logger.info(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        self.logger.info("="*60)
        
        # Ініціалізувати компоненти
        self._init_components()
        
        # Статистика
        self.stats = {
            'start_time': datetime.now(),
            'total_products': 0,
            'updated': 0,
            'errors': 0,
            'competitors': {}
        }
    
    def _init_components(self):
        """Ініціалізувати всі компоненти"""
        try:
            # Google Sheets
            self.logger.info("Initializing Google Sheets client...")
            credentials_path = self.config.google_credentials_path
            self.sheets_client = GoogleSheetsClient(str(credentials_path))
            self.sheets_manager = RepricerSheetsManager(
                self.sheets_client,
                self.config.get('google_sheets', {})
            )
            
            # Перевірити підключення
            if not self.sheets_client.test_connection():
                raise Exception("Google Sheets connection test failed")
            
            # Telegram
            self.logger.info("Initializing Telegram notifier...")
            telegram_config = self.config.get('telegram', {})
            self.telegram = TelegramNotifier(
                self.config.telegram_token,
                self.config.telegram_chat_id,
                self.config.telegram_enabled
            )
            self.telegram_manager = TelegramNotifierManager(
                self.telegram,
                telegram_config
            )
            
            # Pricing Engine
            self.logger.info("Initializing pricing engine...")
            coefficients = self.config.get_pricing_coefficients()
            self.pricing_engine = PricingEngine(coefficients)
            self.pricing_processor = BatchPricingProcessor(self.pricing_engine)
            
            # SKU Matcher
            self.logger.info("Initializing SKU matcher...")
            sku_config = self.config.get('sku_matching', {})
            self.sku_matcher = SKUMatcher(sku_config)
            
            # TODO: Initialize scrapers
            self.logger.info("Initializing scrapers...")
            # self.emma_scraper = EmmaMasonScraper(...)
            # self.onestop_scraper = OneStopBedroomsScraper(...)
            # self.coleman_scraper = ColemanScraper(...)
            # self.afa_scraper = AFAScraper(...)
            
            self.logger.info("✓ All components initialized successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize components: {e}", exc_info=True)
            raise
    
    def run(self):
        """Запустити репрайсер"""
        try:
            # Сповістити про старт
            self.telegram_manager.notify_start(self.test_mode)
            
            with LogBlock("Full Repricer Run", self.logger):
                # 1. Завантажити дані з Google Sheets
                client_products = self._load_client_data()
                
                # 2. Парсити ціни з сайту клієнта
                self._scrape_client_prices(client_products)
                
                # 3. Парсити ціни конкурентів
                competitors_data = self._scrape_competitors()
                
                # 4. Співставити товари
                matched_data = self._match_products(client_products, competitors_data)
                
                # 5. Розрахувати рекомендовані ціни
                priced_products = self._calculate_prices(matched_data)
                
                # 6. Оновити Google Sheets
                self._update_sheets(priced_products)
                
                # 7. Зберегти історію
                self._save_history(priced_products)
                
                # 8. Підготувати статистику
                self._finalize_stats()
            
            # Сповістити про завершення
            self.telegram_manager.notify_complete(self.stats)
            
            self.logger.info("="*60)
            self.logger.info("Repricer Completed Successfully!")
            self.logger.info("="*60)
            
            return True
            
        except Exception as e:
            self.logger.error(f"Repricer failed: {e}", exc_info=True)
            self.telegram_manager.notify_error(str(e), "Main run")
            return False
    
    def _load_client_data(self):
        """Завантажити дані клієнта з Google Sheets"""
        with LogBlock("Loading client data from Google Sheets", self.logger):
            data = self.sheets_manager.get_main_data()
            
            # У тестовому режимі обмежити кількість
            if self.test_mode:
                limit = self.config.test_limit
                data = data[:limit]
                self.logger.info(f"TEST MODE: Limited to {limit} products")
            
            self.stats['total_products'] = len(data)
            self.logger.info(f"Loaded {len(data)} products")
            return data
    
    def _scrape_client_prices(self, products):
        """Парсити актуальні ціни з сайту клієнта"""
        with LogBlock("Scraping client prices (emmamason.com)", self.logger):
            # TODO: Implement Emma Mason scraper
            self.logger.info("TODO: Implement Emma Mason scraper")
            pass
    
    def _scrape_competitors(self):
        """Парсити ціни всіх конкурентів"""
        competitors_data = {}
        
        # Site 1: 1stopbedrooms
        if self.config.is_scraper_enabled('onestopbedrooms'):
            with LogBlock("Scraping 1stopbedrooms.com", self.logger):
                # TODO: Implement
                self.logger.info("TODO: Implement 1stopbedrooms scraper")
                competitors_data['site1'] = []
        
        # Site 2: Coleman
        if self.config.is_scraper_enabled('coleman'):
            with LogBlock("Scraping colemanfurniture.com", self.logger):
                # TODO: Implement
                self.logger.info("TODO: Implement coleman scraper")
                competitors_data['site2'] = []
        
        # Site 3: AFA
        if self.config.is_scraper_enabled('afa'):
            with LogBlock("Scraping afastores.com", self.logger):
                # TODO: Implement
                self.logger.info("TODO: Implement AFA scraper")
                competitors_data['site3'] = []
        
        return competitors_data
    
    def _match_products(self, client_products, competitors_data):
        """Співставити товари за SKU"""
        with LogBlock("Matching products by SKU", self.logger):
            # TODO: Implement SKU matching
            self.logger.info("TODO: Implement SKU matching")
            return client_products
    
    def _calculate_prices(self, products):
        """Розрахувати рекомендовані ціни"""
        with LogBlock("Calculating recommended prices", self.logger):
            priced = self.pricing_processor.process_products(products)
            stats = self.pricing_processor.get_statistics(priced)
            
            self.logger.info(f"Calculated prices for {stats['with_suggestions']} products")
            self.stats['updated'] = stats['with_suggestions']
            
            return priced
    
    def _update_sheets(self, products):
        """Оновити Google Sheets"""
        with LogBlock("Updating Google Sheets", self.logger):
            # TODO: Implement batch update
            self.logger.info("TODO: Implement sheets update")
            pass
    
    def _save_history(self, products):
        """Зберегти історію змін"""
        if not self.config.get('google_sheets.history_sheet.enabled', True):
            return
        
        with LogBlock("Saving price history", self.logger):
            # TODO: Implement history saving
            self.logger.info("TODO: Implement history saving")
            pass
    
    def _finalize_stats(self):
        """Фіналізувати статистику"""
        end_time = datetime.now()
        duration = (end_time - self.stats['start_time']).total_seconds() / 60
        self.stats['duration_minutes'] = duration
        
        self.logger.info(f"Duration: {duration:.1f} minutes")
        self.logger.info(f"Total products: {self.stats['total_products']}")
        self.logger.info(f"Updated: {self.stats['updated']}")
        self.logger.info(f"Errors: {self.stats['errors']}")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='Furniture Price Repricer')
    parser.add_argument('--test', '-t', action='store_true',
                       help='Run in test mode (limited products)')
    parser.add_argument('--dry-run', '-d', action='store_true',
                       help='Dry run (don\'t update sheets)')
    
    args = parser.parse_args()
    
    # Створити та запустити репрайсер
    repricer = FurnitureRepricer(test_mode=args.test)
    success = repricer.run()
    
    # Exit code
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
