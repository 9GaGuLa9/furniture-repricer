"""
Furniture Repricer - Main Script with Full Integration
Повна інтеграція всіх scrapers та логіки репрайсера
"""

import sys
import argparse
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional

# Додати root до path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.modules import get_config, get_logger, setup_logging, LogBlock
from app.modules import PricingEngine, BatchPricingProcessor, SKUMatcher
from app.modules import GoogleSheetsClient, RepricerSheetsManager

# Імпорт scrapers
from app.scrapers.emmamason import scrape_emmamason
from app.scrapers.onestopbedrooms import scrape_onestopbedrooms
from app.scrapers.coleman import scrape_coleman
from app.scrapers.afa import scrape_afa


class FurnitureRepricer:
    """Головний клас репрайсера"""
    
    def __init__(self, test_mode: bool = False):
        self.test_mode = test_mode
        self.config = get_config()
        
        log_config = self.config.get('logging', {})
        self.logger = setup_logging(log_config)
        
        self.logger.info("="*60)
        self.logger.info("Furniture Repricer Started")
        self.logger.info(f"Mode: {'TEST' if test_mode else 'PRODUCTION'}")
        self.logger.info(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        self.logger.info("="*60)
        
        self._init_components()
        
        self.stats = {
            'start_time': datetime.now(),
            'total_products': 0,
            'client_products': 0,
            'competitor1_products': 0,
            'competitor2_products': 0,
            'competitor3_products': 0,
            'matched_products': 0,
            'updated': 0,
            'errors': 0,
        }
        
        # Зберігаємо scraped дані
        self.client_data = []
        self.competitor_data = {
            'onestopbedrooms': [],
            'coleman': [],
            'afa': []
        }
    
    def _init_components(self):
        """Ініціалізувати компоненти"""
        try:
            self.logger.info("Initializing components...")
            
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
            
            # Pricing Engine
            self.logger.info("Initializing pricing engine...")
            coefficients = self.config.get_pricing_coefficients()
            self.pricing_engine = PricingEngine(coefficients)
            self.pricing_processor = BatchPricingProcessor(self.pricing_engine)
            
            # SKU Matcher
            self.logger.info("Initializing SKU matcher...")
            sku_config = self.config.get('sku_matching', {})
            self.sku_matcher = SKUMatcher(sku_config)
            
            self.logger.info("✓ Components initialized")
        except Exception as e:
            self.logger.error(f"Failed to initialize: {e}", exc_info=True)
            raise
    
    def _load_client_data(self) -> List[Dict]:
        """
        1. Завантажити дані з Google Sheets
        Повертає список товарів клієнта з їх cost, current_price, url
        """
        with LogBlock("Loading Client Data from Google Sheets", self.logger):
            try:
                # Завантажити основні дані
                products = self.sheets_manager.get_main_data()
                
                if self.test_mode:
                    test_limit = self.config.test_limit
                    products = products[:test_limit]
                    self.logger.info(f"TEST MODE: Limited to {test_limit} products")
                
                self.logger.info(f"Loaded {len(products)} products from Google Sheets")
                self.stats['total_products'] = len(products)
                
                return products
                
            except Exception as e:
                self.logger.error(f"Failed to load client data: {e}", exc_info=True)
                return []
    
    def _scrape_client_prices(self, products: List[Dict]) -> List[Dict]:
        """
        2. Парсити ціни клієнта (Emma Mason)
        Оновлює products з актуальними цінами з сайту
        """
        with LogBlock("Scraping Client Prices (Emma Mason)", self.logger):
            if not self.config.is_scraper_enabled('emmamason'):
                self.logger.warning("Emma Mason scraper disabled in config")
                return products
            
            try:
                # Отримати список URL товарів клієнта
                client_urls = []
                for product in products:
                    # Спробувати різні варіанти назв колонок URL
                    url = (product.get('our_url') or 
                           product.get('Our URL') or 
                           product.get('url') or
                           product.get('URL'))
                    
                    if url and url.strip():  # Перевірити що не порожній
                        client_urls.append(url.strip())
                    else:
                        # Лог для відладки
                        sku = product.get('sku') or product.get('SKU')
                        self.logger.debug(f"No URL for SKU {sku}")
                
                if not client_urls:
                    self.logger.warning("No client URLs found in data")
                    return products
                
                self.logger.info(f"Scraping {len(client_urls)} client products...")
                
                # Парсити ціни
                scraper_config = self.config.get_scraper_config('emmamason')
                scraped_prices = scrape_emmamason(client_urls, scraper_config)
                
                self.stats['client_products'] = len(scraped_prices)
                self.logger.info(f"Scraped {len(scraped_prices)} client prices")
                
                # Оновити products з новими цінами
                for product in products:
                    product_url = product.get('our_url') or product.get('url')
                    
                    # Знайти відповідну scraped ціну
                    for scraped in scraped_prices:
                        if scraped['url'] == product_url:
                            product['our_current_price'] = scraped['price']
                            break
                
                return products
                
            except Exception as e:
                self.logger.error(f"Failed to scrape client prices: {e}", exc_info=True)
                return products
    
    def _scrape_competitors(self) -> dict:
        """
        3. Парсити ціни конкурентів
        Повертає словник з даними від кожного конкурента
        """
        with LogBlock("Scraping Competitors", self.logger):
            competitor_data = {}
            
            # 1StopBedrooms
            if self.config.is_scraper_enabled('onestopbedrooms'):
                try:
                    self.logger.info("Scraping 1StopBedrooms...")
                    config = self.config.get_scraper_config('onestopbedrooms')
                    products = scrape_onestopbedrooms(config)
                    competitor_data['onestopbedrooms'] = products
                    self.stats['competitor1_products'] = len(products)
                    self.logger.info(f"✓ 1StopBedrooms: {len(products)} products")
                except Exception as e:
                    self.logger.error(f"Failed to scrape 1StopBedrooms: {e}")
                    competitor_data['onestopbedrooms'] = []
            
            # Coleman - ОНОВЛЕНО з підтримкою category_filter
            if self.config.is_scraper_enabled('coleman'):
                try:
                    self.logger.info("Scraping Coleman Furniture...")
                    config = self.config.get_scraper_config('coleman')
                    
                    # Отримати category_filter з конфігу (опціонально)
                    category_filter = config.get('category_filter', None)
                    
                    if category_filter:
                        self.logger.info(f"Using category filter: {category_filter}")
                    
                    # Викликати scraper з фільтром
                    products = scrape_coleman(config, category_filter)
                    
                    competitor_data['coleman'] = products
                    self.stats['competitor2_products'] = len(products)
                    self.logger.info(f"✓ Coleman: {len(products)} products")
                except Exception as e:
                    self.logger.error(f"Failed to scrape Coleman: {e}")
                    competitor_data['coleman'] = []
            
            # AFA
            if self.config.is_scraper_enabled('afa'):
                try:
                    self.logger.info("Scraping AFA Stores...")
                    config = self.config.get_scraper_config('afa')
                    products = scrape_afa(config)
                    competitor_data['afa'] = products
                    self.stats['competitor3_products'] = len(products)
                    self.logger.info(f"✓ AFA: {len(products)} products")
                except Exception as e:
                    self.logger.error(f"Failed to scrape AFA: {e}")
                    competitor_data['afa'] = []
            
            return competitor_data

    
    def _match_products(self, client_products: List[Dict], 
                    competitor_data: dict) -> List[Dict]:
        """
        4. Співставити товари за SKU
        Знаходить відповідні товари конкурентів для кожного товару клієнта
        
        З ДЕТАЛЬНИМ DEBUG LOGGING
        """
        with LogBlock("Matching Products by SKU", self.logger):
            
            # ============================================================
            # 🆕 DEBUG: Показати статистику та приклади SKU
            # ============================================================
            
            self.logger.info("="*60)
            self.logger.info("SKU MATCHING DEBUG INFO")
            self.logger.info("="*60)
            
            # Показати кількість товарів від кожного конкурента
            onestop_count = len(competitor_data.get('onestopbedrooms', []))
            coleman_count = len(competitor_data.get('coleman', []))
            afa_count = len(competitor_data.get('afa', []))
            
            self.logger.info(f"Competitor data available:")
            self.logger.info(f"  1StopBedrooms: {onestop_count} products")
            self.logger.info(f"  Coleman: {coleman_count} products")
            self.logger.info(f"  AFA: {afa_count} products")
            self.logger.info(f"Client products: {len(client_products)}")
            
            # Показати приклади SKU з кожного джерела
            if client_products:
                client_sample = client_products[0]
                client_sku = client_sample.get('sku') or client_sample.get('SKU')
                self.logger.info(f"\nDEBUG: Client SKU example: '{client_sku}'")
                self.logger.info(f"  Type: {type(client_sku)}")
                self.logger.info(f"  Length: {len(client_sku) if client_sku else 0}")
            
            if competitor_data.get('onestopbedrooms'):
                onestop_sample = competitor_data['onestopbedrooms'][0]
                onestop_sku = onestop_sample.get('sku', '')
                self.logger.info(f"\nDEBUG: 1StopBedrooms SKU example: '{onestop_sku}'")
                self.logger.info(f"  Type: {type(onestop_sku)}")
                self.logger.info(f"  Sample data: {onestop_sample}")
            
            if competitor_data.get('coleman'):
                coleman_sample = competitor_data['coleman'][0]
                coleman_sku = coleman_sample.get('sku', '')
                self.logger.info(f"\nDEBUG: Coleman SKU example: '{coleman_sku}'")
                self.logger.info(f"  Type: {type(coleman_sku)}")
                self.logger.info(f"  Sample data: {coleman_sample}")
            
            if competitor_data.get('afa'):
                afa_sample = competitor_data['afa'][0]
                afa_sku = afa_sample.get('sku', '')
                self.logger.info(f"\nDEBUG: AFA SKU example: '{afa_sku}'")
                self.logger.info(f"  Type: {type(afa_sku)}")
                self.logger.info(f"  Sample data: {afa_sample}")
            
            # Показати налаштування matcher
            self.logger.info(f"\nSKU Matcher config:")
            self.logger.info(f"  Strategy: {self.sku_matcher.strategy}")
            self.logger.info(f"  Case sensitive: {self.sku_matcher.case_sensitive}")
            self.logger.info(f"  Delimiter: '{self.sku_matcher.delimiter}'")
            if self.sku_matcher.strategy == 'fuzzy':
                self.logger.info(f"  Fuzzy threshold: {self.sku_matcher.fuzzy_threshold}")
            
            # Тестові matching для перших SKU
            if client_products and competitor_data.get('coleman'):
                test_client = client_sku
                test_coleman = coleman_sku
                match_result = self.sku_matcher.matches(test_client, test_coleman)
                self.logger.info(f"\nTest match: '{test_client}' vs '{test_coleman}'")
                self.logger.info(f"  Result: {match_result}")
                
                # Якщо fuzzy - показати score
                if self.sku_matcher.strategy == 'fuzzy':
                    score = self.sku_matcher.fuzzy_match(test_client, test_coleman)
                    self.logger.info(f"  Fuzzy score: {score:.3f}")
            
            self.logger.info("="*60)
            
            # ============================================================
            # MAIN MATCHING LOOP
            # ============================================================
            
            matched_count = 0
            match_stats = {
                'onestopbedrooms': 0,
                'coleman': 0,
                'afa': 0,
                'total_attempts': 0
            }
            
            # Логувати перші 3 товари детально
            debug_first_n = 3
            
            for idx, product in enumerate(client_products):
                client_sku = product.get('sku') or product.get('SKU')
                if not client_sku:
                    continue
                
                match_stats['total_attempts'] += 1
                debug_mode = (idx < debug_first_n)
                
                if debug_mode:
                    self.logger.info(f"\n--- Product {idx+1}/{len(client_products)} ---")
                    self.logger.info(f"Client SKU: '{client_sku}'")
                
                # Знайти відповідні товари у конкурентів
                competitor_prices = []
                product_matched = False
                
                # ============================================================
                # 1StopBedrooms
                # ============================================================
                if debug_mode:
                    self.logger.info("  Checking 1StopBedrooms...")
                
                onestop_matched = False
                for comp_product in competitor_data.get('onestopbedrooms', []):
                    comp_sku = comp_product.get('sku', '')
                    
                    if self.sku_matcher.matches(client_sku, comp_sku):
                        product['site1_sku'] = comp_product['sku']
                        product['site1_price'] = comp_product.get('price')
                        product['site1_url'] = comp_product.get('url')
                        
                        if comp_product.get('price'):
                            competitor_prices.append(float(comp_product['price']))
                        
                        match_stats['onestopbedrooms'] += 1
                        onestop_matched = True
                        product_matched = True
                        
                        if debug_mode:
                            self.logger.info(f"    ✓ MATCH! '{comp_sku}' - ${comp_product.get('price')}")
                        
                        break
                
                if debug_mode and not onestop_matched:
                    self.logger.info(f"    ✗ No match in 1StopBedrooms")
                
                # ============================================================
                # Coleman
                # ============================================================
                if debug_mode:
                    self.logger.info("  Checking Coleman...")
                
                coleman_matched = False
                for comp_product in competitor_data.get('coleman', []):
                    comp_sku = comp_product.get('sku', '')
                    
                    if self.sku_matcher.matches(client_sku, comp_sku):
                        product['site2_sku'] = comp_product['sku']
                        product['site2_price'] = comp_product.get('price')
                        product['site2_url'] = comp_product.get('url')
                        
                        if comp_product.get('price'):
                            competitor_prices.append(float(comp_product['price']))
                        
                        match_stats['coleman'] += 1
                        coleman_matched = True
                        product_matched = True
                        
                        if debug_mode:
                            self.logger.info(f"    ✓ MATCH! '{comp_sku}' - ${comp_product.get('price')}")
                        
                        break
                
                if debug_mode and not coleman_matched:
                    self.logger.info(f"    ✗ No match in Coleman")
                
                # ============================================================
                # AFA
                # ============================================================
                if debug_mode:
                    self.logger.info("  Checking AFA...")
                
                afa_matched = False
                for comp_product in competitor_data.get('afa', []):
                    comp_sku = comp_product.get('sku', '')
                    
                    if self.sku_matcher.matches(client_sku, comp_sku):
                        product['site3_sku'] = comp_product['sku']
                        product['site3_price'] = comp_product.get('price')
                        product['site3_url'] = comp_product.get('url')
                        
                        if comp_product.get('price'):
                            competitor_prices.append(float(comp_product['price']))
                        
                        match_stats['afa'] += 1
                        afa_matched = True
                        product_matched = True
                        
                        if debug_mode:
                            self.logger.info(f"    ✓ MATCH! '{comp_sku}' - ${comp_product.get('price')}")
                        
                        break
                
                if debug_mode and not afa_matched:
                    self.logger.info(f"    ✗ No match in AFA")
                
                # ============================================================
                # Зберегти результат
                # ============================================================
                
                product['competitor_prices'] = competitor_prices
                
                if product_matched:
                    matched_count += 1
                    
                    if debug_mode:
                        self.logger.info(f"  Result: MATCHED with {len(competitor_prices)} competitors")
                        self.logger.info(f"  Prices: {competitor_prices}")
                else:
                    if debug_mode:
                        self.logger.info(f"  Result: NO MATCHES")
            
            # ============================================================
            # 🆕 DEBUG: Фінальна статистика
            # ============================================================
            
            self.logger.info("\n" + "="*60)
            self.logger.info("MATCHING RESULTS")
            self.logger.info("="*60)
            self.logger.info(f"Total client products: {len(client_products)}")
            self.logger.info(f"Products matched: {matched_count} ({matched_count/len(client_products)*100:.1f}%)")
            self.logger.info(f"\nMatches by competitor:")
            self.logger.info(f"  1StopBedrooms: {match_stats['onestopbedrooms']}")
            self.logger.info(f"  Coleman: {match_stats['coleman']}")
            self.logger.info(f"  AFA: {match_stats['afa']}")
            self.logger.info(f"\nAverage matches per product: {sum([match_stats['onestopbedrooms'], match_stats['coleman'], match_stats['afa']])/len(client_products):.2f}")
            
            # Якщо matched = 0, показати додаткову діагностику
            if matched_count == 0:
                self.logger.warning("\n⚠️ WARNING: NO MATCHES FOUND!")
                self.logger.warning("Possible reasons:")
                self.logger.warning("1. SKU formats don't match (check examples above)")
                self.logger.warning("2. Case sensitivity issue (try case_sensitive: false)")
                self.logger.warning("3. Special characters or delimiters differ")
                self.logger.warning("4. SKUs use different naming conventions")
                self.logger.warning("\nSuggested fixes:")
                self.logger.warning("- Set 'case_sensitive: false' in config.yaml")
                self.logger.warning("- Try 'strategy: fuzzy' for approximate matching")
                self.logger.warning("- Check if SKUs have prefixes/suffixes that need stripping")
            
            self.logger.info("="*60)
            
            # Зберегти статистику
            self.stats['matched_products'] = matched_count
            self.logger.info(f"\nMatched {matched_count} products with competitors")
            
            return client_products
    
    def _calculate_prices(self, products: List[Dict]) -> List[Dict]:
        """
        5. Розрахувати рекомендовані ціни
        Використовує pricing formula для кожного товару
        """
        with LogBlock("Calculating Suggested Prices", self.logger):
            try:
                # 🆕 Нормалізувати назви колонок
                for product in products:
                    if 'Our Cost' in product:
                        product['cost'] = product['Our Cost']
                    if 'Our Sales Price' in product:
                        product['current_price'] = product['Our Sales Price']

                # Використати batch processor
                products_with_prices = self.pricing_processor.process_products(products)
                
                # Статистика
                with_suggestions = [p for p in products_with_prices 
                                   if p.get('suggested_price')]
                
                self.logger.info(f"Calculated prices for {len(with_suggestions)} products")
                
                # Показати статистику
                stats = self.pricing_processor.get_statistics(products_with_prices)
                self.logger.info(f"Average cost: ${stats['avg_cost']:.2f}")
                self.logger.info(f"Average suggested: ${stats['avg_suggested_price']:.2f}")
                
                return products_with_prices
                
            except Exception as e:
                self.logger.error(f"Failed to calculate prices: {e}", exc_info=True)
                return products
    
    def _update_sheets(self, products: List[Dict]) -> int:
        """
        6. Оновити Google Sheets (ОПТИМІЗОВАНА ВЕРСІЯ)
        Записує оновлені ціни та дані конкурентів назад у таблицю
        """
        with LogBlock("Updating Google Sheets", self.logger):
            try:
                # Підготувати prices для кожного товару
                products_with_prices = []
                
                for product in products:
                    sku = product.get('sku') or product.get('SKU')
                    if not sku:
                        continue
                    
                    # Зібрати всі prices в один словник
                    prices = {}
                    
                    # Our current price (якщо парсили)
                    if 'our_current_price' in product:
                        prices['our_price'] = product['our_current_price']
                    
                    # Suggested price
                    if 'suggested_price' in product:
                        prices['suggest_price'] = product['suggested_price']
                    
                    # Competitor 1 (1StopBedrooms)
                    if 'site1_price' in product:
                        prices['site1_price'] = product['site1_price']
                        prices['site1_url'] = product.get('site1_url', '')
                    
                    # Competitor 2 (Coleman)
                    if 'site2_price' in product:
                        prices['site2_price'] = product['site2_price']
                        prices['site2_url'] = product.get('site2_url', '')
                    
                    # Competitor 3 (AFA)
                    if 'site3_price' in product:
                        prices['site3_price'] = product['site3_price']
                        prices['site3_url'] = product.get('site3_url', '')
                    
                    # Зберегти prices в товарі
                    if prices:
                        product['_prices_to_update'] = prices
                        products_with_prices.append(product)
                
                # ОДИН batch update для ВСІХ товарів
                if products_with_prices:
                    self.logger.info(f"Batch updating {len(products_with_prices)} products...")
                    
                    # Використати batch_update_all замість циклу
                    updated = self.sheets_manager.batch_update_all(products_with_prices)
                    
                    self.stats['updated'] = updated
                    self.logger.info(f"✓ Batch update completed: {updated} products")
                    
                    return updated
                else:
                    self.logger.warning("No products with prices to update")
                    return 0
                
            except Exception as e:
                self.logger.error(f"Failed to update sheets: {e}", exc_info=True)
                return 0
    
    def run(self):
        """Запустити репрайсер - головна логіка"""
        try:
            with LogBlock("Full Repricer Run", self.logger):
                
                # 1. Завантажити дані з Google Sheets
                self.logger.info("\n[STEP 1/6] Loading client data...")
                products = self._load_client_data()
                
                if not products:
                    self.logger.error("No products loaded - aborting")
                    return False
                
                # 2. Парсити ціни клієнта
                self.logger.info("\n[STEP 2/6] Scraping client prices...")
                products = self._scrape_client_prices(products)
                
                # 3. Парсити ціни конкурентів
                self.logger.info("\n[STEP 3/6] Scraping competitor prices...")
                competitor_data = self._scrape_competitors()
                
                # 4. Співставити товари
                self.logger.info("\n[STEP 4/6] Matching products...")
                products = self._match_products(products, competitor_data)
                
                # 5. Розрахувати ціни
                self.logger.info("\n[STEP 5/6] Calculating prices...")
                products = self._calculate_prices(products)
                
                # 6. Оновити Google Sheets
                self.logger.info("\n[STEP 6/6] Updating Google Sheets...")
                updated = self._update_sheets(products)
                
                self._finalize_stats()
            
            self.logger.info("="*60)
            self.logger.info("✓ Repricer Completed Successfully!")
            self.logger.info("="*60)
            
            return True
            
        except Exception as e:
            self.logger.error(f"Repricer failed: {e}", exc_info=True)
            self.stats['errors'] += 1
            return False
    
    def _finalize_stats(self):
        """Фіналізувати та вивести статистику"""
        end_time = datetime.now()
        duration = (end_time - self.stats['start_time']).total_seconds() / 60
        self.stats['duration_minutes'] = duration
        
        self.logger.info("\n" + "="*60)
        self.logger.info("FINAL STATISTICS")
        self.logger.info("="*60)
        self.logger.info(f"Duration: {duration:.1f} minutes")
        self.logger.info(f"Total products: {self.stats['total_products']}")
        self.logger.info(f"Client products scraped: {self.stats['client_products']}")
        self.logger.info(f"Competitor 1 (1StopBedrooms): {self.stats['competitor1_products']}")
        self.logger.info(f"Competitor 2 (Coleman): {self.stats['competitor2_products']}")
        self.logger.info(f"Competitor 3 (AFA): {self.stats['competitor3_products']}")
        self.logger.info(f"Products matched: {self.stats['matched_products']}")
        self.logger.info(f"Products updated: {self.stats['updated']}")
        self.logger.info(f"Errors: {self.stats['errors']}")
        self.logger.info("="*60)


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='Furniture Price Repricer')
    parser.add_argument('--test', '-t', action='store_true',
                       help='Run in test mode (limited products)')
    
    args = parser.parse_args()
    
    repricer = FurnitureRepricer(test_mode=args.test)
    success = repricer.run()
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
