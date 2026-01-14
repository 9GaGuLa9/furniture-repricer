#!/usr/bin/env python3
"""
PATCH: Emma Mason URL + ID Matching
Додає пошук по ID як fallback для URL matching

ЩО ЗМІНЮЄТЬСЯ:
- Метод batch_update_emma_mason в app/modules/google_sheets.py
- Додається словник id_to_row для пошуку по ID
- Логіка: спочатку URL → потім ID
"""

import sys
from pathlib import Path
from datetime import datetime
import shutil


def create_backup():
    """Створити backup файлу"""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_dir = Path(f"backup_url_id_matching_{timestamp}")
    backup_dir.mkdir(exist_ok=True)
    
    print(f"\n💾 Creating backup in {backup_dir}/...")
    
    file_to_backup = Path("app/modules/google_sheets.py")
    if file_to_backup.exists():
        dest = backup_dir / file_to_backup.name
        shutil.copy2(file_to_backup, dest)
        print(f"   ✓ Backed up {file_to_backup}")
    
    print(f"✅ Backup created: {backup_dir}/\n")
    return backup_dir


def patch_batch_update_emma_mason():
    """Оновити метод batch_update_emma_mason"""
    
    sheets_py = Path("app/modules/google_sheets.py")
    if not sheets_py.exists():
        print("❌ ERROR: app/modules/google_sheets.py not found!")
        return False
    
    print("📝 Reading app/modules/google_sheets.py...")
    content = sheets_py.read_text(encoding='utf-8')
    
    # Перевірити чи метод вже оновлений
    if "id_to_row = {}" in content or "matched_by_id" in content:
        print("⚠️  Method already patched (found id_to_row or matched_by_id)!")
        return False
    
    # ═══════════════════════════════════════════════════════════════
    # ЗНАЙТИ початок методу batch_update_emma_mason
    # ═══════════════════════════════════════════════════════════════
    
    method_start = "    def batch_update_emma_mason(self, scraped_products: List[Dict]) -> int:"
    
    if method_start not in content:
        print("❌ ERROR: Could not find batch_update_emma_mason method!")
        return False
    
    # ═══════════════════════════════════════════════════════════════
    # ЗНАЙТИ кінець методу (наступний def на тому ж рівні відступу)
    # ═══════════════════════════════════════════════════════════════
    
    lines = content.split('\n')
    start_idx = None
    end_idx = None
    
    for i, line in enumerate(lines):
        if method_start in line:
            start_idx = i
        elif start_idx is not None and line.startswith('    def ') and i > start_idx:
            end_idx = i
            break
    
    if start_idx is None:
        print("❌ ERROR: Could not find method start!")
        return False
    
    # Якщо не знайшли наступний метод - брати до кінця класу
    if end_idx is None:
        # Шукати закриваючу дужку класу
        for i in range(start_idx + 1, len(lines)):
            if lines[i].strip() and not lines[i].startswith(' '):
                end_idx = i
                break
        
        if end_idx is None:
            end_idx = len(lines)
    
    print(f"Found method: lines {start_idx+1} to {end_idx}")
    
    # ═══════════════════════════════════════════════════════════════
    # НОВИЙ МЕТОД
    # ═══════════════════════════════════════════════════════════════
    
    new_method = '''    def batch_update_emma_mason(self, scraped_products: List[Dict]) -> int:
        """
        Batch оновлення для Emma Mason товарів
        
        ✅ UPDATED v4.0:
        - URL normalization (як раніше)
        - ID fallback (НОВИНКА!)
        - Matching логіка: спочатку URL → потім ID
        - Price conversion
        - Batch history з SKU
        
        Args:
            scraped_products: Список товарів з Emma Mason [{'id': '', 'url': '', 'price': ''}]
        
        Returns:
            Кількість оновлених товарів
        """
        try:
            sheet_id = self.config['main_sheet']['id']
            sheet_name = self.config['main_sheet']['name']
            
            self.logger.info(f"Batch updating Emma Mason data for {len(scraped_products)} products...")
            
            # Завантажити всі дані з таблиці
            time.sleep(0.5)
            worksheet = self.client.open_sheet(sheet_id, sheet_name)
            all_data = worksheet.get_all_values()
            
            # ═══════════════════════════════════════════════════════════════
            # ✅ НОВИНКА: Створити ДВА словники - для URL та для ID
            # ═══════════════════════════════════════════════════════════════
            url_to_row = {}
            id_to_row = {}
            
            for idx, row in enumerate(all_data, start=1):
                if len(row) > 5:  # F = index 5 (0-based)
                    sku = row[0] if len(row) > 0 else ''  # A = SKU
                    url_raw = row[5].strip() if len(row) > 5 else ''  # F = Our URL
                    emma_id = row[17].strip() if len(row) > 17 else ''  # R = ID from emmamason
                    old_price = row[3] if len(row) > 3 else ''  # D = Our Sales Price
                    
                    # URL mapping (з нормалізацією)
                    if url_raw:
                        url_normalized = normalize_url(url_raw)
                        url_to_row[url_normalized] = {
                            'row_num': idx,
                            'sku': sku,
                            'old_price': old_price,
                            'original_url': url_raw,
                            'emma_id': emma_id
                        }
                    
                    # ✅ ID mapping (НОВИНКА!)
                    if emma_id:
                        id_to_row[emma_id] = {
                            'row_num': idx,
                            'sku': sku,
                            'old_price': old_price,
                            'original_url': url_raw,
                            'emma_id': emma_id
                        }
            
            self.logger.info(f"Loaded {len(url_to_row)} URLs and {len(id_to_row)} IDs from sheet")
            
            # ═══════════════════════════════════════════════════════════════
            # Знайти співпадіння та підготувати оновлення
            # ═══════════════════════════════════════════════════════════════
            all_updates = []
            updated_count = 0
            history_records = []
            
            # Статистика matching
            matched_by_url = 0
            matched_by_id = 0
            no_match_count = 0
            price_conversion_errors = 0
            
            for product in scraped_products:
                url_raw = product.get('url', '').strip()
                emma_id = product.get('id', '').strip()
                price_raw = product.get('price', '')
                
                # Перевірка що є хоча б URL або ID
                if not url_raw and not emma_id:
                    no_match_count += 1
                    continue
                
                # ═══════════════════════════════════════════════════════════════
                # ✅ КЛЮЧОВА ЛОГІКА: Спочатку URL → потім ID
                # ═══════════════════════════════════════════════════════════════
                row_info = None
                matched_by = None
                
                # КРОК 1: Спробувати знайти по URL
                if url_raw:
                    url_normalized = normalize_url(url_raw)
                    if url_normalized in url_to_row:
                        row_info = url_to_row[url_normalized]
                        matched_by = 'URL'
                        matched_by_url += 1
                
                # КРОК 2: Якщо не знайдено по URL - спробувати по ID
                if not row_info and emma_id:
                    if emma_id in id_to_row:
                        row_info = id_to_row[emma_id]
                        matched_by = 'ID'
                        matched_by_id += 1
                
                # Якщо не знайдено ні по URL, ні по ID
                if not row_info:
                    no_match_count += 1
                    continue
                
                # ═══════════════════════════════════════════════════════════════
                # Отримати дані з row_info
                # ═══════════════════════════════════════════════════════════════
                row_num = row_info['row_num']
                sku = row_info['sku']
                old_price_str = row_info['old_price']
                
                # ✅ Конвертувати ціну
                try:
                    new_price = self._to_float(price_raw)
                    
                    if new_price == 0.0 and price_raw:
                        self.logger.warning(f"Failed to convert price '{price_raw}' for {url_raw[:50]}")
                        price_conversion_errors += 1
                        continue
                        
                except Exception as e:
                    self.logger.error(f"Price conversion error for '{price_raw}': {e}")
                    price_conversion_errors += 1
                    continue
                
                old_price = self._to_float(old_price_str)
                
                # ═══════════════════════════════════════════════════════════════
                # Підготувати updates
                # ═══════════════════════════════════════════════════════════════
                
                # Our Sales Price (D = 4)
                all_updates.append({
                    'range': f'D{row_num}',
                    'values': [[new_price]]
                })
                
                # ID from emmamason (R = 18) - оновити якщо є новий ID
                if emma_id:
                    all_updates.append({
                        'range': f'R{row_num}',
                        'values': [[emma_id]]
                    })
                
                # Last update (Q = 17)
                all_updates.append({
                    'range': f'Q{row_num}',
                    'values': [[datetime.now().strftime('%Y-%m-%d %H:%M:%S')]]
                })
                
                updated_count += 1
                
                # ✅ Зберегти для історії з SKU!
                if abs(new_price - old_price) > 0.01:
                    history_records.append({
                        'sku': sku,
                        'url': url_raw or row_info.get('original_url', ''),
                        'old_price': old_price,
                        'new_price': new_price
                    })
            
            # ═══════════════════════════════════════════════════════════════
            # ✅ ЗВІТ про matching (ПОКРАЩЕНИЙ!)
            # ═══════════════════════════════════════════════════════════════
            self.logger.info("="*60)
            self.logger.info("EMMA MASON MATCHING RESULTS:")
            self.logger.info(f"  Total products from scraper: {len(scraped_products)}")
            self.logger.info(f"  URLs in sheet: {len(url_to_row)}")
            self.logger.info(f"  IDs in sheet: {len(id_to_row)}")
            self.logger.info("")
            self.logger.info(f"  ✅ Matched by URL: {matched_by_url}")
            self.logger.info(f"  ✅ Matched by ID (fallback): {matched_by_id}")
            self.logger.info(f"  ❌ No match: {no_match_count}")
            
            if price_conversion_errors > 0:
                self.logger.warning(f"  ⚠️  Price conversion errors: {price_conversion_errors}")
            
            total_matched = matched_by_url + matched_by_id
            if len(scraped_products) > 0:
                match_rate = total_matched / len(scraped_products) * 100
                self.logger.info(f"  Match rate: {match_rate:.1f}%")
            
            self.logger.info("="*60)
            
            # ═══════════════════════════════════════════════════════════════
            # Виконати batch update
            # ═══════════════════════════════════════════════════════════════
            if all_updates:
                self.logger.info(f"Executing batch update with {len(all_updates)} changes...")
                
                chunk_size = 500
                for i in range(0, len(all_updates), chunk_size):
                    chunk = all_updates[i:i+chunk_size]
                    time.sleep(0.5)
                    self.client.batch_update(sheet_id, chunk, sheet_name)
                    
                    if i + chunk_size < len(all_updates):
                        time.sleep(1.0)
                
                self.logger.info(f"✓ Batch update completed: {updated_count} products")
            
            # ✅ Додати записи в історію (BATCH!)
            if history_records:
                self.logger.info(f"Adding {len(history_records)} records to Price_History (batch mode)...")
                added = self.batch_add_to_history(history_records)
                self.logger.info(f"✓ Price History: {added} records added")
            
            return updated_count
            
        except Exception as e:
            self.logger.error(f"Failed batch update Emma Mason: {e}", exc_info=True)
            return 0
'''
    
    # ═══════════════════════════════════════════════════════════════
    # ЗАМІНИТИ старий метод на новий
    # ═══════════════════════════════════════════════════════════════
    
    new_lines = lines[:start_idx] + [new_method] + lines[end_idx:]
    new_content = '\n'.join(new_lines)
    
    # Зберегти
    sheets_py.write_text(new_content, encoding='utf-8')
    print("✅ Updated batch_update_emma_mason method in google_sheets.py")
    
    return True


