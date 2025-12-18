"""
Logging система для Furniture Repricer
Підтримує консоль та файли з ротацією
"""

import logging
import sys
from pathlib import Path
from datetime import datetime
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler
from typing import Optional

try:
    import colorlog
    COLORLOG_AVAILABLE = True
except ImportError:
    COLORLOG_AVAILABLE = False


class RepricerLogger:
    """Клас для управління логуванням"""
    
    def __init__(self, name: str = "repricer", config: Optional[dict] = None):
        """
        Ініціалізація логгера
        
        Args:
            name: Назва логгера
            config: Конфігурація логування
        """
        self.name = name
        self.config = config or {}
        self.logger = logging.getLogger(name)
        self._setup_logger()
    
    def _setup_logger(self):
        """Налаштувати логгер"""
        # Рівень логування
        level = self.config.get('level', 'INFO')
        self.logger.setLevel(getattr(logging, level))
        
        # Очистити існуючі хендлери
        self.logger.handlers = []
        
        # Налаштувати консоль
        if self.config.get('console', {}).get('enabled', True):
            self._setup_console_handler()
        
        # Налаштувати файли
        if self.config.get('files', {}).get('enabled', True):
            self._setup_file_handler()
    
    def _setup_console_handler(self):
        """Налаштувати консольний хендлер"""
        console_config = self.config.get('console', {})
        colorize = console_config.get('colorize', True)
        
        console_handler = logging.StreamHandler(sys.stdout)
        
        if colorize and COLORLOG_AVAILABLE:
            # Кольоровий формат
            formatter = colorlog.ColoredFormatter(
                '%(log_color)s%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S',
                log_colors={
                    'DEBUG': 'cyan',
                    'INFO': 'green',
                    'WARNING': 'yellow',
                    'ERROR': 'red',
                    'CRITICAL': 'red,bg_white',
                }
            )
        else:
            # Звичайний формат
            formatter = logging.Formatter(
                '%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
        
        console_handler.setFormatter(formatter)
        self.logger.addHandler(console_handler)
    
    def _setup_file_handler(self):
        """Налаштувати файловий хендлер"""
        files_config = self.config.get('files', {})
        
        # Директорія для логів
        log_dir = Path(files_config.get('directory', './logs'))
        log_dir.mkdir(parents=True, exist_ok=True)
        
        # Тип ротації
        rotation = files_config.get('rotation', 'daily')
        
        # Назва файлу
        log_file = log_dir / f"{self.name}.log"
        
        if rotation == 'daily':
            # Щоденна ротація
            handler = TimedRotatingFileHandler(
                log_file,
                when='midnight',
                interval=1,
                backupCount=files_config.get('retention_days', 30),
                encoding='utf-8'
            )
        elif rotation == 'size':
            # Ротація по розміру
            max_size = files_config.get('max_size_mb', 100) * 1024 * 1024
            handler = RotatingFileHandler(
                log_file,
                maxBytes=max_size,
                backupCount=5,
                encoding='utf-8'
            )
        else:
            # Звичайний файл
            handler = logging.FileHandler(log_file, encoding='utf-8')
        
        # Детальний формат для файлів
        if self.config.get('format') == 'json':
            # JSON формат (для майбутнього)
            formatter = logging.Formatter(
                '{"time":"%(asctime)s","level":"%(levelname)s","logger":"%(name)s","message":"%(message)s"}',
                datefmt='%Y-%m-%dT%H:%M:%S'
            )
        else:
            # Детальний текстовий формат
            formatter = logging.Formatter(
                '%(asctime)s | %(levelname)-8s | %(name)-20s | %(funcName)-20s | %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
        
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)
    
    def get_logger(self):
        """Отримати logger instance"""
        return self.logger


def setup_logging(config: Optional[dict] = None) -> logging.Logger:
    """
    Налаштувати головний логгер
    
    Args:
        config: Конфігурація логування
    
    Returns:
        Logger instance
    """
    logger_instance = RepricerLogger("repricer", config)
    return logger_instance.get_logger()


def get_logger(name: str = "repricer") -> logging.Logger:
    """
    Отримати логгер з певною назвою
    
    Args:
        name: Назва логгера
    
    Returns:
        Logger instance
    """
    return logging.getLogger(name)


# Декоратор для логування функцій
def log_function_call(func):
    """Декоратор для автоматичного логування виклику функцій"""
    def wrapper(*args, **kwargs):
        logger = get_logger()
        logger.debug(f"Calling {func.__name__} with args={args}, kwargs={kwargs}")
        try:
            result = func(*args, **kwargs)
            logger.debug(f"{func.__name__} completed successfully")
            return result
        except Exception as e:
            logger.error(f"{func.__name__} failed with error: {e}", exc_info=True)
            raise
    return wrapper


# Контекстний менеджер для логування блоків коду
class LogBlock:
    """Контекстний менеджер для логування блоків коду"""
    
    def __init__(self, name: str, logger: Optional[logging.Logger] = None):
        self.name = name
        self.logger = logger or get_logger()
        self.start_time = None
    
    def __enter__(self):
        self.start_time = datetime.now()
        self.logger.info(f"Starting: {self.name}")
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        duration = (datetime.now() - self.start_time).total_seconds()
        
        if exc_type is None:
            self.logger.info(f"Completed: {self.name} (took {duration:.2f}s)")
        else:
            self.logger.error(f"Failed: {self.name} after {duration:.2f}s - {exc_val}")
        
        return False  # Не придушувати виключення


if __name__ == "__main__":
    # Тестування
    config = {
        'level': 'DEBUG',
        'console': {'enabled': True, 'colorize': True},
        'files': {'enabled': True, 'directory': './logs', 'rotation': 'daily'}
    }
    
    logger = setup_logging(config)
    
    logger.debug("This is a debug message")
    logger.info("This is an info message")
    logger.warning("This is a warning message")
    logger.error("This is an error message")
    
    # Тест LogBlock
    with LogBlock("Test Operation", logger):
        logger.info("Doing some work...")
        import time
        time.sleep(1)
    
    print("Logging test completed!")
