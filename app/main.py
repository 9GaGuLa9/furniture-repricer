"""
Furniture Repricer - Main Script
"""

import sys
import argparse
from datetime import datetime
from pathlib import Path

# Додати root до path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.modules import get_config, get_logger, setup_logging, LogBlock
from app.modules import PricingEngine, BatchPricingProcessor, SKUMatcher

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
            'updated': 0,
            'errors': 0,
        }
    
    def _init_components(self):
        """Ініціалізувати компоненти"""
        try:
            self.logger.info("Initializing components...")
            
            # Pricing Engine
            coefficients = self.config.get_pricing_coefficients()
            self.pricing_engine = PricingEngine(coefficients)
            self.pricing_processor = BatchPricingProcessor(self.pricing_engine)
            
            # SKU Matcher
            sku_config = self.config.get('sku_matching', {})
            self.sku_matcher = SKUMatcher(sku_config)
            
            self.logger.info("✓ Components initialized")
        except Exception as e:
            self.logger.error(f"Failed to initialize: {e}", exc_info=True)
            raise
    
    def run(self):
        """Запустити репрайсер"""
        try:
            with LogBlock("Full Repricer Run", self.logger):
                self.logger.info("Repricer run started")
                
                # TODO: Додати логіку репрайсера
                # 1. Завантажити дані з Google Sheets
                # 2. Парсити ціни клієнта
                # 3. Парсити ціни конкурентів
                # 4. Співставити товари
                # 5. Розрахувати ціни
                # 6. Оновити Google Sheets
                
                self.logger.info("Repricer logic not yet implemented")
                self.logger.info("Add scrapers and Google Sheets integration")
                
                self._finalize_stats()
            
            self.logger.info("="*60)
            self.logger.info("Repricer Completed Successfully!")
            self.logger.info("="*60)
            
            return True
        except Exception as e:
            self.logger.error(f"Repricer failed: {e}", exc_info=True)
            return False
    
    def _finalize_stats(self):
        """Фіналізувати статистику"""
        end_time = datetime.now()
        duration = (end_time - self.stats['start_time']).total_seconds() / 60
        self.stats['duration_minutes'] = duration
        
        self.logger.info(f"Duration: {duration:.1f} minutes")
        self.logger.info(f"Total products: {self.stats['total_products']}")
        self.logger.info(f"Updated: {self.stats['updated']}")

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
