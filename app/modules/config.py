"""
Configuration Manager для Furniture Repricer
"""

import os
import yaml
from pathlib import Path
from dotenv import load_dotenv
from typing import Any, Dict, Optional

load_dotenv()

BASE_DIR = Path(__file__).parent.parent.parent.resolve()

class Config:
    """Клас для управління конфігурацією"""
    
    def __init__(self, config_path: Optional[str] = None):
        if config_path is None:
            config_path = BASE_DIR / "config.yaml"
        
        self.config_path = Path(config_path)
        self.config = self._load_config()
        self._resolve_env_vars()
    
    def _load_config(self) -> Dict[str, Any]:
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            return config or {}
        except FileNotFoundError:
            return {}
        except yaml.YAMLError:
            return {}
    
    def _resolve_env_vars(self):
        self._recursive_resolve(self.config)
    
    def _recursive_resolve(self, obj):
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
    
    @property
    def google_credentials_path(self) -> Path:
        path = self.get('google_sheets.credentials_file', './credentials/service_account.json')
        return BASE_DIR / path
    
    @property
    def main_sheet_id(self) -> str:
        return self.get('google_sheets.main_sheet.id', '')
    
    @property
    def main_sheet_name(self) -> str:
        return self.get('google_sheets.main_sheet.name', 'Data')
    
    @property
    def telegram_enabled(self) -> bool:
        return self.get('telegram.enabled', False)
    
    @property
    def telegram_token(self) -> str:
        return os.getenv('TELEGRAM_BOT_TOKEN', '')
    
    @property
    def telegram_chat_id(self) -> str:
        return os.getenv('TELEGRAM_CHAT_ID', '')
    
    @property
    def test_mode(self) -> bool:
        return self.get('development.test_mode', False)
    
    @property
    def test_limit(self) -> int:
        return self.get('development.test_limit', 10)
    
    def is_scraper_enabled(self, scraper_name: str) -> bool:
        return self.get(f'scrapers.{scraper_name}.enabled', False)
    
    def get_scraper_config(self, scraper_name: str) -> Dict[str, Any]:
        return self.get(f'scrapers.{scraper_name}', {})
    
    def get_pricing_coefficients(self) -> Dict[str, float]:
        return self.get('pricing.coefficients', {
            'floor': 1.5,
            'below_lowest': 1.0,
            'max': 2.0
        })

config = Config()

def get_config() -> Config:
    return config
