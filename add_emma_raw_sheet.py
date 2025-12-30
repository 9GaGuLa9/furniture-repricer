#!/usr/bin/env python3
"""
Add Emma Mason Raw Sheet - Automatic Patch
Додає діагностичний аркуш для збереження RAW даних Emma Mason
"""

import sys
from pathlib import Path


def add_emma_raw_method_to_google_sheets():
    """Додати метод batch_update_emma_mason_raw до google_sheets.py"""
    
    sheets_py = Path("app/modules/google_sheets.py")
    if not sheets_py.exists():
        print("❌ ERROR: app/modules/google_sheets.py not found!")
        return False
    
    print("📝 Reading app/modules/google_sheets.py...")
    content = sheets_py.read_text(encoding='utf-8')
    
    # Перевірити чи метод вже існує
    if "batch_update_emma_mason_raw" in content:
        print("⚠️  Method batch_update_emma_mason_raw already exists!")
        return False
    
    # Новий метод для додавання
    new_method = '''
    def batch_update_emma_mason_raw(self, scraped_products: List[Dict]) -> int:
        """
        ✅ DEBUG: Записати ВСІ RAW дані від Emma Mason scraper
        
        Структура Emma_Mason_Raw sheet:
        ID | URL | Price | Brand | Scraped At
        
        Args:
            scraped_products: Список товарів з Emma Mason scraper
                [{'id': '', 'url': '', 'price': '', 'brand': '', 'scraped_at': ''}, ...]
        
        Returns:
            Кількість записаних товарів
        """
        try:
            sheet_id = self.config['main_sheet']['id']
            emma_raw_sheet = "Emma_Mason_Raw"
            
            if not scraped_products:
                self.logger.warning("No Emma Mason products to save (empty list)")
                return 0
            
            self.logger.info(f"Updating Emma_Mason_Raw sheet with {len(scraped_products)} RAW products...")
            
            # Перевірити чи існує аркуш
            if not self.client.worksheet_exists(sheet_id, emma_raw_sheet):
                self.logger.info("Creating Emma_Mason_Raw worksheet...")
                ws = self.client.create_worksheet(sheet_id, emma_raw_sheet, rows=10000, cols=5)
                
                # Headers
                headers = [
                    'ID',           # A - product ID from Emma Mason
                    'URL',          # B - full URL
                    'Price',        # C - scraped price
                    'Brand',        # D - brand name
                    'Scraped At'    # E - timestamp
                ]
                ws.update('A1', [headers])
                time.sleep(0.5)
            
            # Підготувати ВСІ рядки
            all_rows = []
            
            for product in scraped_products:
                row = [
                    product.get('id', ''),
                    product.get('url', ''),
                    self._to_float(product.get('price', 0)),  # Конвертувати в float
                    product.get('brand', ''),
                    product.get('scraped_at', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
                ]
                all_rows.append(row)
            
            # Записати ВСЕ одним batch update
            if all_rows:
                self.logger.info(f"Writing {len(all_rows)} Emma Mason RAW products...")
                
                time.sleep(0.5)
                worksheet = self.client.open_sheet(sheet_id, emma_raw_sheet)
                
                # ✅ Розширити worksheet перед записом
                rows_needed = len(all_rows) + 1  # +1 для header
                current_rows = worksheet.row_count
                
                if current_rows < rows_needed:
                    self.logger.info(f"Expanding worksheet from {current_rows} to {rows_needed} rows...")
                    worksheet.resize(rows=rows_needed)
                    time.sleep(0.3)
                
                # Очистити старі дані (залишити тільки header)
                if current_rows > 1:
                    self.logger.info("Clearing old data...")
                    clear_range = f'A2:E{current_rows}'
                    worksheet.batch_clear([clear_range])
                    time.sleep(0.3)
                
                # Визначити діапазон
                start_row = 2  # Після header
                end_row = start_row + len(all_rows) - 1
                
                # Update одним range з USER_ENTERED для правильного форматування
                range_name = f'A{start_row}:E{end_row}'
                worksheet.update(range_name, all_rows, value_input_option='USER_ENTERED')
                
                self.logger.info(f"✅ Emma_Mason_Raw sheet updated: {len(all_rows)} RAW products")
                
                # Показати статистику по брендах
                brands = {}
                for product in scraped_products:
                    brand = product.get('brand', 'Unknown')
                    brands[brand] = brands.get(brand, 0) + 1
                
                self.logger.info("Emma Mason products by brand:")
                for brand, count in brands.items():
                    self.logger.info(f"  {brand}: {count}")
                
                return len(all_rows)
            else:
                self.logger.warning("No Emma Mason data to write!")
                return 0
            
        except Exception as e:
            self.logger.error(f"Failed to update Emma_Mason_Raw sheet: {e}", exc_info=True)
            return 0
'''
    
    # Знайти місце для вставки (після batch_update_competitors_raw)
    marker = "            return 0\n" + \
             "            \n" + \
             "        except Exception as e:\n" + \
             "            self.logger.error(f\"Failed to update Competitors sheet: {e}\", exc_info=True)\n" + \
             "            return 0"
    
    if marker not in content:
        print("⚠️  Could not find insertion point in google_sheets.py")
        print("    Please add the method manually after batch_update_competitors_raw")
        return False
    
    # Вставити новий метод
    content = content.replace(marker, marker + new_method)
    
    # Зберегти
    sheets_py.write_text(content, encoding='utf-8')
    print("✅ Added batch_update_emma_mason_raw method to google_sheets.py")
    
    return True


