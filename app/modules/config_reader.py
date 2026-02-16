"""
Module for reading configuration from Google Sheets
Reads Config and Price_rules sheets to control the repricer
"""

from typing import Dict, Any, List, Optional
from .logger import get_logger

logger = get_logger("config_reader")


class GoogleSheetsConfigReader:
    """Reading configuration from Google Sheets"""
    
    def __init__(self, sheets_client, main_sheet_id: str):
        """
        Args:
            sheets_client: GoogleSheetsClient instance
            main_sheet_id: ID main table
        """
        self.client = sheets_client
        self.sheet_id = main_sheet_id
        self.logger = logger
    
    def read_config(self) -> Dict[str, Any]:
        """
        Reading the configuration from the “Config” sheet
        
        Structure:
        | Parameter | Value | Description |
        |-----------|-------|-------------|
        | run_enabled | TRUE | ... |
        
        Returns:
            Dictionary with configuration parameters
        """
        try:
            self.logger.info("Reading Config from Google Sheets...")
            
            # Try to find the Config sheet
            try:
                data = self.client.read_all_data(self.sheet_id, "Config")
            except Exception:
                self.logger.warning("Config sheet not found, using defaults")
                return self._get_default_config()
            
            if not data or len(data) < 2:
                self.logger.warning("Config sheet is empty, using defaults")
                return self._get_default_config()
            
            # Data parsing
            config = {}
            
            # Skip header (line 1)
            for row in data[1:]:
                if len(row) < 2:
                    continue
                
                param_name = row[0].strip()
                param_value = row[1].strip() if len(row) > 1 else ""
                
                if not param_name or param_name.startswith("==="):
                    continue  # Skip empty lines and separators
                
                # Convert values
                config[param_name] = self._parse_value(param_value)
            
            # Logging
            self.logger.info(f"[OK] Loaded {len(config)} parameters from Config sheet")
            
            # Show critical parameters
            critical_params = [
                'run_enabled',
                'scraper_emmamason',
                'enable_price_updates',
                'enable_price_history'
            ]
            
            for param in critical_params:
                if param in config:
                    self.logger.info(f"  {param}: {config[param]}")
            
            # Merge with defaults (if some parameters are missing)
            default_config = self._get_default_config()
            for key, value in default_config.items():
                if key not in config:
                    config[key] = value
            
            return config
            
        except Exception as e:
            self.logger.error(f"Failed to read Config: {e}")
            return self._get_default_config()
    
    def read_price_rules(self) -> Dict[str, float]:
        """
        Reading the pricing rules from the sheet "Price_rules"
        
        Structure:
        | Parameter                  | Value |
        |----------------------------|-------|
        | Floor (rate)               | 1.5   |
        | Below Lowest Competitor($) | 1     |
        | Max (rate)                 | 2     |
        
        Returns:
            Glossary of pricing rules
        """
        try:
            self.logger.info("Reading Price_rules from Google Sheets...")
            
            # Try to find the Price_rules sheet
            try:
                data = self.client.read_all_data(self.sheet_id, "Price_rules")
            except Exception:
                self.logger.warning("Price_rules sheet not found, using defaults")
                return self._get_default_price_rules()
            
            if not data or len(data) < 2:
                self.logger.warning("Price_rules sheet is empty, using defaults")
                return self._get_default_price_rules()
            
            # Data parsing
            rules = {}
            
            # Skip header (line 1)
            for row in data[1:]:
                if len(row) < 2:
                    continue
                
                param_name = row[0].strip()
                param_value = row[1].strip() if len(row) > 1 else ""
                
                if not param_name:
                    continue
                
                # Normalize parameter names
                # "Floor (rate)" -> "floor_rate"
                # "Below Lowest Competitor ($)" -> "below_competitor"
                # "Max (rate)" -> "max_rate"
                
                if "floor" in param_name.lower():
                    rules['floor_rate'] = self._parse_float(param_value, 1.5)
                
                elif "below" in param_name.lower() and "competitor" in param_name.lower():
                    rules['below_competitor'] = self._parse_float(param_value, 1.0)
                
                elif "max" in param_name.lower():
                    rules['max_rate'] = self._parse_float(param_value, 2.0)
            
            # Logging
            self.logger.info(f"[OK] Loaded price rules:")
            self.logger.info(f"  Floor rate: {rules.get('floor_rate', 1.5)}")
            self.logger.info(f"  Below competitor: ${rules.get('below_competitor', 1.0)}")
            self.logger.info(f"  Max rate: {rules.get('max_rate', 2.0)}")
            
            # Merge with defaults
            default_rules = self._get_default_price_rules()
            for key, value in default_rules.items():
                if key not in rules:
                    rules[key] = value
            
            return rules
            
        except Exception as e:
            self.logger.error(f"Failed to read Price_rules: {e}")
            return self._get_default_price_rules()
    
    def _parse_value(self, value: str) -> Any:
        """
        Convert string values to the appropriate type
        
        Args:
            value: String value
        
        Returns:
            Converted value (bool, int, float or string)
        """
        if not value:
            return None
        
        value_upper = value.upper()
        
        # Boolean
        if value_upper == "TRUE":
            return True
        if value_upper == "FALSE":
            return False
        
        # Number
        try:
            # FIXED: Replace comma with dot for European decimal separator
            value_normalized = value.replace(',', '.')
            
            # Try int
            if '.' not in value_normalized:
                return int(value_normalized)
            # Try float
            return float(value_normalized)
        except ValueError:
            pass
        
        # String
        return value
    
    def _parse_float(self, value: str, default: float = 0.0) -> float:
        """
        Convert to float with default value
        
        Args:
            value: String value
            default: Default if conversion failed
        
        Returns:
            Float value
        """
        if not value:
            return default
        
        try:
            return float(value.replace(',', '.'))
        except ValueError:
            self.logger.warning(f"Failed to parse float '{value}', using default {default}")
            return default
    
    def _get_default_config(self) -> Dict[str, Any]:
        """
        Default configuration if Config sheet not found
        
        Returns:
            Dictionary with default parameters
        """
        return {
            # System
            'run_enabled': True,
            'test_mode': False,
            'dry_run': False,
            'log_level': 'INFO',
            
            # Scrapers
            'scraper_emmamason': True,
            'scraper_coleman': True,
            'scraper_onestopbedrooms': True,
            'scraper_afastores': True,
            'delay_between_requests': 3,
            'max_products_emmamason': 50000,
            'max_products_per_competitor': 50000,
            'scraping_timeout_minutes': 45,
            
            # Emma Mason
            'emmamason_target_brands': 'ALL',
            'emmamason_country_code': 'US',
            'emmamason_max_retries': 3,
            
            # Pricing
            'enable_price_updates': True,
            'update_only_with_competitors': False,
            'min_price_change_percent': 0.5,
            'max_price_change_percent': 20.0,
            
            # Data
            'enable_price_history': True,
            'enable_competitors_sheet': True,
            'save_scraping_errors': True,
            
            # Validation
            'validate_prices_range': True,
            'min_valid_price': 10.0,
            'max_valid_price': 50000.0,
            'reject_zero_prices': True,
            
            # Performance
            'batch_size_sheets_update': 500,
            'retry_on_rate_limit': True,
            
            # Notifications
            'telegram_enabled': True,
            'telegram_on_errors_only': False,

            # Retention
            'log_retention_days': 10,
            'error_retention_days': 10,
        }
    
    def _get_default_price_rules(self) -> Dict[str, float]:
        """
        Default pricing rules
        
        Returns:
            Glossary of default rules
        """
        return {
            'floor_rate': 1.5,        # Min price = Our Cost * 1.5
            'below_competitor': 1.0,   # $1 lower than the competitor
            'max_rate': 2.0,          # Max price = Our Cost * 2.0
        }
