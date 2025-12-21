"""
Scraper Results Analyzer
Аналіз результатів scraping для швидкого огляду
"""

import sys
import json
from pathlib import Path
from collections import Counter
from datetime import datetime

def analyze_file(filepath):
    """Аналіз одного JSON файлу з результатами"""
    
    print("\n" + "="*60)
    print(f"ANALYZING: {filepath.name}")
    print("="*60 + "\n")
    
    # Завантажити дані
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        print(f"❌ Error loading file: {e}")
        return
    
    if not data:
        print("⚠️ File is empty!")
        return
    
    # Базова статистика
    print(f"Total products: {len(data):,}")
    print(f"File size: {filepath.stat().st_size / 1024 / 1024:.2f} MB")
    print(f"Created: {datetime.fromtimestamp(filepath.stat().st_mtime).strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Аналіз структури
    if data:
        first_item = data[0]
        print(f"\nData structure:")
        print(f"  Fields: {list(first_item.keys())}")
    
    # Аналіз по полях
    analyze_fields(data)
    
    # Sample
    print(f"\n{'='*60}")
    print("SAMPLE PRODUCTS (first 3):")
    print("="*60)
    
    for i, product in enumerate(data[:3], 1):
        print(f"\n{i}. {product}")

def analyze_fields(data):
    """Детальний аналіз полів"""
    
    # Підрахунок популярних значень
    brands = []
    categories = []
    prices = []
    
    for item in data:
        # Brand/Manufacturer
        brand = item.get('brand') or item.get('manufacturer')
        if brand:
            brands.append(brand)
        
        # Category
        category = item.get('category_name')
        if category:
            categories.append(category)
        
        # Price
        price = item.get('price')
        if price:
            try:
                prices.append(float(price))
            except:
                pass
    
    # Brand statistics
    if brands:
        brand_counts = Counter(brands)
        print(f"\nTop 10 Brands:")
        for brand, count in brand_counts.most_common(10):
            print(f"  {brand:<30} {count:>6,} ({count/len(data)*100:.1f}%)")
    
    # Category statistics
    if categories:
        cat_counts = Counter(categories)
        print(f"\nTop 10 Categories:")
        for cat, count in cat_counts.most_common(10):
            print(f"  {cat:<40} {count:>6,}")
    
    # Price statistics
    if prices:
        print(f"\nPrice Statistics:")
        print(f"  Average: ${sum(prices)/len(prices):.2f}")
        print(f"  Min: ${min(prices):.2f}")
        print(f"  Max: ${max(prices):.2f}")
        print(f"  Median: ${sorted(prices)[len(prices)//2]:.2f}")

def main():
    output_dir = Path("output")
    
    if not output_dir.exists():
        print("❌ output/ directory not found!")
        print("Run a scraper first to generate results.")
        return
    
    # Знайти всі JSON файли
    json_files = list(output_dir.glob("*.json"))
    
    if not json_files:
        print("❌ No JSON files found in output/ directory")
        return
    
    print("\n" + "="*60)
    print("SCRAPER RESULTS ANALYZER")
    print("="*60)
    print(f"\nFound {len(json_files)} result file(s):\n")
    
    for i, file in enumerate(sorted(json_files), 1):
        size_mb = file.stat().st_size / 1024 / 1024
        modified = datetime.fromtimestamp(file.stat().st_mtime).strftime('%Y-%m-%d %H:%M')
        print(f"{i}. {file.name:<50} {size_mb:>6.1f} MB  {modified}")
    
    print(f"\n{'='*60}\n")
    
    # Вибір файлу
    if len(json_files) == 1:
        choice = 1
        print(f"Analyzing only file: {json_files[0].name}\n")
    else:
        try:
            choice = input(f"Choose file (1-{len(json_files)}) or 'all': ").strip()
            
            if choice.lower() == 'all':
                for file in json_files:
                    analyze_file(file)
                return
            
            choice = int(choice)
            if choice < 1 or choice > len(json_files):
                print("Invalid choice!")
                return
        except ValueError:
            print("Invalid input!")
            return
        except KeyboardInterrupt:
            print("\nCancelled.")
            return
    
    # Аналіз вибраного файлу
    selected_file = sorted(json_files)[choice - 1]
    analyze_file(selected_file)
    
    print("\n" + "="*60)
    print("Analysis complete!")
    print("="*60 + "\n")

if __name__ == "__main__":
    main()
