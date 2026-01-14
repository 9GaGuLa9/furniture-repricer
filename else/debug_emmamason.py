"""
Emma Mason DEBUG Scraper - HTML Analyzer
Зберігає HTML в файли для аналізу структури
"""

import sys
from pathlib import Path
import time
import random
from datetime import datetime

# Додати project root
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Імпортувати curl_cffi
try:
    from curl_cffi import requests
    print("✓ curl_cffi available")
except ImportError:
    import requests
    print("⚠️ Using standard requests")

# Створити директорію для HTML
debug_dir = Path(__file__).parent / "debug_html"
debug_dir.mkdir(exist_ok=True)

# Тестові URL
TEST_URLS = [
    {
        "name": "Intercon Furniture",
        "url": "https://emmamason.com/?q=intercon-furniture&brand=Intercon%20Furniture&page=1"
    },
    {
        "name": "ACME",
        "url": "https://emmamason.com/brands-acme-furniture.html?q=Acme&brand=ACME&page=1"
    },
    {
        "name": "Steve Silver",
        "url": "https://emmamason.com/?q=Steve%20Silver&brand=Steve%20Silver&page=1"
    },
]

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
]

def fetch_and_save(url: str, brand_name: str):
    """Завантажити і зберегти HTML"""
    print(f"\n{'='*60}")
    print(f"Fetching: {brand_name}")
    print(f"URL: {url}")
    print(f"{'='*60}")
    
    try:
        headers = {
            "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "accept-language": "en-US,en;q=0.9",
            "accept-encoding": "gzip, deflate, br",
            "user-agent": random.choice(USER_AGENTS),
            "cache-control": "no-cache",
            "pragma": "no-cache",
        }
        
        # Спробувати з curl_cffi
        try:
            from curl_cffi import requests as cffi_requests
            response = cffi_requests.get(
                url,
                headers=headers,
                impersonate="chrome120",
                timeout=30
            )
            print(f"✓ Used curl_cffi")
        except:
            response = requests.get(url, headers=headers, timeout=30)
            print(f"✓ Used standard requests")
        
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            html = response.text
            print(f"HTML length: {len(html)} chars")
            
            # Зберегти HTML
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{brand_name.replace(' ', '_')}_{timestamp}.html"
            filepath = debug_dir / filename
            
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(html)
            
            print(f"✓ Saved to: {filepath}")
            
            # Швидкий аналіз
            print(f"\nQuick analysis:")
            print(f"  'ais-InfiniteHits-list' found: {'ais-InfiniteHits-list' in html}")
            print(f"  'product-item-info' found: {'product-item-info' in html}")
            print(f"  'no-results' found: {'no-results' in html}")
            print(f"  'Cloudflare' found: {'Cloudflare' in html or 'Just a moment' in html}")
            print(f"  'result-wrapper' found: {'result-wrapper' in html}")
            
            # Знайти що є насправді
            if 'class="' in html:
                # Показати перші 10 унікальних класів
                import re
                classes = re.findall(r'class="([^"]+)"', html)
                unique_classes = list(set(classes))[:20]
                print(f"\n  First 20 unique classes:")
                for cls in unique_classes:
                    print(f"    - {cls}")
            
            return html
        else:
            print(f"✗ Failed with status {response.status_code}")
            return None
            
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return None

def main():
    print("\n" + "="*60)
    print("EMMA MASON HTML DEBUG ANALYZER")
    print("="*60)
    
    for test in TEST_URLS:
        html = fetch_and_save(test['url'], test['name'])
        
        if html:
            print(f"\n✓ Successfully fetched and saved HTML for {test['name']}")
        else:
            print(f"\n✗ Failed to fetch HTML for {test['name']}")
        
        # Затримка між запитами
        time.sleep(3)
    
    print("\n" + "="*60)
    print(f"HTML files saved to: {debug_dir.absolute()}")
    print("="*60)
    print("\n📝 Next steps:")
    print("1. Open HTML files in browser")
    print("2. Inspect the structure")
    print("3. Update scraper based on actual HTML")
    print("="*60)

if __name__ == "__main__":
    main()
