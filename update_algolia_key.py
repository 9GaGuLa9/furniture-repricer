#!/usr/bin/env python3
"""
Quick Algolia API Key Updater
Quick update of the Algolia API key

Usage:
    python update_algolia_key.py NEW_API_KEY_HERE
    python update_algolia_key.py "MmQ5Yjc2NjZhMjcyMDM3..."
"""

import sys
import re
from pathlib import Path
from datetime import datetime

# Colors
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'

def print_success(text):
    print(f"{GREEN}✓ {text}{RESET}")

def print_error(text):
    print(f"{RED}✗ {text}{RESET}")

def print_warning(text):
    print(f"{YELLOW}⚠ {text}{RESET}")

def print_info(text):
    print(f"{BLUE}ℹ {text}{RESET}")

def validate_api_key(key):
    """API key validation"""
    if not key:
        return False, "Key is empty"
    
    if len(key) < 50:
        return False, f"Key too short ({len(key)} chars, expected 100+)"
    
    if ' ' in key:
        return False, "Key contains spaces"
    
    # Base64 check
    if not re.match(r'^[A-Za-z0-9+/=]+$', key):
        return False, "Key contains invalid characters (not base64)"
    
    return True, "OK"

def find_scraper_file():
    """Find the file emmamason_algolia.py"""
    
    # Try different possible paths
    possible_paths = [
        Path("app/scrapers/emmamason_algolia.py"),
        Path("scrapers/emmamason_algolia.py"),
        Path("emmamason_algolia.py"),
    ]
    
    for path in possible_paths:
        if path.exists():
            return path
    
    return None

def update_api_key(file_path, new_key):
    """Update the API key in the file"""
    
    print_info(f"Reading {file_path}...")
    
    # Read file
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        return False, f"Failed to read file: {e}"
    
    # Backup
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = file_path.with_suffix(f'.py.backup_{timestamp}')
    
    try:
        with open(backup_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print_success(f"Backup created: {backup_path.name}")
    except Exception as e:
        return False, f"Failed to create backup: {e}"
    
    # Replace key - find the active string (without # comment)
    pattern = r'(^\s*ALGOLIA_API_KEY\s*=\s*)"([^"]+)"'
    
    def replace_key(match):
        indent = match.group(1)
        return f'{indent}"{new_key}"'
    
    new_content = re.sub(pattern, replace_key, content, count=1, flags=re.MULTILINE)
    
    if new_content == content:
        return False, "Pattern not found in file (ALGOLIA_API_KEY = \"...\")"
    
    # Write
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print_success(f"API key updated in {file_path}")
    except Exception as e:
        # Restore from backup
        with open(backup_path, 'r', encoding='utf-8') as f:
            content = f.read()
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        return False, f"Failed to write file (restored from backup): {e}"
    
    return True, "OK"

def test_new_key(file_path):
    """Quick test to see if the key works"""
    
    print_info("Testing new key...")
    
    try:
        # Import scraper
        import importlib.util
        spec = importlib.util.spec_from_file_location("scraper", file_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        
        # Test
        config = {
            'delay_min': 0.5,
            'delay_max': 1.5,
            'retry_attempts': 1,
            'timeout': 10
        }
        
        scraper = module.EmmaMasonAlgoliaScraper(config)
        
        # Build test params
        params = scraper._build_params([("brand", "ACME")], page=0, hits=1)
        
        # Try fetch
        result = scraper._fetch_algolia(params)
        
        if result:
            print_success("API key is VALID! [OK]")
            return True
        else:
            print_warning("API key test returned None (might be expired)")
            return False
    
    except module.AlgoliaAPIKeyExpired as e:
        print_error(f"API key is INVALID: {e}")
        return False
    
    except Exception as e:
        print_warning(f"Test failed (but key might still work): {e}")
        return False

def main():
    print(f"\n{BLUE}{'='*60}{RESET}")
    print(f"{BLUE}Algolia API Key Updater{RESET}")
    print(f"{BLUE}{'='*60}{RESET}\n")
    
    # Check args
    if len(sys.argv) < 2:
        print_error("Missing API key argument")
        print(f"\nUsage:")
        print(f"  python {sys.argv[0]} NEW_API_KEY")
        print(f"\nExample:")
        print(f'  python {sys.argv[0]} "MmQ5Yjc2NjZhMjcyMDM3..."')
        print()
        sys.exit(1)
    
    new_key = sys.argv[1].strip().strip('"').strip("'")
    
    # Validate key
    print_info("Validating API key...")
    valid, msg = validate_api_key(new_key)
    
    if not valid:
        print_error(f"Invalid API key: {msg}")
        print(f"\nKey preview: {new_key[:50]}...")
        sys.exit(1)
    
    print_success(f"Key format looks good ({len(new_key)} chars)")
    print_info(f"Key preview: {new_key[:30]}...")
    
    # Find file
    print_info("Searching for scraper file...")
    file_path = find_scraper_file()
    
    if not file_path:
        print_error("Could not find emmamason_algolia.py")
        print("\nSearched in:")
        print("  - app/scrapers/emmamason_algolia.py")
        print("  - scrapers/emmamason_algolia.py")
        print("  - emmamason_algolia.py")
        print("\nMake sure you run this from project root directory")
        sys.exit(1)
    
    print_success(f"Found: {file_path}")
    
    # Update
    print_info("Updating API key...")
    success, msg = update_api_key(file_path, new_key)
    
    if not success:
        print_error(msg)
        sys.exit(1)
    
    # Test (optional)
    print()
    test_choice = input("Test new key now? (Y/n): ").strip().lower()
    
    if test_choice != 'n':
        test_new_key(file_path)
    
    # Summary
    print(f"\n{GREEN}{'='*60}{RESET}")
    print(f"{GREEN}[OK] API KEY UPDATED SUCCESSFULLY{RESET}")
    print(f"{GREEN}{'='*60}{RESET}\n")
    
    print("Next steps:")
    print("  1. Run scraper: python -m app.scrapers.emmamason_smart_scraper")
    print("  2. Monitor logs for any issues")
    print("  3. Verify product count is normal (7000+)")
    print()
    print(f"Backup saved at: {file_path.with_suffix('.py.backup_*')}")
    print()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n\n{YELLOW}Cancelled by user{RESET}\n")
        sys.exit(1)
    except Exception as e:
        print(f"\n{RED}Unexpected error: {e}{RESET}\n")
        import traceback
        traceback.print_exc()
        sys.exit(1)
