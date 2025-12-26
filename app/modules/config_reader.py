"""
Модуль для читання конфігурації з Google Sheets
Читає Config та Price_rules sheets для керування репрайсером
"""

from typing import Dict, Any, List, Optional
from .logger import get_logger

logger = get_logger("config_reader")


class GoogleSheetsConfigReader:
    """Читання конфігурації з Google Sheets"""
    
    def __init__(self, sheets_client, main_sheet_id: str):
        """
        Args:
            sheets_client: GoogleSheetsClient instance
            main_sheet_id: ID головної таблиці
        """
        self.client = sheets_client
        self.sheet_id = main_sheet_id
        self.logger = logger
    
    def read_config(self) -> Dict[str, Any]:
        """
        Читання конфігурації з аркушу "Config"
        
        Структура:
        | Parameter | Value | Description |
        |-----------|-------|-------------|
        | run_enabled | TRUE | ... |
        
        Returns:
            Словник з параметрами конфігурації
        """
        try:
            self.logger.info("Reading Config from Google Sheets...")
            
            # Спробувати знайти Config sheet
            try:
                data = self.client.read_all_data(self.sheet_id, "Config")
            except Exception:
                self.logger.warning("Config sheet not found, using defaults")
                return self._get_default_config()
            
            if not data or len(data) < 2:
                self.logger.warning("Config sheet is empty, using defaults")
                return self._get_default_config()
            
            # Парсинг даних
            config = {}
            
            # Пропустити header (рядок 1)
            for row in data[1:]:
                if len(row) < 2:
                    continue
                
                param_name = row[0].strip()
                param_value = row[1].strip() if len(row) > 1 else ""
                
                if not param_name or param_name.startswith("==="):
                    continue  # Пропустити порожні рядки та роздільники
                
                # Конвертувати значення
                config[param_name] = self._parse_value(param_value)
            
            # Логування
            self.logger.info(f"✓ Loaded {len(config)} parameters from Config sheet")
            
            # Показати критичні параметри
            critical_params = [
                'run_enabled',
                'scraper_emmamason',
                'enable_price_updates',
                'enable_price_history'
            ]
            
            for param in critical_params:
                if param in config:
                    self.logger.info(f"  {param}: {config[param]}")
            
            # Merge з defaults (якщо якихось параметрів немає)
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
        Читання правил ціноутворення з аркушу "Price_rules"
        
        Структура:
        | Parameter                  | Value |
        |----------------------------|-------|
        | Floor (rate)               | 1.5   |
        | Below Lowest Competitor($) | 1     |
        | Max (rate)                 | 2     |
        
        Returns:
            Словник з правилами ціноутворення
        """
        try:
            self.logger.info("Reading Price_rules from Google Sheets...")
            
            # Спробувати знайти Price_rules sheet
            try:
                data = self.client.read_all_data(self.sheet_id, "Price_rules")
            except Exception:
                self.logger.warning("Price_rules sheet not found, using defaults")
                return self._get_default_price_rules()
            
            if not data or len(data) < 2:
                self.logger.warning("Price_rules sheet is empty, using defaults")
                return self._get_default_price_rules()
            
            # Парсинг даних
            rules = {}
            
            # Пропустити header (рядок 1)
            for row in data[1:]:
                if len(row) < 2:
                    continue
                
                param_name = row[0].strip()
                param_value = row[1].strip() if len(row) > 1 else ""
                
                if not param_name:
                    continue
                
                # Нормалізувати назви параметрів
                # "Floor (rate)" -> "floor_rate"
                # "Below Lowest Competitor ($)" -> "below_competitor"
                # "Max (rate)" -> "max_rate"
                
                if "floor" in param_name.lower():
                    rules['floor_rate'] = self._parse_float(param_value, 1.5)
                
                elif "below" in param_name.lower() and "competitor" in param_name.lower():
                    rules['below_competitor'] = self._parse_float(param_value, 1.0)
                
                elif "max" in param_name.lower():
                    rules['max_rate'] = self._parse_float(param_value, 2.0)
            
            # Логування
            self.logger.info(f"✓ Loaded price rules:")
            self.logger.info(f"  Floor rate: {rules.get('floor_rate', 1.5)}")
            self.logger.info(f"  Below competitor: ${rules.get('below_competitor', 1.0)}")
            self.logger.info(f"  Max rate: {rules.get('max_rate', 2.0)}")
            
            # Merge з defaults
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
        Конвертувати string значення в відповідний тип
        
        Args:
            value: String значення
        
        Returns:
            Конвертоване значення (bool, int, float, або string)
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
            # Спробувати int
            if '.' not in value:
                return int(value)
            # Спробувати float
            return float(value)
        except ValueError:
            pass
        
        # String
        return value
    
    def _parse_float(self, value: str, default: float = 0.0) -> float:
        """
        Конвертувати в float з default значенням
        
        Args:
            value: String значення
            default: Default якщо конвертація не вдалась
        
        Returns:
            Float значення
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
        Default конфігурація якщо Config sheet не знайдено
        
        Returns:
            Словник з default параметрами
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
            'max_products_emmamason': 5000,
            'max_products_per_competitor': 2000,
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
        }
    
    def _get_default_price_rules(self) -> Dict[str, float]:
        """
        Default правила ціноутворення
        
        Returns:
            Словник з default rules
        """
        return {
            'floor_rate': 1.5,        # Мінімальна ціна = Our Cost * 1.5
            'below_competitor': 1.0,   # На $1 нижче конкурента
            'max_rate': 2.0,          # Максимальна ціна = Our Cost * 2.0
        }
    
    def is_scraper_enabled(self, scraper_name: str) -> bool:
        """
        Перевірити чи увімкнений scraper
        
        Args:
            scraper_name: Назва scraper (emmamason, coleman, onestopbedrooms, afastores)
        
        Returns:
            True якщо увімкнений
        """
        config = self.read_config()
        param_name = f'scraper_{scraper_name}'
        return config.get(param_name, True)
    
    def get_scraper_config(self, scraper_name: str) -> Dict[str, Any]:
        """
        Отримати конфігурацію для конкретного scraper
        
        Args:
            scraper_name: Назва scraper
        
        Returns:
            Словник з параметрами для scraper
        """
        config = self.read_config()
        
        scraper_config = {
            'enabled': config.get(f'scraper_{scraper_name}', True),
            'delay': config.get('delay_between_requests', 3),
            'max_products': config.get('max_products_per_competitor', 2000),
            'timeout_minutes': config.get('scraping_timeout_minutes', 45),
        }
        
        # Emma Mason specific
        if scraper_name == 'emmamason':
            scraper_config.update({
                'max_products': config.get('max_products_emmamason', 5000),
                'target_brands': config.get('emmamason_target_brands', 'ALL'),
                'country_code': config.get('emmamason_country_code', 'US'),
                'max_retries': config.get('emmamason_max_retries', 3),
            })
        
        return scraper_config
    
    def validate_config(self) -> List[str]:
        """
        Валідація конфігурації
        
        Returns:
            Список помилок (порожній якщо все OK)
        """
        errors = []
        
        try:
            config = self.read_config()
            
            # Перевірка обов'язкових параметрів
            required_params = [
                'run_enabled',
                'enable_price_updates',
                'enable_price_history',
            ]
            
            for param in required_params:
                if param not in config:
                    errors.append(f"Missing required parameter: {param}")
            
            # Перевірка діапазонів
            if config.get('delay_between_requests', 0) < 0:
                errors.append("delay_between_requests must be >= 0")
            
            if config.get('min_price_change_percent', 0) < 0:
                errors.append("min_price_change_percent must be >= 0")
            
            if config.get('max_price_change_percent', 0) <= 0:
                errors.append("max_price_change_percent must be > 0")
            
            # Перевірка Price rules
            rules = self.read_price_rules()
            
            if rules.get('floor_rate', 0) <= 0:
                errors.append("floor_rate must be > 0")
            
            if rules.get('max_rate', 0) <= 0:
                errors.append("max_rate must be > 0")
            
            if rules.get('floor_rate', 0) > rules.get('max_rate', 0):
                errors.append("floor_rate cannot be greater than max_rate")
            
        except Exception as e:
            errors.append(f"Config validation error: {e}")
        
        return errors
    
    def print_config_summary(self):
        """Вивести summary конфігурації в лог"""
        try:
            config = self.read_config()
            rules = self.read_price_rules()
            
            self.logger.info("="*60)
            self.logger.info("CONFIGURATION SUMMARY:")
            self.logger.info("="*60)
            
            self.logger.info("SCRAPERS:")
            for scraper in ['emmamason', 'coleman', 'onestopbedrooms', 'afastores']:
                enabled = config.get(f'scraper_{scraper}', True)
                status = "✓ ENABLED" if enabled else "✗ DISABLED"
                self.logger.info(f"  {scraper:20s}: {status}")
            
            self.logger.info("")
            self.logger.info("PRICING RULES:")
            self.logger.info(f"  Floor rate:        {rules.get('floor_rate', 1.5)}")
            self.logger.info(f"  Below competitor:  ${rules.get('below_competitor', 1.0)}")
            self.logger.info(f"  Max rate:          {rules.get('max_rate', 2.0)}")
            
            self.logger.info("")
            self.logger.info("UPDATES:")
            self.logger.info(f"  Price updates:     {'✓' if config.get('enable_price_updates') else '✗'}")
            self.logger.info(f"  Price history:     {'✓' if config.get('enable_price_history') else '✗'}")
            self.logger.info(f"  Competitors sheet: {'✓' if config.get('enable_competitors_sheet') else '✗'}")
            
            self.logger.info("="*60)
            
        except Exception as e:
            self.logger.error(f"Failed to print config summary: {e}")
