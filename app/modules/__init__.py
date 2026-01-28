"""
Modules package для Furniture Repricer
UPDATED v5.0 - With ConfigManager, ErrorLogger support
"""

from .logger import get_logger, setup_logging, LogBlock
from .google_sheets import GoogleSheetsClient, RepricerSheetsManager
from .pricing import PricingEngine, BatchPricingProcessor
from .sku_matcher import SKUMatcher
# from .config import get_config, Config

# ✅ NEW IMPORTS для ConfigManager + ErrorLogger
from .config_manager import ConfigManager
from .config_reader import GoogleSheetsConfigReader
from .error_logger import ErrorLogger, ScraperErrorMixin

__all__ = [
    # Logging
    'get_logger',
    'setup_logging',
    'LogBlock',
    
    # Google Sheets
    'GoogleSheetsClient',
    'RepricerSheetsManager',
    
    # Pricing
    'PricingEngine',
    'BatchPricingProcessor',
    
    # SKU Matching
    'SKUMatcher',
    
    # Old Config (deprecated but kept for compatibility)
    'get_config',
    'Config',
    
    # ✅ NEW: Config Management
    'ConfigManager',
    'GoogleSheetsConfigReader',
    
    # ✅ NEW: Error Logging
    'ErrorLogger',
    'ScraperErrorMixin',
]
