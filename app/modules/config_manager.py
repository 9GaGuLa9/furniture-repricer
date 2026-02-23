"""
ConfigManager - Merge YAML defaults from Google Sheets overrides

YAML = unchangeable defaults
Google Sheets = customer changes (overrides)
Merged config = used in runtime
"""

import yaml
from typing import Dict, Any, List, Optional
from pathlib import Path
from .config_reader import GoogleSheetsConfigReader
from .logger import get_logger

logger = get_logger("config_manager")


class ConfigManager:
    """
    Configuration management with merge logic
    
    Priority: Google Sheets > YAML defaults > Hardcoded defaults
    """
    
    def __init__(self, yaml_path: str, sheets_reader: GoogleSheetsConfigReader):
        """
        Args:
            yaml_path: Path to config.yaml
            sheets_reader: GoogleSheetsConfigReader instance
        """
        self.yaml_path = Path(yaml_path)
        self.sheets_reader = sheets_reader
        self.logger = logger
        
        # Cached config
        self._merged_config = None
        self._price_rules = None
    
    def get_config(self, force_reload: bool = False) -> Dict[str, Any]:
        """
        Get merged configuration
        
        Args:
            force_reload: Force reload (ignore cache)
        
        Returns:
            Merged config dictionary
        """
        if self._merged_config is None or force_reload:
            self._merged_config = self._merge_configs()
        
        return self._merged_config
    
    def get_price_rules(self, force_reload: bool = False) -> Dict[str, float]:
        """
        Get price rules
        
        Args:
            force_reload: Force restart
        
        Returns:
            Price rules dictionary
        """
        if self._price_rules is None or force_reload:
            # Try with Google Sheets
            sheets_rules = self.sheets_reader.read_price_rules()
            
            # Fallback to YAML if Google Sheets is empty
            if not sheets_rules or all(v == 0 for v in sheets_rules.values()):
                self.logger.warning("Price_rules empty in Google Sheets, using YAML defaults")
                yaml_config = self._load_yaml_config()
                sheets_rules = yaml_config.get('price_rules', self._get_hardcoded_price_rules())
            
            self._price_rules = sheets_rules
        
        return self._price_rules
    
    def _merge_configs(self) -> Dict[str, Any]:
        """
        Merge configurations with the correct priority
        
        Returns:
            Merged config
        """
        self.logger.info("="*60)
        self.logger.info("MERGING CONFIGURATION...")
        self.logger.info("="*60)
        
        # 1. Hardcoded defaults (lowest priority)
        config = self._get_hardcoded_defaults()
        self.logger.info("[OK] Loaded hardcoded defaults")
        
        # 2. YAML config (medium priority)
        try:
            yaml_config = self._load_yaml_config()
            
            # Merge from YAML
            for key, value in yaml_config.items():
                if key != 'price_rules':  # Price rules separately
                    config[key] = value
            
            self.logger.info(f"[OK] Loaded YAML config from {self.yaml_path}")
            
        except FileNotFoundError:
            self.logger.warning(f"YAML config not found: {self.yaml_path}")
            self.logger.warning("Using hardcoded defaults only")
        
        except Exception as e:
            self.logger.error(f"Failed to load YAML: {e}")
            self.logger.warning("Using hardcoded defaults only")
        
        # 3. Google Sheets overrides (highest priority)
        try:
            sheets_config = self.sheets_reader.read_config()
            
            # Find which parameters the client has changed
            overrides = []
            new_params = []
            
            for key, value in sheets_config.items():
                if key in config:
                    if config[key] != value:
                        overrides.append(f"  {key}: {config[key]} -> {value}")
                        config[key] = value
                else:
                    new_params.append(f"  {key}: {value}")
                    config[key] = value
            
            # Change log
            if overrides:
                self.logger.info("[OK] Client OVERRIDES from Google Sheets:")
                for override in overrides:
                    self.logger.info(override)
            
            if new_params:
                self.logger.info("[OK] Client NEW parameters from Google Sheets:")
                for param in new_params:
                    self.logger.info(param)
            
            if not overrides and not new_params:
                self.logger.info("[OK] No overrides from Google Sheets (using YAML/defaults)")
            
        except Exception as e:
            self.logger.error(f"Failed to load Google Sheets config: {e}")
            self.logger.warning("Using YAML/hardcoded defaults only")
        
        self.logger.info("="*60)
        
        return config
    
    def _load_yaml_config(self) -> Dict[str, Any]:
        """
        Download YAML configuration
        
        Returns:
            YAML config dictionary
        """
        with open(self.yaml_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f) or {}
    
    def _get_hardcoded_defaults(self) -> Dict[str, Any]:
        """
        Hardcoded defaults (fallback if there is no YAML or Google Sheets)
        
        Returns:
            Default config
        """
        return {
            # === SYSTEM ===
            'run_enabled': True,
            'test_mode': False,
            'dry_run': False,
            'log_level': 'INFO',
            'sys_log_level': 'INFO',
            'scrap_log_level': 'INFO',
            'scheduler_log_level': 'INFO',
            
            # === SCRAPERS CONTROL ===
            'scraper_emmamason': True,
            'scraper_coleman': True,
            'scraper_onestopbedrooms': True,
            'scraper_afastores': True,
            'site4_enabled': False,
            'site5_enabled': False,
            
            # === SCRAPING LIMITS ===
            'max_products_emmamason': 15000,
            'max_products_per_competitor': 50000,
            'scraping_timeout_minutes': 300,
            
            # === EMMA MASON SPECIFIC ===
            'emmamason_max_retries': 3,
            
            # === PRICING RULES ===
            'enable_price_updates': True,
            'update_only_with_competitors': False,
            'min_price_change_percent': 0.5,
            'max_price_change_percent': 20.0,
            
            # === DATA & HISTORY ===
            'enable_price_history': True,
            'enable_competitors_sheet': True,
            'save_scraping_errors': True,
            
            # === VALIDATION ===
            'validate_prices_range': True,
            'min_valid_price': 10.0,
            'max_valid_price': 50000.0,
            'reject_zero_prices': True,
            
            # === PERFORMANCE ===
            'batch_size_sheets_update': 500,
            'max_concurrent_requests': 5,
            'retry_on_rate_limit': True,
            'rate_limit_delay_seconds': 60,
            
            # === SCHEDULE ===
            'schedule_enabled': True,
            'schedule_times': '06:00,16:00,21:00',
            'schedule_timezone': 'America/New_York',
            
            # === NOTIFICATIONS ===
            'telegram_enabled': True,
            'telegram_on_errors_only': False,
            'telegram_chat_id': '',
            
            # === TESTING & DEBUG ===
            'test_sample_size': 100,

            # === RETENTION ===
            'log_retention_days': 10,
            'error_retention_days': 10,
            'history_retention_days': 15,
        }
    
    def _get_hardcoded_price_rules(self) -> Dict[str, float]:
        """Hardcoded price rules"""
        return {
            'floor_rate': 1.5,
            'below_competitor': 1.0,
            'max_rate': 2.0,
        }
    
    def is_enabled(self, feature: str) -> bool:
        """
        Check if the feature is enabled
        
        Args:
            feature: Name feature (e.g. 'scraper_emmamason', 'enable_price_history')
        
        Returns:
            True if enabled
        """
        config = self.get_config()
        return config.get(feature, False)
    
    def get_value(self, key: str, default: Any = None) -> Any:
        """
        Get parameter value
        
        Args:
            key: Parameter name
            default: Default value if not found
        
        Returns:
            Parameter value
        """
        config = self.get_config()
        return config.get(key, default)
    
    def get_scraper_config(self, scraper_name: str) -> Dict[str, Any]:
        """
        Get configuration for a specific scraper
        
        Args:
            scraper_name: Name (emmamason, coleman, onestopbedrooms, afastores)
        
        Returns:
            Scraper config
        """
        config = self.get_config()
        
        scraper_config = {
            'enabled': config.get(f'scraper_{scraper_name}', True),
            'timeout_minutes': config.get('scraping_timeout_minutes', 45),
        }
        
        # Emma Mason specific
        if scraper_name == 'emmamason':
            scraper_config.update({
                'max_products': config.get('max_products_emmamason', 5000),
                'max_retries': config.get('emmamason_max_retries', 3),
            })
        else:
            scraper_config['max_products'] = config.get('max_products_per_competitor', 5000)
        
        return scraper_config
    
    def validate(self) -> List[str]:
        """
        Configuration validation
        
        Returns:
            List of errors (empty if OK)
        """
        errors = []
        config = self.get_config()
        
        # Checking numerical ranges
        validations = [
            ('max_products_emmamason', 100, 50000),
            ('max_products_per_competitor', 50, 50000),
            ('scraping_timeout_minutes', 10, 300),
            ('min_price_change_percent', 0, 300),
            ('max_price_change_percent', 1, 300),
            ('min_valid_price', 1, 1000),
            ('max_valid_price', 100, 100000),
            ('batch_size_sheets_update', 100, 1000),
            ('max_concurrent_requests', 1, 20),
            ('rate_limit_delay_seconds', 30, 300),
        ]
        
        for param, min_val, max_val in validations:
            value = config.get(param)
            if value is not None:
                if not (min_val <= value <= max_val):
                    errors.append(f"{param} must be between {min_val} and {max_val}, got {value}")
        
        # Logical checks
        if config.get('min_price_change_percent', 0) > config.get('max_price_change_percent', 100):
            errors.append("min_price_change_percent cannot be > max_price_change_percent")
        
        if config.get('min_valid_price', 0) > config.get('max_valid_price', 100000):
            errors.append("min_valid_price cannot be > max_valid_price")
        
        # Price rules
        rules = self.get_price_rules()
        if rules.get('floor_rate', 0) <= 0:
            errors.append("floor_rate must be > 0")
        
        if rules.get('max_rate', 0) <= 0:
            errors.append("max_rate must be > 0")
        
        if rules.get('floor_rate', 0) > rules.get('max_rate', 0):
            errors.append("floor_rate cannot be > max_rate")
        
        return errors
    
    def print_summary(self):
        """Display configuration summary"""
        config = self.get_config()
        rules = self.get_price_rules()
        
        self.logger.info("="*60)
        self.logger.info("CONFIGURATION SUMMARY")
        self.logger.info("="*60)
        
        # System
        self.logger.info("SYSTEM:")
        self.logger.info(f"  Run enabled:     {config.get('run_enabled')}")
        self.logger.info(f"  Test mode:       {config.get('test_mode')}")
        self.logger.info(f"  Dry run:         {config.get('dry_run')}")
        self.logger.info(f"  Log level:       {config.get('log_level')}")
        
        # Scrapers
        self.logger.info("")
        self.logger.info("SCRAPERS:")
        for scraper in ['emmamason', 'coleman', 'onestopbedrooms', 'afastores']:
            enabled = config.get(f'scraper_{scraper}', True)
            status = "[ENABLED]" if enabled else "[DISABLED]"
            self.logger.info(f"  {scraper:20s}: {status}")
        
        # Limits
        self.logger.info("")
        self.logger.info("LIMITS:")
        self.logger.info(f"  Emma Mason:      {config.get('max_products_emmamason')} products")
        self.logger.info(f"  Competitors:     {config.get('max_products_per_competitor')} products each")
        self.logger.info(f"  Timeout:         {config.get('scraping_timeout_minutes')} minutes")
        
        # Pricing
        self.logger.info("")
        self.logger.info("PRICING RULES:")
        self.logger.info(f"  Floor rate:      {rules.get('floor_rate')}")
        self.logger.info(f"  Below competitor: ${rules.get('below_competitor')}")
        self.logger.info(f"  Max rate:        {rules.get('max_rate')}")
        self.logger.info(f"  Min change:      {config.get('min_price_change_percent')}%")
        self.logger.info(f"  Max change:      {config.get('max_price_change_percent')}%")
        
        # Updates
        self.logger.info("")
        self.logger.info("UPDATES:")
        self.logger.info(f"  Price updates:   {'[OK]' if config.get('enable_price_updates') else '✗'}")
        self.logger.info(f"  Price history:   {'[OK]' if config.get('enable_price_history') else '✗'}")
        self.logger.info(f"  Competitors:     {'[OK]' if config.get('enable_competitors_sheet') else '✗'}")
        
        # Performance
        self.logger.info("")
        self.logger.info("PERFORMANCE:")
        self.logger.info(f"  Batch size:      {config.get('batch_size_sheets_update')}")
        self.logger.info(f"  Concurrent:      {config.get('max_concurrent_requests')}")
        
        # Notifications
        if config.get('telegram_enabled'):
            self.logger.info("")
            self.logger.info("NOTIFICATIONS:")
            errors_only = " (errors only)" if config.get('telegram_on_errors_only') else ""
            self.logger.info(f"  Telegram:        [ENABLED]{errors_only}")
        
        self.logger.info("="*60)
    
    def reload(self):
        """Reload configuration (if Google Sheets has changed)"""
        self._merged_config = None
        self._price_rules = None
        self.logger.info("Configuration reloaded")
