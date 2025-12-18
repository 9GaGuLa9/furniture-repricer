"""
Simple Logger Module для Furniture Repricer
"""

import logging
import sys
from pathlib import Path


def get_logger(name: str = "repricer") -> logging.Logger:
    """
    Отримати logger з певною назвою
    
    Args:
        name: Назва логгера
    
    Returns:
        Logger instance
    """
    logger = logging.getLogger(name)
    
    # Налаштувати тільки якщо ще не налаштовано
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        
        # Console handler
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(logging.INFO)
        
        # Formatter
        formatter = logging.Formatter(
            '%(asctime)s | %(name)-12s | %(levelname)-8s | %(message)s',
            datefmt='%H:%M:%S'
        )
        handler.setFormatter(formatter)
        
        logger.addHandler(handler)
    
    return logger


def setup_logging(config: dict = None) -> logging.Logger:
    """
    Налаштувати головний логgер
    
    Args:
        config: Конфігурація логування (опціонально)
    
    Returns:
        Logger instance
    """
    return get_logger("repricer")


class LogBlock:
    """Контекстний менеджер для логування блоків коду"""
    
    def __init__(self, name: str, logger: logging.Logger = None):
        self.name = name
        self.logger = logger or get_logger()
        self.start_time = None
    
    def __enter__(self):
        from datetime import datetime
        self.start_time = datetime.now()
        self.logger.info(f"Starting: {self.name}")
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        from datetime import datetime
        duration = (datetime.now() - self.start_time).total_seconds()
        
        if exc_type is None:
            self.logger.info(f"Completed: {self.name} (took {duration:.2f}s)")
        else:
            self.logger.error(f"Failed: {self.name} after {duration:.2f}s - {exc_val}")
        
        return False


if __name__ == "__main__":
    # Тестування
    logger = get_logger("test")
    logger.info("Info message")
    logger.warning("Warning message")
    logger.error("Error message")
    
    with LogBlock("Test operation", logger):
        logger.info("Doing some work...")
        import time
        time.sleep(0.5)
    
    print("✅ Logger test completed!")