def main():
    """Головна функція"""
    print("="*70)
    print(" PATCH: Emma Mason URL + ID Matching")
    print("="*70)
    print()
    print("This will update batch_update_emma_mason to search by:")
    print("  1. URL (primary)")
    print("  2. ID from column R (fallback)")
    print()
    
    # Перевірити що ми в правильній директорії
    if not Path("app").exists():
        print("❌ ERROR: 'app' directory not found!")
        print("   Please run this script from the project root directory.")
        sys.exit(1)
    
    # Створити backup
    backup_dir = create_backup()
    
    # Застосувати patch
    print("🔧 Applying patch...\n")
    
    success = patch_batch_update_emma_mason()
    print()
    
    # Підсумок
    print("="*70)
    print(" SUMMARY")
    print("="*70)
    
    if success:
        print("✅ Patch applied successfully!")
        print()
        print("Changes:")
        print("  • Added id_to_row dictionary for ID matching")
        print("  • Search priority: URL → ID (fallback)")
        print("  • Enhanced matching statistics")
        print()
        print("Next steps:")
        print("  1. Run repricer: python run_repricer.py")
        print("  2. Check logs for matching statistics:")
        print("     - Matched by URL")
        print("     - Matched by ID (fallback)")
        print("     - Match rate")
        print()
        print(f"⚠️  Backup saved to: {backup_dir}/")
    else:
        print("⚠️  Patch could not be applied.")
        print("   Check warnings above.")
        print()
        print("Manual steps:")
        print("  1. Open app/modules/google_sheets.py")
        print("  2. Find method batch_update_emma_mason (around line 855)")
        print("  3. Replace entire method with version from:")
        print("     /tmp/batch_update_emma_mason_updated.py")
    
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
