"""
Furniture Repricer - Main Application
FIXED VERSION v5.1 - CORRECTED "Used In Pricing" logic

КРИТИЧНЕ ВИПРАВЛЕННЯ:
✅ "Used In Pricing" = True ТІЛЬКИ для товару з найнижчою ціною серед ВСІХ конкурентів
✅ Перевіряє calculation_method: якщо 'competitor_capped_at_floor' або 'competitor_capped_at_max' → Used = False
"""

import sys
from pathlib import Path
from typing import List, Dict, Any
import time
from datetime import datetime
import yaml

# Imports
from .modules.logger import setup_logging, get_logger
from .modules.google_sheets import GoogleSheetsClient, RepricerSheetsManager
from .modules.config_reader import GoogleSheetsConfigReader
from .modules.config_manager import ConfigManager
from .modules.error_logger import ErrorLogger
from .modules.sku_matcher import SKUMatcher
from .modules.competitors_tracker import CompetitorsMatchedTracker
from .modules.pricing import PricingEngine, BatchPricingProcessor

# Scrapers
from .scrapers.emmamason_smart_scraper import EmmaMasonBrandsScraper
from .scrapers.coleman import ColemanScraper
from .scrapers.onestopbedrooms import OneStopBedroomsScraper
from .scrapers.afa import AFAScraper

logger = get_logger("repricer")