def add_emma_raw_call_to_main():
    """Додати виклик batch_update_emma_mason_raw в main.py"""
    
    main_py = Path("app/main.py")
    if not main_py.exists():
        print("❌ ERROR: app/main.py not found!")
        return False
    
    print("📝 Reading app/main.py...")
    content = main_py.read_text(encoding='utf-8')
    
    # Перевірити чи виклик вже є
    if "batch_update_emma_mason_raw" in content:
        print("⚠️  Call to batch_update_emma_mason_raw already exists!")
        return False
    
    # Старий код для заміни
    old_code = """            # Batch update
            if emma_products and not self.runtime_config.get('dry_run'):
                updated = self.sheets_manager.batch_update_emma_mason(emma_products)
                self.logger.info(f"✓ Emma Mason updated: {updated} products")"""
    
    # Новий код
    new_code = """            # Batch update
            if emma_products and not self.runtime_config.get('dry_run'):
                # ✅ DEBUG: Зберегти RAW дані в окремий аркуш
                raw_saved = self.sheets_manager.batch_update_emma_mason_raw(emma_products)
                self.logger.info(f"✓ Emma Mason RAW saved: {raw_saved} products")
                
                # Оновити основну таблицю
                updated = self.sheets_manager.batch_update_emma_mason(emma_products)
                self.logger.info(f"✓ Emma Mason updated: {updated} products")"""
    
    if old_code not in content:
        print("⚠️  Could not find exact match in app/main.py")
        print("    The code may have been already modified.")
        return False
    
    # Замінити
    content = content.replace(old_code, new_code)
    
    # Зберегти
    main_py.write_text(content, encoding='utf-8')
    print("✅ Added call to batch_update_emma_mason_raw in main.py")
    
    return True


def create_backup():
    """Створити backup файлів"""
    import shutil
    from datetime import datetime
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_dir = Path(f"backup_emma_raw_{timestamp}")
    backup_dir.mkdir(exist_ok=True)
    
    print(f"\n💾 Creating backup in {backup_dir}/...")
    
    files_to_backup = [
        "app/main.py",
        "app/modules/google_sheets.py"
    ]
    
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
    print(" ADD EMMA MASON RAW SHEET - DEBUG FEATURE")
    print("="*70)
    print()
    print("This will add a diagnostic sheet 'Emma_Mason_Raw' that saves")
    print("all scraped Emma Mason data for debugging matching issues.")
    print()
    
    # Перевірити що ми в правильній директорії
    if not Path("app").exists():
        print("❌ ERROR: 'app' directory not found!")
        print("   Please run this script from the project root directory.")
        sys.exit(1)
    
    # Створити backup
    backup_dir = create_backup()
    
    # Застосувати зміни
    print("🔧 Adding Emma Mason Raw sheet support...\n")
    
    success1 = add_emma_raw_method_to_google_sheets()
    print()
    
    success2 = add_emma_raw_call_to_main()
    print()
    
    # Підсумок
    print("="*70)
    print(" SUMMARY")
    print("="*70)
    
    if success1:
        print("✅ Added batch_update_emma_mason_raw method to google_sheets.py")
    else:
        print("❌ Failed to add method to google_sheets.py (may exist already)")
    
    if success2:
        print("✅ Added call to batch_update_emma_mason_raw in main.py")
    else:
        print("❌ Failed to add call to main.py (may exist already)")
    
    print()
    
    if success1 and success2:
        print("🎉 EMMA MASON RAW SHEET FEATURE ADDED!")
        print()
        print("Next steps:")
        print("  1. Run repricer: python run_repricer.py")
        print("  2. Check Google Sheets for new 'Emma_Mason_Raw' sheet")
        print("  3. Compare URLs/IDs with main Data sheet")
        print("  4. Debug any matching issues")
        print()
        print("Sheet structure:")
        print("  ID | URL | Price | Brand | Scraped At")
        print()
        print(f"⚠️  Backup saved to: {backup_dir}/")
    else:
        print("⚠️  Some changes could not be applied.")
        print("   Check warnings above and apply manually if needed.")
    
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
