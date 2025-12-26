"""
Furniture Repricer - Main Application
З інтеграцією ConfigManager
"""

import sys
from pathlib import Path
from typing import List, Dict, Any
import time
from datetime import datetime

# Imports
from .modules.logger import setup_logging, get_logger
from .modules.error_logger import ErrorLogger
from .modules.google_sheets import GoogleSheetsClient, RepricerSheetsManager
from .modules.config_reader import GoogleSheetsConfigReader
from .modules.config_manager import ConfigManager  # ← НОВИЙ IMPORT!
from .modules.sku_matcher import SKUMatcher
from .scrapers.emmamason_brands import EmmaM asonBrandsScraper
from .scrapers.coleman import ColemanScraper
from .scrapers.onestopbedrooms import OnestopbedroomsScraper
from .scrapers.afastores import AfastoresScraper

logger = get_logger("repricer")


class FurnitureRepricer:
    """Main репрайсер з Config management"""
    
    def __init__(self, config_path: str):
        """
        Ініціалізація
        
        Args:
            config_path: Шлях до config.yaml
        """
        self.config_path = Path(config_path)
        self.logger = logger
        
        # Завантажити базову конфігурацію (YAML)
        self._load_base_config()
        
        # Ініціалізувати компоненти
        self._init_components()
        
        # ✅ НОВИЙ КОД: ConfigManager з merge logic
        self.config_manager = ConfigManager(
            yaml_path=str(self.config_path),
            sheets_reader=self.config_reader
        )
        
        # ✅ ДОДАТИ: ErrorLogger
        save_errors = self.runtime_config.get('save_scraping_errors', True)
        
        self.error_logger = ErrorLogger(
            sheets_client=self.sheets_client,
            sheet_id=self.base_config['main_sheet']['id'],
            enabled=save_errors
        )
        
        self.logger.info(f"Error logging: {'✓ enabled' if save_errors else '✗ disabled'}")

        # ✅ НОВИЙ КОД: Отримати merged config
        self.runtime_config = self.config_manager.get_config()
        self.price_rules = self.config_manager.get_price_rules()
        
        # ✅ НОВИЙ КОД: Валідація
        errors = self.config_manager.validate()
        if errors:
            self.logger.error("Configuration validation errors:")
            for error in errors:
                self.logger.error(f"  - {error}")
            raise ValueError("Invalid configuration")
        
        # ✅ НОВИЙ КОД: Вивести summary
        self.config_manager.print_summary()
        
        # ✅ НОВИЙ КОД: Перевірити чи run_enabled
        if not self.runtime_config.get('run_enabled', True):
            self.logger.warning("run_enabled = FALSE, repricer will not run!")
            self.logger.warning("Change 'run_enabled' to TRUE in Config sheet or config.yaml")
            sys.exit(0)
    
    def _load_base_config(self):
        """Завантажити базову YAML конфігурацію"""
        import yaml
        
        with open(self.config_path, 'r') as f:
            self.base_config = yaml.safe_load(f)
        
        # Setup logging
        log_config = self.base_config.get('logging', {})
        setup_logging(
            log_dir=log_config.get('directory', 'logs'),
            log_format=log_config.get('format'),
            date_format=log_config.get('date_format')
        )
    
    def _init_components(self):
        """Ініціалізація компонентів"""
        self.logger.info("Initializing components...")
        
        # Google Sheets
        creds_file = self.base_config['google_sheets']['credentials_file']
        self.sheets_client = GoogleSheetsClient(creds_file)
        self.sheets_manager = RepricerSheetsManager(
            self.sheets_client,
            self.base_config
        )
        
        # Config reader для Google Sheets
        self.config_reader = GoogleSheetsConfigReader(
            self.sheets_client,
            self.base_config['main_sheet']['id']
        )
        
        # SKU Matcher
        self.sku_matcher = SKUMatcher()
        
        self.logger.info("✓ Components initialized")
    
    def run(self):
        """
        Головний метод запуску
        """
        start_time = time.time()
        
        try:
            self.logger.info("="*60)
            self.logger.info("STARTING FURNITURE REPRICER")
            self.logger.info("="*60)
            
            # ✅ НОВИЙ КОД: Перевірки з runtime_config
            if self.runtime_config.get('dry_run'):
                self.logger.warning("🔵 DRY RUN MODE - No changes will be made!")
            
            if self.runtime_config.get('test_mode'):
                self.logger.warning("🧪 TEST MODE - Scraping but not updating sheets!")
            
            # 1. Завантажити дані з Google Sheets
            client_products = self._load_client_data()
            
            # ✅ НОВИЙ КОД: Test sample
            if self.runtime_config.get('test_mode'):
                sample_size = self.runtime_config.get('test_sample_size', 100)
                client_products = client_products[:sample_size]
                self.logger.info(f"🧪 Test mode: limited to {sample_size} products")
            
            # 2. Scrape Emma Mason (якщо увімкнено)
            if self.config_manager.is_enabled('scraper_emmamason'):
                self._scrape_and_update_emma_mason()
            else:
                self.logger.info("Emma Mason scraper DISABLED in config")
            
            # 3. Scrape competitors
            competitor_data = self._scrape_competitors()
            
            # 4. Match products з конкурентами
            matched_products = self._match_products(client_products, competitor_data)
            
            # 5. Розрахувати ціни
            products_with_prices = self._calculate_prices(matched_products)
            
            # 6. Оновити Google Sheets
            if not self.runtime_config.get('dry_run'):
                if not self.runtime_config.get('test_mode'):
                    updated = self._update_sheets(products_with_prices)
                    self.logger.info(f"✓ Updated {updated} products")
                else:
                    self.logger.info("🧪 Test mode: skipping sheet updates")
            else:
                self.logger.info("🔵 Dry run: skipping sheet updates")
            
            # 7. Статистика
            duration = time.time() - start_time
            self._print_statistics(duration)
            
            self.logger.info("="*60)
            self.logger.info("✓ REPRICER COMPLETED SUCCESSFULLY")
            self.logger.info("="*60)
            
        except Exception as e:
            self.logger.error(f"Repricer failed: {e}", exc_info=True)
            raise
    
    def _scrape_competitors(self) -> Dict[str, List[Dict]]:
        """
        Scrape всіх конкурентів
        
        Returns:
            Dictionary з даними конкурентів
        """
        competitor_data = {
            'coleman': [],
            'onestopbedrooms': [],
            'afastores': []
        }
        
        # Coleman
        if self.config_manager.is_enabled('scraper_coleman'):
            scraper_config = self.config_manager.get_scraper_config('coleman')
            
            coleman_scraper = ColemanScraper(
                max_products=scraper_config['max_products'],
                timeout_minutes=scraper_config['timeout_minutes']
            )
            
            competitor_data['coleman'] = coleman_scraper.scrape()
            self.logger.info(f"Coleman: {len(competitor_data['coleman'])} products")
        else:
            self.logger.info("Coleman scraper DISABLED in config")
        
        # 1StopBedrooms
        if self.config_manager.is_enabled('scraper_onestopbedrooms'):
            scraper_config = self.config_manager.get_scraper_config('onestopbedrooms')
            
            onestop_scraper = OnestopbedroomsScraper(
                max_products=scraper_config['max_products'],
                timeout_minutes=scraper_config['timeout_minutes']
            )
            
            competitor_data['onestopbedrooms'] = onestop_scraper.scrape()
            self.logger.info(f"1StopBedrooms: {len(competitor_data['onestopbedrooms'])} products")
        else:
            self.logger.info("1StopBedrooms scraper DISABLED in config")
        
        # AFA Stores
        if self.config_manager.is_enabled('scraper_afastores'):
            scraper_config = self.config_manager.get_scraper_config('afastores')
            
            afa_scraper = AfastoresScraper(
                max_products=scraper_config['max_products'],
                timeout_minutes=scraper_config['timeout_minutes']
            )
            
            competitor_data['afastores'] = afa_scraper.scrape()
            self.logger.info(f"AFA Stores: {len(competitor_data['afastores'])} products")
        else:
            self.logger.info("AFA Stores scraper DISABLED in config")
        
        return competitor_data
    
    def _calculate_prices(self, products: List[Dict]) -> List[Dict]:
        """
        Розрахувати ціни для products
        
        Args:
            products: Список products з competitor data
        
        Returns:
            Products з розрахованими цінами
        """
        # ✅ НОВИЙ КОД: Використати price_rules з config
        floor_rate = self.price_rules.get('floor_rate', 1.5)
        below_competitor = self.price_rules.get('below_competitor', 1.0)
        max_rate = self.price_rules.get('max_rate', 2.0)
        
        # ✅ НОВИЙ КОД: Validation параметри
        validate = self.runtime_config.get('validate_prices_range', True)
        min_valid = self.runtime_config.get('min_valid_price', 10.0)
        max_valid = self.runtime_config.get('max_valid_price', 50000.0)
        reject_zero = self.runtime_config.get('reject_zero_prices', True)
        
        # ✅ НОВИЙ КОД: Price update параметри
        update_only_with_comp = self.runtime_config.get('update_only_with_competitors', False)
        min_change_pct = self.runtime_config.get('min_price_change_percent', 0.5)
        max_change_pct = self.runtime_config.get('max_price_change_percent', 20.0)
        
        updated_products = []
        skipped_validation = 0
        skipped_min_change = 0
        skipped_max_change = 0
        skipped_no_competitors = 0
        
        for product in products:
            our_cost = product.get('Our Cost', 0)
            current_price = product.get('Our Sales Price', 0)
            
            # Знайти найнижчу ціну конкурента
            competitor_prices = []
            for site_num in [1, 2, 3]:
                price = product.get(f'site{site_num}_price', 0)
                if price and price > 0:
                    competitor_prices.append(price)
            
            # ✅ НОВИЙ КОД: update_only_with_competitors
            if update_only_with_competitors and not competitor_prices:
                skipped_no_competitors += 1
                continue
            
            # Розрахувати floor і max
            floor_price = our_cost * floor_rate
            max_price = our_cost * max_rate
            
            # Розрахувати suggested price
            if competitor_prices:
                lowest_competitor = min(competitor_prices)
                suggested_price = lowest_competitor - below_competitor
            else:
                # Немає конкурентів - залишити поточну ціну
                suggested_price = current_price
            
            # Обмежити діапазоном floor-max
            suggested_price = max(floor_price, min(suggested_price, max_price))
            
            # ✅ НОВИЙ КОД: Validation
            if validate:
                if suggested_price < min_valid or suggested_price > max_valid:
                    self.logger.warning(
                        f"SKU {product.get('sku')}: price ${suggested_price:.2f} outside valid range "
                        f"${min_valid}-${max_valid}, skipping"
                    )
                    skipped_validation += 1
                    continue
                
                if reject_zero and suggested_price == 0:
                    self.logger.warning(f"SKU {product.get('sku')}: rejecting zero price")
                    skipped_validation += 1
                    continue
            
            # ✅ НОВИЙ КОД: Min/Max change validation
            if current_price > 0:
                change_pct = abs(suggested_price - current_price) / current_price * 100
                
                if change_pct < min_change_pct:
                    skipped_min_change += 1
                    continue
                
                if change_pct > max_change_pct:
                    self.logger.warning(
                        f"SKU {product.get('sku')}: price change {change_pct:.1f}% exceeds max {max_change_pct}%, "
                        f"limiting"
                    )
                    # Обмежити зміну
                    if suggested_price > current_price:
                        suggested_price = current_price * (1 + max_change_pct/100)
                    else:
                        suggested_price = current_price * (1 - max_change_pct/100)
            
            # Додати _prices_to_update
            product['_prices_to_update'] = {
                'suggest_price': suggested_price,
            }
            
            updated_products.append(product)
        
        # Статистика
        self.logger.info(f"Price calculation:")
        self.logger.info(f"  Products calculated: {len(updated_products)}")
        if skipped_validation > 0:
            self.logger.info(f"  Skipped (validation): {skipped_validation}")
        if skipped_min_change > 0:
            self.logger.info(f"  Skipped (min change): {skipped_min_change}")
        if skipped_max_change > 0:
            self.logger.info(f"  Limited (max change): {skipped_max_change}")
        if skipped_no_competitors > 0:
            self.logger.info(f"  Skipped (no competitors): {skipped_no_competitors}")
        
        return updated_products
    
    def _update_sheets(self, products: List[Dict]) -> int:
        """
        Оновити Google Sheets
        
        Args:
            products: Products з розрахованими цінами
        
        Returns:
            Кількість оновлених products
        """
        # ✅ НОВИЙ КОД: Перевірити enable_price_updates
        if not self.runtime_config.get('enable_price_updates', True):
            self.logger.info("Price updates DISABLED in config")
            return 0
        
        # 1. Оновити основні ціни
        updated = self.sheets_manager.batch_update_all(products)
        
        # ✅ НОВИЙ КОД: Оновити Competitors sheet якщо enabled
        if self.runtime_config.get('enable_competitors_sheet', True):
            competitors_updated = self.sheets_manager.batch_update_competitors_sheet(products)
            self.logger.info(f"Competitors sheet: {competitors_updated} products")
        
        return updated


def main():
    """Entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Furniture Repricer')
    parser.add_argument('--config', default='config.yaml', help='Config file path')
    parser.add_argument('--test', action='store_true', help='Run in test mode')
    
    args = parser.parse_args()
    
    # Якщо --test флаг, можна override test_mode
    # Але краще використовувати Config sheet!
    
    repricer = FurnitureRepricer(args.config)
    repricer.run()


if __name__ == '__main__':
    main()