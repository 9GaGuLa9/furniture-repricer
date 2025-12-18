"""
Test Runner для Emma Mason Scraper
Правильний спосіб запуску модулів
"""

import sys
from pathlib import Path

# Додати root проекту до Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Тепер можна імпортувати
from app.modules.logger import setup_logging
import logging

# Налаштування логування
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(name)-12s | %(levelname)-8s | %(message)s',
    datefmt='%H:%M:%S'
)

# Тестові дані
test_config = {
    'delay_min': 1.0,
    'delay_max': 2.0,
    'retry_attempts': 3,
    'timeout': 30
}

test_urls = [
    "https://emmamason.com/lighting.html",
    "https://emmamason.com/bedroom-furniture-dresser.html",
    "https://emmamason.com/dining-rooms-dining-chairs-arm-chairs.html"
]

print("="*60)
print("ТЕСТ EMMA MASON SCRAPER")
print("="*60)
print()

# Імпорт scraper функції
from app.scrapers.emmamason import scrape_emmamason

# Запуск
results = scrape_emmamason(test_urls, test_config)

# Виведення результатів
print()
print("="*60)
print("РЕЗУЛЬТАТИ:")
print("="*60)

if results:
    for product in results:
        print(f"\nSKU: {product['sku']}")
        print(f"  Price: ${product['price']}")
        print(f"  URL: {product['url'][:60]}...")
else:
    print("❌ Немає результатів")

print()
print("="*60)
