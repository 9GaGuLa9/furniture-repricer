"""
Configuration Manager для Furniture Repricer
Читає налаштування з config.yaml та .env
"""

import os
import yaml
from pathlib import Path
from dotenv import load_dotenv
from typing import Any, Dict, Optional
import logging

# Завантажити .env файл
load_dotenv()

# Базова директорія проекту
BASE_DIR = Path(__file__).parent.parent.resolve()

class Config:
    """Клас для управління конфігурацією"""
    
    def __init__(self, config_path: Optional[str] = None):
        """
        Ініціалізація конфігурації
        
        Args:
            config_path: Шлях до config.yaml (опціонально)
        """
        if config_path is None:
            config_path = BASE_DIR / "config.yaml"
        
        self.config_path = Path(config_path)
        self.config = self._load_config()
        self._resolve_env_vars()
    
    def _load_config(self) -> Dict[str, Any]:
        """Завантажити конфігурацію з YAML файлу"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            return config or {}
        except FileNotFoundError:
            logging.warning(f"Config file not found: {self.config_path}")
            return {}
        except yaml.YAMLError as e:
            logging.error(f"Error parsing config.yaml: {e}")
            return {}
    
    def _resolve_env_vars(self):
        """Замінити ${VAR} на значення з environment variables"""
        self._recursive_resolve(self.config)
    
    def _recursive_resolve(self, obj):
        """Рекурсивно замінити env vars у словнику"""
        if isinstance(obj, dict):
            for key, value in obj.items():
                if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
                    env_var = value[2:-1]
                    obj[key] = os.getenv(env_var, "")
                elif isinstance(value, (dict, list)):
                    self._recursive_resolve(value)
        elif isinstance(obj, list):
            for item in obj:
                self._recursive_resolve(item)
    
    def get(self, key_path: str, default: Any = None) -> Any:
        """
        Отримати значення з конфігурації за шляхом
        
        Args:
            key_path: Шлях до значення (напр. "google_sheets.main_sheet.id")
            default: Значення за замовчуванням
        
        Returns:
            Значення або default
        """
        keys = key_path.split('.')
        value = self.config
        
        for key in keys:
            if isinstance(value, dict):
                value = value.get(key)
                if value is None:
                    return default
            else:
                return default
        
        return value
    
    def set(self, key_path: str, value: Any):
        """
        Встановити значення в конфігурації
        
        Args:
            key_path: Шлях до значення
            value: Нове значення
        """
        keys = key_path.split('.')
        config = self.config
        
        for key in keys[:-1]:
            if key not in config:
                config[key] = {}
            config = config[key]
        
        config[keys[-1]] = value
    
    def save(self):
        """Зберегти конфігурацію назад у файл"""
        try:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                yaml.dump(self.config, f, default_flow_style=False, allow_unicode=True)
            return True
        except Exception as e:
            logging.error(f"Error saving config: {e}")
            return False
    
    def reload(self):
        """Перезавантажити конфігурацію з файлу"""
        self.config = self._load_config()
        self._resolve_env_vars()
    
    # Швидкий доступ до основних налаштувань
    
    @property
    def google_credentials_path(self) -> Path:
        """Шлях до Google Service Account credentials"""
        path = self.get('google_sheets.credentials_path', './credentials/service_account.json')
        return BASE_DIR / path
    
    @property
    def main_sheet_id(self) -> str:
        """ID основної таблиці"""
        return self.get('google_sheets.main_sheet.id', '')
    
    @property
    def main_sheet_name(self) -> str:
        """Назва основного аркушу"""
        return self.get('google_sheets.main_sheet.name', 'Data')
    
    @property
    def competitors_sheet_id(self) -> str:
        """ID таблиці конкурентів"""
        return self.get('google_sheets.competitors_sheet.id', '')
    
    @property
    def telegram_enabled(self) -> bool:
        """Чи увімкнені Telegram сповіщення"""
        return self.get('telegram.enabled', False)
    
    @property
    def telegram_token(self) -> str:
        """Telegram Bot Token"""
        return os.getenv('TELEGRAM_BOT_TOKEN', '')
    
    @property
    def telegram_chat_id(self) -> str:
        """Telegram Chat ID"""
        return os.getenv('TELEGRAM_CHAT_ID', '')
    
    @property
    def admin_panel_enabled(self) -> bool:
        """Чи увімкнена адмін-панель"""
        return self.get('admin_panel.enabled', False)
    
    @property
    def admin_panel_port(self) -> int:
        """Порт адмін-панелі"""
        return self.get('admin_panel.port', 5000)
    
    @property
    def log_level(self) -> str:
        """Рівень логування"""
        return self.get('logging.level', 'INFO')
    
    @property
    def test_mode(self) -> bool:
        """Чи увімкнений тестовий режим"""
        return self.get('development.test_mode', False)
    
    @property
    def test_limit(self) -> int:
        """Ліміт товарів у тестовому режимі"""
        return self.get('development.test_limit', 10)
    
    def is_scraper_enabled(self, scraper_name: str) -> bool:
        """Перевірити чи увімкнений скрапер"""
        return self.get(f'scrapers.{scraper_name}.enabled', False)
    
    def get_scraper_config(self, scraper_name: str) -> Dict[str, Any]:
        """Отримати конфігурацію скрапера"""
        return self.get(f'scrapers.{scraper_name}', {})
    
    def get_pricing_coefficients(self) -> Dict[str, float]:
        """Отримати коефіцієнти ціноутворення"""
        return self.get('pricing.coefficients', {
            'floor': 1.5,
            'below_lowest': 1.0,
            'max': 2.0
        })
    
    def __repr__(self) -> str:
        return f"Config(path={self.config_path})"


# Глобальний екземпляр конфігурації
config = Config()


# Допоміжні функції
def get_config() -> Config:
    """Отримати глобальний екземпляр конфігурації"""
    return config


def reload_config():
    """Перезавантажити конфігурацію"""
    global config
    config.reload()


if __name__ == "__main__":
    # Тестування
    print("Testing Config...")
    print(f"Main Sheet ID: {config.main_sheet_id}")
    print(f"Telegram enabled: {config.telegram_enabled}")
    print(f"Credentials path: {config.google_credentials_path}")
    print(f"Pricing coefficients: {config.get_pricing_coefficients()}")
    print(f"Coleman enabled: {config.is_scraper_enabled('coleman')}")
