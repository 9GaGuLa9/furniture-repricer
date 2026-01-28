"""
Logger Module для Furniture Repricer
FIXED VERSION v2.0 - з підтримкою log_level parameter
"""

import logging
import sys
from pathlib import Path
from datetime import datetime


def get_logger(name: str = "repricer", log_to_file: bool = True) -> logging.Logger:
    """
    Отримати logger з певною назвою
    
    Args:
        name: Назва логгера
        log_to_file: Чи писати в файл (default: True)
    
    Returns:
        Logger instance
    """
    logger = logging.getLogger(name)
    
    # Налаштувати тільки якщо ще не налаштовано
    if not logger.handlers:
        logger.setLevel(logging.DEBUG)  # Logger сам приймає все
        
        # Formatter (один для всіх handlers)
        formatter = logging.Formatter(
            '%(asctime)s | %(name)-12s | %(levelname)-8s | %(message)s',
            datefmt='%H:%M:%S'
        )
        
        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)  # За замовчуванням INFO
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
        
        # File handler
        if log_to_file:
            try:
                log_dir = Path(__file__).parent.parent.parent / "logs"
                log_dir.mkdir(exist_ok=True)
                
                log_file = log_dir / f"repricer_{datetime.now().strftime('%Y-%m-%d')}.log"
                
                file_handler = logging.FileHandler(log_file, encoding='utf-8')
                file_handler.setLevel(logging.DEBUG)  # В файл пишемо все
                
                file_formatter = logging.Formatter(
                    '%(asctime)s | %(name)-15s | %(levelname)-8s | %(funcName)-20s | %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S'
                )
                file_handler.setFormatter(file_formatter)
                logger.addHandler(file_handler)
                
                logger.debug(f"Logging to file: {log_file}")
            except Exception as e:
                print(f"Warning: Could not setup file logging: {e}", file=sys.stderr)
    
    return logger


def setup_logging(
    log_dir: str = 'logs',
    log_format: str = None,
    date_format: str = None,
    level: str = 'INFO'  # ✅ НОВИЙ ПАРАМЕТР!
) -> logging.Logger:
    """
    Налаштувати головний logger
    
    ✅ FIXED v2.0: Підтримка log_level parameter!
    
    Args:
        log_dir: Директорія для логів
        log_format: Формат логування
        date_format: Формат дати
        level: Рівень логування ('DEBUG', 'INFO', 'WARNING', 'ERROR')
    
    Returns:
        Logger instance
    """
    # Конвертувати string level в logging constant
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    
    # Створити logger
    logger = logging.getLogger("repricer")
    logger.setLevel(logging.DEBUG)  # Logger сам приймає все
    
    # Видалити існуючі handlers якщо є
    logger.handlers.clear()
    
    # Формат
    if not log_format:
        log_format = '%(asctime)s | %(name)-12s | %(levelname)-8s | %(message)s'
    if not date_format:
        date_format = '%H:%M:%S'
    
    formatter = logging.Formatter(log_format, datefmt=date_format)
    
    # ═══════════════════════════════════════════════════════════════
    # Console handler з вказаним level
    # ═══════════════════════════════════════════════════════════════
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(numeric_level)  # ✅ Використати parameter!
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # ═══════════════════════════════════════════════════════════════
    # File handler (завжди DEBUG)
    # ═══════════════════════════════════════════════════════════════
    try:
        log_path = Path(log_dir)
        log_path.mkdir(exist_ok=True)
        
        log_file = log_path / f"repricer_{datetime.now().strftime('%Y-%m-%d')}.log"
        
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)  # Файл завжди детальний
        
        file_formatter = logging.Formatter(
            '%(asctime)s | %(name)-15s | %(levelname)-8s | %(funcName)-20s | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)
        
        logger.debug(f"Logging to file: {log_file}")
        logger.debug(f"Console log level: {level}")
    except Exception as e:
        print(f"Warning: Could not setup file logging: {e}", file=sys.stderr)
    
    return logger


class LogBlock:
    """Контекстний менеджер для логування блоків коду"""
    
    def __init__(self, name: str, logger: logging.Logger = None):
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
        
        return False


if __name__ == "__main__":
    # Показати де файл
    log_dir = Path(__file__).parent.parent.parent / "logs"
    log_file = log_dir / f"repricer_{datetime.now().strftime('%Y-%m-%d')}.log"
    
    if log_file.exists():
        print(f"\n📝 Log file: {log_file}")
        print("\nLast 10 lines:")
        print("-" * 60)
        with open(log_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            for line in lines[-10:]:
                print(line.rstrip())
