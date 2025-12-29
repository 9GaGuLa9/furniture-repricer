#!/usr/bin/env python3
"""
Automatic Fix Script for Furniture Repricer
Застосовує всі необхідні виправлення автоматично
"""

import sys
from pathlib import Path

def apply_main_py_fix():
    """Виправити app/main.py - додати competitor дані до _prices_to_update"""
    
    main_py = Path("app/main.py")
    if not main_py.exists():
        print("❌ ERROR: app/main.py not found!")
        return False
    
    print("📝 Reading app/main.py...")
    content = main_py.read_text(encoding='utf-8')
    
    # Старий код для заміни
    old_code = """            # Додати _prices_to_update
            product['_prices_to_update'] = {
                'suggest_price': suggested_price,
            }
            
            filtered_products.append(product)"""
    
    # Новий код
    new_code = """            # Додати _prices_to_update
            prices_dict = {
                'suggest_price': suggested_price,
            }
            
            # ✅ КРИТИЧНО: Додати competitor дані якщо є!
            # Без цього batch_update_all не може записати competitor ціни в стовпці G-L
            if product.get('site1_price'):
                prices_dict['site1_price'] = product.get('site1_price')
                prices_dict['site1_url'] = product.get('site1_url', '')
                prices_dict['site1_sku'] = product.get('site1_sku', '')
            
            if product.get('site2_price'):
                prices_dict['site2_price'] = product.get('site2_price')
                prices_dict['site2_url'] = product.get('site2_url', '')
                prices_dict['site2_sku'] = product.get('site2_sku', '')
            
            if product.get('site3_price'):
                prices_dict['site3_price'] = product.get('site3_price')
                prices_dict['site3_url'] = product.get('site3_url', '')
                prices_dict['site3_sku'] = product.get('site3_sku', '')
            
            product['_prices_to_update'] = prices_dict
            
            filtered_products.append(product)"""
    
    if old_code not in content:
        print("⚠️  WARNING: Could not find exact match in app/main.py")
        print("    The file may have been already fixed or modified.")
        return False
    
    # Замінити
    content = content.replace(old_code, new_code)
    
    # Зберегти
    main_py.write_text(content, encoding='utf-8')
    print("✅ app/main.py fixed successfully!")
    return True


def apply_google_sheets_fix():
    """Виправити app/modules/google_sheets.py - розрахунок change"""
    
    sheets_py = Path("app/modules/google_sheets.py")
    if not sheets_py.exists():
        print("❌ ERROR: app/modules/google_sheets.py not found!")
        return False
    
    print("📝 Reading app/modules/google_sheets.py...")
    content = sheets_py.read_text(encoding='utf-8')
    
    # Старий код для заміни
    old_code = "                change = new_price - old_price if old_price else 0"
    
    # Новий код
    new_code = """                # ✅ ВИПРАВЛЕННЯ: Завжди розраховувати change
                change = new_price - old_price"""
    
    if old_code not in content:
        print("⚠️  WARNING: Could not find exact match in app/modules/google_sheets.py")
        print("    The file may have been already fixed or modified.")
        return False
    
    # Замінити
    content = content.replace(old_code, new_code)
    
    # Зберегти
    sheets_py.write_text(content, encoding='utf-8')
    print("✅ app/modules/google_sheets.py fixed successfully!")
    return True


def create_backup():
    """Створити backup файлів перед зміною"""
    import shutil
    from datetime import datetime
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_dir = Path(f"backup_{timestamp}")
    backup_dir.mkdir(exist_ok=True)
    
    files_to_backup = [
        "app/main.py",
        "app/modules/google_sheets.py"
    ]
    
    print(f"\n💾 Creating backup in {backup_dir}/...")
    for file_path in files_to_backup:
        file = Path(file_path)
        if file.exists():
            dest = backup_dir / file.name
            shutil.copy2(file, dest)
            print(f"   ✓ Backed up {file_path}")
    
    print(f"✅ Backup created: {backup_dir}/\n")
    return backup_dir


def main():
    """Головна функція"""
    print("="*70)
    print(" FURNITURE REPRICER - AUTOMATIC FIX SCRIPT")
    print("="*70)
    print()
    print("This script will fix two issues:")
    print("  1. Data sheet columns G-L (competitor prices) not updating")
    print("  2. Price_History Change column always showing 0")
    print()
    
    # Перевірити що ми в правильній директорії
    if not Path("app").exists():
        print("❌ ERROR: 'app' directory not found!")
        print("   Please run this script from the project root directory.")
        sys.exit(1)
    
    # Створити backup
    backup_dir = create_backup()
    
    # Застосувати виправлення
    print("🔧 Applying fixes...\n")
    
    fix1_success = apply_main_py_fix()
    print()
    
    fix2_success = apply_google_sheets_fix()
    print()
    
    # Підсумок
    print("="*70)
    print(" SUMMARY")
    print("="*70)
    
    if fix1_success:
        print("✅ Fix 1: app/main.py - competitor data in _prices_to_update")
    else:
        print("❌ Fix 1: FAILED or already applied")
    
    if fix2_success:
        print("✅ Fix 2: app/modules/google_sheets.py - change calculation")
    else:
        print("❌ Fix 2: FAILED or already applied")
    
    print()
    
    if fix1_success and fix2_success:
        print("🎉 ALL FIXES APPLIED SUCCESSFULLY!")
        print()
        print("Next steps:")
        print("  1. Run test: python run_repricer.py --test")
        print("  2. Check Google Sheets:")
        print("     - Data sheet columns G-L should show competitor prices")
        print("     - Price_History Change column should show price differences")
        print()
        print(f"⚠️  Backup saved to: {backup_dir}/")
        print("   You can restore from backup if needed.")
    else:
        print("⚠️  Some fixes could not be applied.")
        print("   Please check the warnings above and apply fixes manually.")
        print("   See /tmp/FIXING_GUIDE.txt for detailed instructions.")
    
    print("="*70)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
