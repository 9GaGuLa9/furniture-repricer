#!/usr/bin/env python3
"""
Scheduler Daemon for Furniture Repricer
Entry point for running scheduler as background service
"""

import sys
import signal
from pathlib import Path
import logging
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from app.modules.scheduler import create_scheduler_from_config
from app.modules.config_manager import ConfigManager
from app.modules.config_reader import GoogleSheetsConfigReader
from app.modules.google_sheets import GoogleSheetsClient
import yaml


# Global scheduler instance for signal handling
scheduler_instance = None
# Global logger for signal handling
daemon_logger = None


def signal_handler(signum, frame):
    """Handle graceful shutdown on SIGTERM/SIGINT"""
    global scheduler_instance, daemon_logger
    
    # Use daemon_logger if available, otherwise print
    if daemon_logger:
        daemon_logger.info(f"\nReceived signal {signum}, shutting down gracefully...")
    else:
        print(f"\nReceived signal {signum}, shutting down gracefully...")
    
    if scheduler_instance:
        scheduler_instance.stop()
    
    sys.exit(0)


def setup_logging():
    """Setup logging for daemon"""
    global daemon_logger
    
    # Create logs directory
    log_dir = project_root / "logs"
    log_dir.mkdir(exist_ok=True)
    
    # Log file with date
    log_file = log_dir / f"scheduler_{datetime.now().strftime('%Y-%m-%d')}.log"
    
    # Setup logging with UTF-8 encoding and error handling for emoji
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s | %(name)-15s | %(levelname)-8s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    # Configure StreamHandler to handle emoji gracefully on Windows
    for handler in logging.root.handlers:
        if isinstance(handler, logging.StreamHandler):
            # Use 'replace' error handling to avoid UnicodeEncodeError
            if hasattr(handler.stream, 'reconfigure'):
                try:
                    handler.stream.reconfigure(encoding='utf-8', errors='replace')
                except Exception:
                    pass
    
    daemon_logger = logging.getLogger("scheduler_daemon")
    return daemon_logger


def load_config(config_path: str = "config.yaml"):
    """
    Load configuration (YAML + Google Sheets)
    
    Args:
        config_path: Path to config.yaml
    
    Returns:
        Merged config dictionary
    """
    logger = logging.getLogger("scheduler_daemon")
    
    logger.info("Loading configuration...")
    
    try:
        # 1. Load YAML
        with open(config_path, 'r', encoding='utf-8') as f:
            base_config = yaml.safe_load(f)
        
        # 2. Initialize Google Sheets
        creds_file = base_config['google_sheets']['credentials_file']
        sheets_client = GoogleSheetsClient(creds_file)
        
        # 3. Config reader
        config_reader = GoogleSheetsConfigReader(
            sheets_client,
            base_config['main_sheet']['id']
        )
        
        # 4. ConfigManager with merge
        config_manager = ConfigManager(
            yaml_path=config_path,
            sheets_reader=config_reader
        )
        
        # 5. Get merged config
        config = config_manager.get_config()
        
        logger.info("Configuration loaded (YAML + Google Sheets)")
        
        return config
    
    except Exception as e:
        logger.error(f"Failed to load config: {e}", exc_info=True)
        logger.warning("Using basic YAML config only")
        
        # Fallback to simple YAML
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
        except Exception as e2:
            logger.error(f"Failed to load YAML: {e2}")
            sys.exit(1)


def main():
    """Main entry point"""
    global scheduler_instance, daemon_logger
    
    # Setup logging
    daemon_logger = setup_logging()
    
    daemon_logger.info("="*60)
    daemon_logger.info("FURNITURE REPRICER SCHEDULER DAEMON")
    daemon_logger.info("="*60)
    
    # Setup signal handlers for graceful shutdown
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    
    try:
        # Load config
        config = load_config()
        
        # Check if scheduler enabled
        if not config.get('schedule_enabled', False):
            daemon_logger.error("Scheduler is DISABLED in config!")
            daemon_logger.error("Set schedule_enabled = TRUE in Config sheet or config.yaml")
            sys.exit(1)
        
        # Create scheduler
        scheduler_instance = create_scheduler_from_config(config)
        
        if not scheduler_instance:
            daemon_logger.error("Failed to create scheduler!")
            sys.exit(1)
        
        # Run forever
        daemon_logger.info("\n" + "="*60)
        daemon_logger.info("Starting scheduler daemon...")
        daemon_logger.info("="*60 + "\n")
        
        scheduler_instance.run_forever()
    
    except KeyboardInterrupt:
        daemon_logger.info("\nScheduler stopped by user (Ctrl+C)")
    
    except Exception as e:
        daemon_logger.error(f"Scheduler daemon failed: {e}", exc_info=True)
        sys.exit(1)
    
    finally:
        daemon_logger.info("Scheduler daemon shutdown complete")


if __name__ == "__main__":
    main()
