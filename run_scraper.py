"""
Universal Scraper Runner
Запуск будь-якого scraper через command line
"""

import sys
import argparse
from pathlib import Path
from datetime import datetime
import json

# Додати root до path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from app.modules import get_config, get_logger
import logging

# Налаштування логування
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(message)s',
    datefmt='%H:%M:%S'
)

# Scrapers
from app.scrapers.emmamason import scrape_emmamason
from app.scrapers.onestopbedrooms import scrape_onestopbedrooms
from app.scrapers.coleman import scrape_coleman
from app.scrapers.afa import scrape_afa

# ============================================================
# SCRAPER DEFINITIONS
# ============================================================

SCRAPERS = {
    'emma': {
        'name': 'Emma Mason',
        'function': scrape_emmamason,
        'config_key': 'emmamason',
        'time': '1-2 minutes',
        'products': '~10 (test)',
        'needs_urls': True,
        'test_urls': [
            "https://emmamason.com/aico-villa-valencia-dresser-in-chestnut-72050-55.html",
            "https://emmamason.com/caracole-furniture-fontainebleau-center-side-chair-set-of-2-in-champagne-mist-c062-419-281.html",
        ]
    },
    'onestop': {
        'name': '1StopBedrooms',
        'function': scrape_onestopbedrooms,
        'config_key': 'onestopbedrooms',
        'time': '30-40 minutes',
        'products': '~2,000',
        'warning': 'Disable VPN before running!'
    },
    'coleman': {
        'name': 'Coleman Furniture',
        'function': scrape_coleman,
        'config_key': 'coleman',
        'time': '5-6 hours',
        'products': '~60,000-70,000',
        'warning': 'This takes VERY LONG! Run overnight.'
    },
    'afa': {
        'name': 'AFA Stores',
        'function': scrape_afa,
        'config_key': 'afa',
        'time': '1-2 hours',
        'products': 'varies',
        'warning': 'Requires cloudscraper (pip install cloudscraper)'
    }
}

# ============================================================
# MAIN FUNCTION
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description='Run furniture competitor scrapers',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run_scraper.py emma              # Quick test with Emma Mason
  python run_scraper.py onestop --save    # 1StopBedrooms with save
  python run_scraper.py coleman --save    # Coleman (5-6 hours!)
  python run_scraper.py --list            # List all scrapers
        """
    )
    
    parser.add_argument(
        'scraper',
        nargs='?',
        choices=['emma', 'onestop', 'coleman', 'afa'],
        help='Which scraper to run'
    )
    
    parser.add_argument(
        '--save', '-s',
        action='store_true',
        help='Save results to output/ directory'
    )
    
    parser.add_argument(
        '--list', '-l',
        action='store_true',
        help='List all available scrapers'
    )
    
    parser.add_argument(
        '--no-confirm',
        action='store_true',
        help='Skip confirmation prompt'
    )
    
    args = parser.parse_args()
    
    # List scrapers
    if args.list:
        print("\n" + "="*60)
        print("AVAILABLE SCRAPERS")
        print("="*60 + "\n")
        
        for key, info in SCRAPERS.items():
            print(f"{key:10} - {info['name']}")
            print(f"{'':10}   Time: {info['time']}")
            print(f"{'':10}   Products: {info['products']}")
            if 'warning' in info:
                print(f"{'':10}   ⚠️ {info['warning']}")
            print()
        
        return
    
    # Check scraper selected
    if not args.scraper:
        parser.print_help()
        return
    
    # Get scraper info
    scraper_key = args.scraper
    scraper_info = SCRAPERS[scraper_key]
    
    # Load config
    config = get_config()
    logger = get_logger("scraper_runner")
    
    # Header
    print("\n" + "="*60)
    print(f"🚀 {scraper_info['name'].upper()} SCRAPER")
    print("="*60)
    print(f"Expected time: {scraper_info['time']}")
    print(f"Expected products: {scraper_info['products']}")
    
    if 'warning' in scraper_info:
        print(f"\n⚠️ WARNING: {scraper_info['warning']}")
    
    print("="*60 + "\n")
    
    # Confirmation
    if not args.no_confirm:
        if scraper_key == 'coleman':
            confirm = input("Type 'yes' to start or anything else to cancel: ")
            if confirm.lower() != 'yes':
                print("Cancelled.")
                return
        else:
            input("Press Enter to start or Ctrl+C to cancel...")
        print()
    
    # Get scraper config
    scraper_config = config.get_scraper_config(scraper_info['config_key'])
    
    # Start
    logger.info("="*60)
    logger.info(f"Starting {scraper_info['name']} scraper")
    logger.info(f"Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("="*60)
    
    start_time = datetime.now()
    
    try:
        # Run scraper
        if scraper_info.get('needs_urls'):
            # Emma Mason needs URLs
            results = scraper_info['function'](scraper_info['test_urls'], scraper_config)
        else:
            results = scraper_info['function'](scraper_config)
        
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds() / 60
        
        # Results
        logger.info("="*60)
        logger.info(f"COMPLETED in {duration:.1f} minutes ({duration/60:.2f} hours)")
        logger.info(f"Products scraped: {len(results)}")
        logger.info("="*60)
        
        # Save results
        if args.save or len(results) > 100:
            output_dir = Path("output")
            output_dir.mkdir(exist_ok=True)
            
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_file = output_dir / f"{scraper_key}_{timestamp}.json"
            
            logger.info(f"Saving to {output_file}...")
            
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(results, f, indent=2, ensure_ascii=False)
            
            file_size = output_file.stat().st_size / 1024 / 1024
            logger.info(f"✓ Saved {len(results)} products ({file_size:.1f} MB)")
            logger.info(f"  File: {output_file}")
        
        # Sample output
        if results:
            print("\n" + "="*60)
            print("SAMPLE PRODUCTS")
            print("="*60)
            
            for i, product in enumerate(results[:3], 1):
                print(f"\n{i}. SKU: {product.get('sku', 'N/A')}")
                
                if 'brand' in product:
                    print(f"   Brand: {product['brand']}")
                if 'manufacturer' in product:
                    print(f"   Manufacturer: {product['manufacturer']}")
                if 'title' in product:
                    print(f"   Title: {product['title'][:50]}...")
                
                print(f"   Price: ${product.get('price', 'N/A')}")
                print(f"   URL: {product.get('url', 'N/A')[:60]}...")
            
            print()
        else:
            print("\n⚠️ No products scraped!")
            print("Check logs for errors.\n")
        
    except KeyboardInterrupt:
        logger.warning("\n⚠️ Scraping interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Scraper failed: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
