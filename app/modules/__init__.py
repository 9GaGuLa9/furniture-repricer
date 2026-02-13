"""
Modules package for Furniture Repricer
UPDATED v5.0 - With ConfigManager, ErrorLogger support
"""

from .logger import get_logger, setup_logging, LogBlock
from .google_sheets import GoogleSheetsClient, RepricerSheetsManager
from .pricing import PricingEngine, BatchPricingProcessor
from .sku_matcher import SKUMatcher

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
    
    # Config Management
    'ConfigManager',
    'GoogleSheetsConfigReader',
    
    # Error Logging
    'ErrorLogger',
    'ScraperErrorMixin',
]
