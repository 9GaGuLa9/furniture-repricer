"""
Logger Module for Furniture Repricer
with log_level parameter support
"""

import logging
import sys
from pathlib import Path
from datetime import datetime, timedelta




def cleanup_old_logs(log_dir: str, retention_days: int = 10) -> int:
    """
    Delete log files older than retention_days
    
    Args:
        log_dir: Directory with log files
        retention_days: Number of days to keep logs (default: 10)
    
    Returns:
        Number of deleted files
    """
    try:
        log_path = Path(log_dir)
        
        if not log_path.exists():
            return 0
        
        deleted_count = 0
        deleted_files = []
        
        # Find all .log files
        for log_file in log_path.glob('*.log'):
            try:
                # Get file modification time
                file_mtime = datetime.fromtimestamp(log_file.stat().st_mtime)

                # Compare integer days to avoid microsecond precision issues.
                # retention_days=10 means: delete files OLDER THAN 10 days (age > 10).
                # A file exactly 10 days old is kept.
                file_age_days = (datetime.now() - file_mtime).days

                if file_age_days > retention_days:
                    log_file.unlink()
                    deleted_count += 1
                    deleted_files.append(f"{log_file.name} ({file_age_days} days old)")
            
            except Exception as e:
                print(f"[CLEANUP] Failed to delete {log_file.name}: {e}", file=sys.stderr)
                continue
        
        if deleted_count > 0:
            print(f"[CLEANUP] Deleted {deleted_count} old log files (older than {retention_days} days):")
            for file_info in deleted_files[:5]:  # Show first 5
                print(f"  - {file_info}")
            if len(deleted_files) > 5:
                print(f"  ... and {len(deleted_files) - 5} more")
        
        return deleted_count
    
    except Exception as e:
        print(f"[CLEANUP] Failed to cleanup old logs: {e}", file=sys.stderr)
        return 0


def get_logger(name: str = "repricer") -> logging.Logger:
    """
    Get a child logger under 'repricer' namespace.

    All handlers are on the parent 'repricer' logger (configured by setup_logging).
    Child loggers propagate messages up — no duplicate handlers.

    Args:
        name: Logger name (will become 'repricer.name')

    Returns:
        Logger instance
    """
    if name == "repricer":
        return logging.getLogger("repricer")
    return logging.getLogger(f"repricer.{name}")


# Scraper logger name fragments — used to apply scrap_log_level selectively.
# Any repricer.<name> where <name> starts with one of these prefixes is a scraper.
SCRAPER_LOGGER_PREFIXES: tuple = (
    "emmamason",
    "coleman",
    "afa",
    "onestopbedrooms",
)


def _is_scraper_logger(name: str) -> bool:
    """Return True if the logger name belongs to a scraper."""
    # name is like 'repricer.coleman' or 'repricer.emmamason_algolia'
    short = name.removeprefix("repricer.")
    return short.startswith(SCRAPER_LOGGER_PREFIXES)