class FurnitureRepricer:
    """Main репрайсер з Config management + Error logging"""
    
    def __init__(self, config_path: str):
        """
        Ініціалізація
        
        Args:
            config_path: Шлях до config.yaml
        """
        self.config_path = Path(config_path)
        self.logger = logger
        
        # ═══════════════════════════════════════════════════════════════
        # КРОК 1: Завантажити базову YAML конфігурацію
        # ═══════════════════════════════════════════════════════════════
        self._load_base_config()
        
        # ═══════════════════════════════════════════════════════════════
        # КРОК 2: Ініціалізувати компоненти (Google Sheets, etc.)
        # ═══════════════════════════════════════════════════════════════
        self._init_components()
        
        # ═══════════════════════════════════════════════════════════════
        # КРОК 3: ConfigManager (YAML + Google Sheets merge)
        # ═══════════════════════════════════════════════════════════════
        self.config_manager = ConfigManager(
            yaml_path=str(self.config_path),
            sheets_reader=self.config_reader
        )
        
        # ✅ КРИТИЧНО: СПОЧАТКУ runtime_config!
        self.runtime_config = self.config_manager.get_config()
        self.price_rules = self.config_manager.get_price_rules()
        
        # ═══════════════════════════════════════════════════════════════
        # КРОК 4: ErrorLogger (ТІЛЬКИ ПІСЛЯ runtime_config!)
        # ═══════════════════════════════════════════════════════════════
        save_errors = self.runtime_config.get('save_scraping_errors', True)
        
        self.error_logger = ErrorLogger(
            sheets_client=self.sheets_client,
            sheet_id=self.base_config['main_sheet']['id'],
            enabled=save_errors
        )
        
        self.logger.info(f"Error logging: {'✓ enabled' if save_errors else '✗ disabled'}")
        
        # ═══════════════════════════════════════════════════════════════
        # КРОК 5: Валідація конфігурації
        # ═══════════════════════════════════════════════════════════════
        errors = self.config_manager.validate()
        if errors:
            self.logger.error("Configuration validation errors:")
            for error in errors:
                self.logger.error(f"  - {error}")
            raise ValueError("Invalid configuration")
        
        # Вивести summary
        self.config_manager.print_summary()
        
        # ═══════════════════════════════════════════════════════════════
        # КРОК 6: Перевірити чи run_enabled
        # ═══════════════════════════════════════════════════════════════
        if not self.runtime_config.get('run_enabled', True):
            self.logger.warning("run_enabled = FALSE, repricer will not run!")
            self.logger.warning("Change 'run_enabled' to TRUE in Config sheet or config.yaml")
            sys.exit(0)
        
        # ═══════════════════════════════════════════════════════════════
        # КРОК 7: Pricing Engine
        # ═══════════════════════════════════════════════════════════════
        self.pricing_engine = PricingEngine(self.price_rules)
        self.pricing_processor = BatchPricingProcessor(self.pricing_engine)
        
        self.competitor_data = {}  # Кеш для competitors raw data


    def _load_base_config(self):
        """Завантажити базову YAML конфігурацію"""
        with open(self.config_path, 'r', encoding='utf-8') as f:
            self.base_config = yaml.safe_load(f)
        
        # Setup logging
        log_config = self.base_config.get('logging', {})
        setup_logging(
            log_dir=log_config.get('directory', 'logs'),
            log_format=log_config.get('format'),
            date_format=log_config.get('date_format'),
            level=log_config.get('level', 'INFO')
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
        sku_config = self.base_config.get('sku_matching', {})
        self.sku_matcher = SKUMatcher(sku_config)
        
        # ═══════════════════════════════════════════════════════════
        # Competitors Matched Tracker
        # ═══════════════════════════════════════════════════════════
        self.matched_tracker = CompetitorsMatchedTracker()
        
        self.logger.info("✓ Components initialized")
    
    def run(self):
        """Головний метод запуску"""
        start_time = time.time()
        
        try:
            self.logger.info("="*60)
            self.logger.info("STARTING FURNITURE REPRICER")
            self.logger.info("="*60)
            
            # Перевірки
            if self.runtime_config.get('dry_run'):
                self.logger.warning("🔵 DRY RUN MODE - No changes will be made!")
            
            if self.runtime_config.get('test_mode'):
                self.logger.warning("🧪 TEST MODE - Limited sample!")
            
            # 1. Завантажити дані з Google Sheets
            client_products = self._load_client_data()
            
            # Test sample
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
            self.competitor_data = competitor_data
            
            # 4. Match products з конкурентами
            matched_products = self._match_products(client_products, competitor_data)
            
            # 5. Розрахувати ціни
            priced_products = self._calculate_prices(matched_products)
            
            # ═══════════════════════════════════════════════════════════
            # ✅ NEW STEP 5.5: Оновити "Used In Pricing" на основі фактично використаної ціни
            # ═══════════════════════════════════════════════════════════
            self._update_used_in_pricing(priced_products)
            
            # 6. Оновити Google Sheets
            if not self.runtime_config.get('dry_run'):
                updated = self._update_sheets(priced_products)
            else:
                self.logger.info("DRY RUN: Skipping Google Sheets update")
                updated = 0
            
            # 7. Статистика
            duration = time.time() - start_time
            self._print_statistics(duration, len(client_products), updated)
            
            self.logger.info("\n" + "="*60)
            self.logger.info("✅ REPRICER COMPLETED SUCCESSFULLY")
            self.logger.info("="*60)
            
        except Exception as e:
            self.logger.error(f"❌ Repricer failed: {e}", exc_info=True)
            raise
    
    def _load_client_data(self) -> List[Dict]:
        """Завантажити дані клієнта з Google Sheets"""
        self.logger.info("\n" + "="*60)
        self.logger.info("LOADING CLIENT DATA FROM GOOGLE SHEETS")
        self.logger.info("="*60)
        
        # Завантажити всі products
        client_products = self.sheets_manager.get_main_data()
        
        # ✅ NEW: Зберегти URLs наших товарів для matched tracking
        for product in client_products:
            sku = product.get('sku')
            url = product.get('our_url')  # ✅ FIXED: 'our_url' а не 'url'
            if sku and url:
                self.matched_tracker.add_our_product(sku, url)
        
        self.logger.info(f"Loaded {len(client_products)} products from Google Sheets")
        
        return client_products
    
    def _scrape_and_update_emma_mason(self):
        """Scrape Emma Mason та оновити Google Sheets"""
        self.logger.info("\n" + "="*60)
        self.logger.info("SCRAPING EMMA MASON")
        self.logger.info("="*60)
        
        try:
            scraper_config = self.config_manager.get_scraper_config('emmamason')
            
            # Створити scraper config
            config = {
                'delay_min': self.base_config.get('scrapers', {}).get('emmamason', {}).get('delay_min', 2.0),
                'delay_max': self.base_config.get('scrapers', {}).get('emmamason', {}).get('delay_max', 5.0),
                'retry_attempts': scraper_config.get('max_retries', 3),
                'timeout': self.base_config.get('scrapers', {}).get('emmamason', {}).get('timeout', 45),
            }
            
            emma_scraper = EmmaMasonBrandsScraper(
                config,
                error_logger=self.error_logger,
                telegram_bot=getattr(self, 'telegram_bot', None)  # Safe: буде None якщо немає
            )
            emma_products = emma_scraper.scrape_all_brands()
            
            self.logger.info(f"Emma Mason scraped: {len(emma_products)} products")
            
            # Batch update
            if emma_products and not self.runtime_config.get('dry_run'):
                # ✅ DEBUG: Зберегти RAW дані в окремий аркуш
                raw_saved = self.sheets_manager.batch_update_emma_mason_raw(emma_products)
                self.logger.info(f"✓ Emma Mason RAW saved: {raw_saved} products")
                
                # Оновити основну таблицю
                updated = self.sheets_manager.batch_update_emma_mason(emma_products)
                self.logger.info(f"✓ Emma Mason updated: {updated} products")
            
        except Exception as e:
            self.logger.error(f"Emma Mason scraping failed: {e}", exc_info=True)
            
            if self.error_logger:
                self.error_logger.log_error("EmmaMasonScraper", e)
    
    def _scrape_competitors(self) -> Dict[str, List[Dict]]:
        """Scrape дані з конкурентів"""
        self.logger.info("\n" + "="*60)
        self.logger.info("SCRAPING COMPETITORS")
        self.logger.info("="*60)
        
        competitor_data = {}
        
        # Coleman
        if self.config_manager.is_enabled('scraper_coleman'):
            self.logger.info("\n--- Coleman Furniture ---")
            scraper_config = self.config_manager.get_scraper_config('coleman')
            
            scraper = ColemanScraper(
                config=scraper_config,
                error_logger=self.error_logger
            )
            
            try:
                products = scraper.scrape_all_products()
                competitor_data['coleman'] = products
                self.logger.info(f"✓ Coleman: {len(products)} products")
            except Exception as e:
                self.logger.error(f"Coleman scraper failed: {e}")
                competitor_data['coleman'] = []
        
        # 1StopBedrooms
        if self.config_manager.is_enabled('scraper_onestopbedrooms'):
            self.logger.info("\n--- 1StopBedrooms ---")
            scraper_config = self.config_manager.get_scraper_config('onestopbedrooms')
            
            scraper = OneStopBedroomsScraper(
                config=scraper_config,
                error_logger=self.error_logger
            )
            
            try:
                products = scraper.scrape_all_products()
                competitor_data['onestopbedrooms'] = products
                self.logger.info(f"✓ 1StopBedrooms: {len(products)} products")
            except Exception as e:
                self.logger.error(f"1StopBedrooms scraper failed: {e}")
                competitor_data['onestopbedrooms'] = []
        
        # AFA Stores
        if self.config_manager.is_enabled('scraper_afastores'):
            self.logger.info("\n--- AFA Stores ---")
            scraper_config = self.config_manager.get_scraper_config('afastores')
            
            scraper = AFAScraper(
                config=scraper_config,
                error_logger=self.error_logger
            )
            
            try:
                products = scraper.scrape_all_products()
                competitor_data['afastores'] = products
                self.logger.info(f"✓ AFA Stores: {len(products)} products")
            except Exception as e:
                self.logger.error(f"AFA Stores scraper failed: {e}")
                competitor_data['afastores'] = []
        
        total = sum(len(v) for v in competitor_data.values())
        self.logger.info(f"\nTotal competitor products: {total}")
        
        return competitor_data
    
    def _match_and_track_competitor(
        self, 
        product: Dict,
        our_sku: str,
        source: str,
        competitor_products: List[Dict],
        site_prefix: str
    ) -> bool:
        """
        Зіставити товар з competitor і відстежити результат
        
        ✅ UPDATED: Всі matches позначаємо used=False (буде оновлено пізніше)
        
        Args:
            product: Наш товар (буде оновлено з competitor даними)
            our_sku: Наш SKU
            source: 'coleman', 'onestopbedrooms', 'afastores'
            competitor_products: Список товарів competitor
            site_prefix: 'site1', 'site2', 'site3'
        
        Returns:
            True якщо знайдено match
        """
        
        # ═══════════════════════════════════════════════════════════
        # Знайти ВСІ matches (для tracking)
        # ═══════════════════════════════════════════════════════════
        all_matches = self.sku_matcher.find_all_matching_products(
            our_sku,
            competitor_products,
            sku_field='sku',
            source=source
        )
        
        # Track ALL matches з used=False (буде оновлено в _update_used_in_pricing)
        for match in all_matches:
            comp_sku = match.get('sku')
            self.matched_tracker.track_match(
                source=source,
                competitor_sku=comp_sku,
                our_sku=our_sku,
                used=False  # ✅ ЗМІНЕНО: Спочатку всі False
            )
        
        # ═══════════════════════════════════════════════════════════
        # Знайти BEST match (найнижча ціна для цього конкурента)
        # ═══════════════════════════════════════════════════════════
        best_match = self.sku_matcher.find_best_match(
            our_sku,
            competitor_products,
            sku_field='sku',
            price_field='price',
            source=source
        )
        
        if best_match:
            # Зберегти в product (але НЕ позначати used=True!)
            product[f'{site_prefix}_sku'] = best_match.get('sku')
            product[f'{site_prefix}_price'] = best_match.get('price')
            product[f'{site_prefix}_url'] = best_match.get('url')
            
            return True
        
        return False
    
    def _match_products(self, client_products: List[Dict], 
                        competitor_data: Dict[str, List[Dict]]) -> List[Dict]:
        """Match products з конкурентами за SKU"""
        self.logger.info("\n" + "="*60)
        self.logger.info("MATCHING PRODUCTS WITH COMPETITORS")
        self.logger.info("="*60)
        
        matched_products = []
        match_stats = {
            'coleman': 0,
            'onestopbedrooms': 0,
            'afastores': 0
        }
        
        for product in client_products:
            our_sku = product.get('sku')
            if not our_sku:
                continue
            
            # ═══════════════════════════════════════════════════════
            # Coleman
            # ═══════════════════════════════════════════════════════
            if self._match_and_track_competitor(
                product, 
                our_sku, 
                'coleman',
                competitor_data.get('coleman', []),
                'site1'
            ):
                match_stats['coleman'] += 1
            
            # ═══════════════════════════════════════════════════════
            # 1StopBedrooms
            # ═══════════════════════════════════════════════════════
            if self._match_and_track_competitor(
                product, 
                our_sku, 
                'onestopbedrooms',
                competitor_data.get('onestopbedrooms', []),
                'site2'
            ):
                match_stats['onestopbedrooms'] += 1
            
            # ═══════════════════════════════════════════════════════
            # AFA Stores
            # ═══════════════════════════════════════════════════════
            if self._match_and_track_competitor(
                product, 
                our_sku, 
                'afastores',
                competitor_data.get('afastores', []),
                'site3'
            ):
                match_stats['afastores'] += 1
            
            matched_products.append(product)
        
        # Мінімальна статистика (тільки цифри)
        self.logger.info(
            f"Coleman: {match_stats['coleman']} | "
            f"1StopBedrooms: {match_stats['onestopbedrooms']} | "
            f"AFA: {match_stats['afastores']}"
        )
        
        with_competitors = sum(
            1 for p in matched_products 
            if any([p.get('site1_price'), p.get('site2_price'), p.get('site3_price')])
        )
        
        self.logger.info(f"Products with competitors: {with_competitors}/{len(matched_products)}")
        
        return matched_products

    def _calculate_prices(self, products: List[Dict]) -> List[Dict]:
        """Розрахувати ціни для products"""
        self.logger.info("\n" + "="*60)
        self.logger.info("CALCULATING PRICES")
        self.logger.info("="*60)
        
        # Використати pricing processor
        products_with_prices = self.pricing_processor.process_products(products)
        
        # Застосувати validation з runtime_config
        validate = self.runtime_config.get('validate_prices_range', True)
        min_valid = self.runtime_config.get('min_valid_price', 10.0)
        max_valid = self.runtime_config.get('max_valid_price', 50000.0)
        reject_zero = self.runtime_config.get('reject_zero_prices', True)
        
        update_only_with_comp = self.runtime_config.get('update_only_with_competitors', False)
        min_change_pct = self.runtime_config.get('min_price_change_percent', 0.5)
        max_change_pct = self.runtime_config.get('max_price_change_percent', 20.0)
        
        filtered_products = []
        skipped_validation = 0
        skipped_min_change = 0
        skipped_no_competitors = 0
        
        for product in products_with_prices:
            suggested_price = product.get('suggested_price')
            current_price = product.get('Our Sales Price', 0)
            
            if not suggested_price:
                continue
            
            # Check update_only_with_competitors
            if update_only_with_comp:
                has_competitors = any([
                    product.get('site1_price'),
                    product.get('site2_price'),
                    product.get('site3_price')
                ])
                
                if not has_competitors:
                    skipped_no_competitors += 1
                    continue
            
            # Validation
            if validate:
                if suggested_price < min_valid or suggested_price > max_valid:
                    skipped_validation += 1
                    continue
                
                if reject_zero and suggested_price == 0:
                    skipped_validation += 1
                    continue
            
            # Min/Max change validation
            if current_price > 0:
                change_pct = abs(suggested_price - current_price) / current_price * 100
                
                if change_pct < min_change_pct:
                    skipped_min_change += 1
                    continue
                
                if change_pct > max_change_pct:
                    # Обмежити зміну
                    if suggested_price > current_price:
                        suggested_price = current_price * (1 + max_change_pct/100)
                    else:
                        suggested_price = current_price * (1 - max_change_pct/100)
                    
                    product['suggested_price'] = suggested_price
            
            # Додати _prices_to_update
            prices_dict = {
                'suggest_price': suggested_price,
            }
            
            # ✅ КРИТИЧНО: Додати competitor дані якщо є!
            if product.get('site1_price'):
                prices_dict['site1_price'] = product.get('site1_price')
                prices_dict['site1_url'] = product.get('site1_url', '')
                prices_dict['site1_sku'] = product.get('site1_sku', '')
            
            if product.get('site2_price'):
                prices_dict['site2_price'] = product.get('site2_price')
                prices_dict['site2_url'] = product.get('site2_url', '')
                prices_dict['site2_sku'] = product.get('site2_sku', '')
            
            if product.get('site3_price'):
                prices_dict['site3_price'] = product.get('site3_price')
                prices_dict['site3_url'] = product.get('site3_url', '')
                prices_dict['site3_sku'] = product.get('site3_sku', '')
            
            product['_prices_to_update'] = prices_dict
            
            filtered_products.append(product)
        
        # Статистика
        self.logger.info(f"Price calculation:")
        self.logger.info(f"  Products calculated: {len(filtered_products)}")
        if skipped_validation > 0:
            self.logger.info(f"  Skipped (validation): {skipped_validation}")
        if skipped_min_change > 0:
            self.logger.info(f"  Skipped (min change): {skipped_min_change}")
        if skipped_no_competitors > 0:
            self.logger.info(f"  Skipped (no competitors): {skipped_no_competitors}")
        
        return filtered_products
    
    def _update_used_in_pricing(self, products: List[Dict]):
        """
        ✅ NEW METHOD: Оновити "Used In Pricing" на основі фактично використаної ціни
        
        Логіка:
        1. Для кожного товару перевірити pricing_metadata
        2. Якщо calculation_method == 'competitor_based':
           - Знайти який конкурент має lowest_competitor price
           - Встановити used=True ТІЛЬКИ для цього товару
        3. Якщо calculation_method == 'competitor_capped_at_floor' або 'competitor_capped_at_max':
           - Всі товари залишаються used=False (ціна обмежена, а не використана)
        """
        self.logger.info("\n" + "="*60)
        self.logger.info("UPDATING 'Used In Pricing' FLAGS")
        self.logger.info("="*60)
        
        updated_count = 0
        
        for product in products:
            metadata = product.get('pricing_metadata', {})
            calculation_method = metadata.get('calculation_method')
            
            # ✅ КРИТИЧНО: Тільки якщо використана ціна конкурента БЕЗ обмежень
            if calculation_method == 'competitor_based':
                lowest_competitor = metadata.get('lowest_competitor')
                
                if lowest_competitor is None:
                    continue
                
                # Знайти який конкурент має цю ціну
                our_sku = product.get('sku')
                
                # Перевірити site1 (Coleman)
                if product.get('site1_price') == lowest_competitor:
                    site_sku = product.get('site1_sku')
                    if site_sku:
                        self.matched_tracker.track_match(
                            source='coleman',
                            competitor_sku=site_sku,
                            our_sku=our_sku,
                            used=True  # ✅ Цей використано!
                        )
                        updated_count += 1
                        self.logger.debug(
                            f"Product {our_sku}: Coleman {site_sku} used (${lowest_competitor})"
                        )
                
                # Перевірити site2 (1StopBedrooms)
                elif product.get('site2_price') == lowest_competitor:
                    site_sku = product.get('site2_sku')
                    if site_sku:
                        self.matched_tracker.track_match(
                            source='onestopbedrooms',
                            competitor_sku=site_sku,
                            our_sku=our_sku,
                            used=True  # ✅ Цей використано!
                        )
                        updated_count += 1
                        self.logger.debug(
                            f"Product {our_sku}: 1StopBedrooms {site_sku} used (${lowest_competitor})"
                        )
                
                # Перевірити site3 (AFA)
                elif product.get('site3_price') == lowest_competitor:
                    site_sku = product.get('site3_sku')
                    if site_sku:
                        self.matched_tracker.track_match(
                            source='afastores',
                            competitor_sku=site_sku,
                            our_sku=our_sku,
                            used=True  # ✅ Цей використано!
                        )
                        updated_count += 1
                        self.logger.debug(
                            f"Product {our_sku}: AFA {site_sku} used (${lowest_competitor})"
                        )
            
            # Якщо calculation_method != 'competitor_based':
            # - Всі товари залишаються used=False (вже встановлено в _match_and_track_competitor)
        
        self.logger.info(f"✓ Updated 'Used In Pricing' for {updated_count} competitor products")
    
    def _update_sheets(self, products: List[Dict]) -> int:
        """Оновити Google Sheets"""
        # Перевірити enable_price_updates
        if not self.runtime_config.get('enable_price_updates', True):
            self.logger.info("Price updates DISABLED in config")
            return 0
        
        # 1. Оновити основні ціни (тільки для matched products)
        updated = self.sheets_manager.batch_update_all(products)
        
        # 2. ✅ ОНОВЛЕНО: Передати matched_tracker для tracking колонок!
        if self.runtime_config.get('enable_competitors_sheet', True):
            # Передати competitor_data + matched_tracker
            competitors_updated = self.sheets_manager.batch_update_competitors_raw(
                self.competitor_data,  # ← RAW дані від scrapers
                matched_tracker=self.matched_tracker  # ← Для tracking колонок
            )
            
            self.logger.info(f"Competitors sheet: {competitors_updated} products")
            
            # ═══════════════════════════════════════════════════════
            # Показати matched tracking статистику
            # ═══════════════════════════════════════════════════════
            total_counts = {
                src: len(prods) 
                for src, prods in self.competitor_data.items()
            }
            stats = self.matched_tracker.get_statistics(total_counts)
            
            self.logger.info("\nMatched tracking statistics:")
            for source in ['coleman', 'onestopbedrooms', 'afastores']:
                s = stats.get(source, {'total': 0, 'matched': 0, 'used': 0})
                self.logger.info(
                    f"{source}: {s['total']} total | "
                    f"{s['matched']} matched | "
                    f"{s['used']} used"
                )
        
        return updated
    
    def _print_statistics(self, duration: float, total_products: int, updated_products: int):
        """Вивести статистику"""
        self.logger.info("\n" + "="*60)
        self.logger.info("STATISTICS")
        self.logger.info("="*60)
        self.logger.info(f"Duration: {duration/60:.1f} minutes")
        self.logger.info(f"Total products: {total_products}")
        self.logger.info(f"Updated products: {updated_products}")
        self.logger.info(f"Speed: {total_products/duration*60:.1f} products/min")
        self.logger.info("="*60)


def main():
    """Entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Furniture Repricer')
    parser.add_argument('--config', default='config.yaml', help='Config file path')
    parser.add_argument('--test', action='store_true', help='Run in test mode')
    
    args = parser.parse_args()
    
    repricer = FurnitureRepricer(args.config)
    repricer.run()


if __name__ == '__main__':
    main()
