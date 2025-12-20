"""
Simple Logger Module для Furniture Repricer
WITH FILE LOGGING! ✅
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
        logger.setLevel(logging.INFO)
        
        # Formatter (один для всіх handlers)
        formatter = logging.Formatter(
            '%(asctime)s | %(name)-12s | %(levelname)-8s | %(message)s',
            datefmt='%H:%M:%S'
        )
        
        # ═══════════════════════════════════════════════════════════════
        # 1. Console handler (як було)
        # ═══════════════════════════════════════════════════════════════
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
        
        # ═══════════════════════════════════════════════════════════════
        # 2. File handler (НОВИЙ!) ✅
        # ═══════════════════════════════════════════════════════════════
        if log_to_file:
            try:
                # Створити директорію logs/
                log_dir = Path(__file__).parent.parent.parent / "logs"
                log_dir.mkdir(exist_ok=True)
                
                # Файл з датою: logs/repricer_2024-12-19.log
                log_file = log_dir / f"repricer_{datetime.now().strftime('%Y-%m-%d')}.log"
                
                file_handler = logging.FileHandler(log_file, encoding='utf-8')
                file_handler.setLevel(logging.DEBUG)  # В файл пишемо все (включно DEBUG)
                
                # Детальніший formatter для файлу
                file_formatter = logging.Formatter(
                    '%(asctime)s | %(name)-15s | %(levelname)-8s | %(funcName)-20s | %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S'
                )
                file_handler.setFormatter(file_formatter)
                logger.addHandler(file_handler)
                
                # Перший лог - інформація про файл
                logger.debug(f"Logging to file: {log_file}")
            except Exception as e:
                # Якщо не вдалось створити file handler - продовжуємо з console
                print(f"Warning: Could not setup file logging: {e}", file=sys.stderr)
    
    return logger


def setup_logging(config: dict = None) -> logging.Logger:
    """
    Налаштувати головний логgер
    
    Args:
        config: Конфігурація логування (опціонально)
    
    Returns:
        Logger instance
    """
    log_to_file = True
    if config:
        log_to_file = config.get('files', {}).get('enabled', True)
    
    return get_logger("repricer", log_to_file=log_to_file)


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
    print("Testing logger with file output...")
    print()
    
    logger = get_logger("test")
    logger.info("Info message - console AND file")
    logger.warning("Warning message")
    logger.error("Error message")
    logger.debug("Debug message - ONLY in file")
    
    with LogBlock("Test operation", logger):
        logger.info("Doing some work...")
        import time
        time.sleep(0.5)
    
    print()
    print("✅ Logger test completed!")
    print()
    
    # Показати де файл
    log_dir = Path(__file__).parent.parent.parent / "logs"
    log_file = log_dir / f"repricer_{datetime.now().strftime('%Y-%m-%d')}.log"
    
    if log_file.exists():
        print(f"📝 Log file created: {log_file}")
        print()
        print("Last 10 lines:")
        print("-" * 60)
        with open(log_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            for line in lines[-10:]:
                print(line.rstrip())
    else:
        print(f"❌ Log file not found: {log_file}")