def setup_logging(
    log_dir: str = 'logs',
    log_format: str = None,
    date_format: str = None,
    level: str = 'INFO',
    sys_level: str = None,
    scrap_level: str = None,
    retention_days: int = 10,
) -> logging.Logger:
    """
    Configure the main logger.

    Args:
        log_dir:     Directory for logs.
        log_format:  Logging format string.
        date_format: Date format string.
        level:       Fallback level used when sys_level / scrap_level are not
                     provided (kept for backwards-compatibility).
        sys_level:   Level for system modules (google_sheets, pricing, …).
        scrap_level: Level for scraper modules (emmamason, coleman, afa, …).
        retention_days: Days to keep log files.

    Returns:
        Root repricer logger instance.
    """
    """
    Configure the main logger
    Support for log_level parameter
    
    Args:
        log_dir: Directory for logs
        log_format: Logging format
        date_format: Date format
        level: Logging level (‘DEBUG’, ‘INFO’, ‘WARNING’, ‘ERROR’)
    
    Returns:
        Logger instance
    """
    # Resolve effective levels for each tier.
    # If the fine-grained params are absent, fall back to the generic `level`.
    def _to_numeric(lvl: str) -> int:
        return getattr(logging, lvl.upper(), logging.INFO)

    sys_numeric   = _to_numeric(sys_level   or level)
    scrap_numeric = _to_numeric(scrap_level  or level)

    # The root repricer logger must be at the *most permissive* level so
    # that child loggers at DEBUG can propagate messages up to the handlers.
    root_numeric  = min(sys_numeric, scrap_numeric)
    
    # Create the root application logger
    logger = logging.getLogger("repricer")
    logger.setLevel(root_numeric)
    logger.propagate = False  # Don't propagate to root — we handle everything here

    # Remove existing handlers if any
    logger.handlers.clear()
    
    # Format
    if not log_format:
        log_format = '%(asctime)s | %(name)-12s | %(levelname)-8s | %(message)s'
    if not date_format:
        date_format = '%H:%M:%S'
    
    formatter = logging.Formatter(log_format, datefmt=date_format)
    
    # Console handler with the specified level
    console_handler = logging.StreamHandler(sys.stdout)
    # Console shows the less-verbose of the two tiers (keeps output readable).
    console_handler.setLevel(max(sys_numeric, scrap_numeric))
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # File handler (always DEBUG)
    try:
        log_path = Path(log_dir)
        log_path.mkdir(exist_ok=True)
        
        log_file = log_path / f"repricer_{datetime.now().strftime('%Y-%m-%d')}.log"
        
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(root_numeric)  # File matches the most permissive tier
        
        file_formatter = logging.Formatter(
            '%(asctime)s | %(name)-15s | %(levelname)-8s | %(funcName)-20s | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)
        
        logger.debug(f"Logging to file: {log_file}")
        logger.debug(
            f"Log levels — sys: {sys_level or level}, "
            f"scrapers: {scrap_level or level}"
        )
        
        # Cleanup old logs
        deleted = cleanup_old_logs(log_dir, retention_days)
        if deleted > 0:
            logger.info(f"[CLEANUP] Cleaned up {deleted} old log files (retention: {retention_days} days)")
    except Exception as e:
        print(f"Warning: Could not setup file logging: {e}", file=sys.stderr)
    
    return logger




def apply_log_levels(
    sys_level: str = None,
    scrap_level: str = None,
) -> None:
    """
    Apply new log levels to all repricer logger handlers at runtime.

    Safe to call from any thread — Python logging uses internal locks.
    Typically called after Google Sheets config is loaded so that runtime
    overrides (sys_log_level / scrap_log_level) are honoured without a restart.

    Args:
        sys_level:   New level for system modules, e.g. 'INFO'.
        scrap_level: New level for scraper modules, e.g. 'DEBUG'.
    """
    if not sys_level and not scrap_level:
        return

    def _to_numeric(lvl: str) -> int:
        return getattr(logging, lvl.upper(), logging.INFO)

    root = logging.getLogger("repricer")

    sys_numeric   = _to_numeric(sys_level)   if sys_level   else None
    scrap_numeric = _to_numeric(scrap_level) if scrap_level else None

    # Collect all active child loggers in the repricer namespace
    manager = root.manager
    child_loggers = [
        logging.getLogger(name)
        for name in manager.loggerDict
        if name.startswith("repricer.")
    ]

    for child in child_loggers:
        if _is_scraper_logger(child.name):
            if scrap_numeric is not None:
                child.setLevel(scrap_numeric)
        else:
            if sys_numeric is not None:
                child.setLevel(sys_numeric)

    # Root must be at least as permissive as the most verbose child
    active = [
        v for v in (sys_numeric, scrap_numeric) if v is not None
    ]
    if active:
        root.setLevel(min(active))
        for handler in root.handlers:
            handler.setLevel(min(active))

    root.debug(
        f"Log levels updated — sys: {sys_level}, scrapers: {scrap_level}"
    )

class LogBlock:
    """Context manager for logging code blocks"""
    
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
    # Show where the file is located
    log_dir = Path(__file__).parent.parent.parent / "logs"
    log_file = log_dir / f"repricer_{datetime.now().strftime('%Y-%m-%d')}.log"
    
    if log_file.exists():
        print(f"\n[NOTE] Log file: {log_file}")
        print("\nLast 10 lines:")
        print("-" * 60)
        with open(log_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            for line in lines[-10:]:
                print(line.rstrip())
