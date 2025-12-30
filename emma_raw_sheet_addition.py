"""
ДОДАВАННЯ DEBUG АРКУШУ "Emma_Mason_Raw"

Цей код додає метод для збереження RAW даних Emma Mason в окремий аркуш
для діагностики matching проблем.

ФАЙЛ: app/modules/google_sheets.py
ДОДАТИ МЕТОД в клас RepricerSheetsManager (після batch_update_competitors_raw)
"""

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


# ============================================================
# ЯК ДОДАТИ ДО ФАЙЛУ:
# ============================================================
"""
1. Відкрити app/modules/google_sheets.py
2. Знайти метод batch_update_competitors_raw (біля рядка 670-750)
3. ПІСЛЯ цього методу (перед закриваючою дужкою класу) вставити новий метод
4. Зберегти файл
"""

# ============================================================
# ДОДАТИ ВИКЛИК В app/main.py:
# ============================================================
"""
ФАЙЛ: app/main.py
МЕТОД: _scrape_and_update_emma_mason (біля рядка 195)

ЗНАЙТИ:
-------
            # Batch update
            if emma_products and not self.runtime_config.get('dry_run'):
                updated = self.sheets_manager.batch_update_emma_mason(emma_products)
                self.logger.info(f"✓ Emma Mason updated: {updated} products")

ЗАМІНИТИ НА:
------------
            # Batch update
            if emma_products and not self.runtime_config.get('dry_run'):
                # ✅ DEBUG: Зберегти RAW дані в окремий аркуш
                raw_saved = self.sheets_manager.batch_update_emma_mason_raw(emma_products)
                self.logger.info(f"✓ Emma Mason RAW saved: {raw_saved} products")
                
                # Оновити основну таблицю
                updated = self.sheets_manager.batch_update_emma_mason(emma_products)
                self.logger.info(f"✓ Emma Mason updated: {updated} products")
"""

# ============================================================
# РЕЗУЛЬТАТ:
# ============================================================
"""
Після виконання з'явиться новий аркуш "Emma_Mason_Raw":

┌──────────┬───────────────────────────────┬─────────┬──────────────┬─────────────────────┐
│ ID       │ URL                           │ Price   │ Brand        │ Scraped At          │
├──────────┼───────────────────────────────┼─────────┼──────────────┼─────────────────────┤
│ 12345    │ emmamason.com/product-1.html  │ 499.00  │ ACME         │ 2025-12-29 10:30:00 │
│ 12346    │ emmamason.com/product-2.html  │ 799.00  │ Steve Silver │ 2025-12-29 10:30:00 │
│ 12347    │ emmamason.com/product-3.html  │ 1299.00 │ Legacy Class │ 2025-12-29 10:30:00 │
└──────────┴───────────────────────────────┴─────────┴──────────────┴─────────────────────┘

Це дозволить:
1. Побачити скільки товарів scraper збирає
2. Перевірити чи ціни правильно конвертуються
3. Порівняти URL з основної таблиці з URL з scraper
4. Діагностувати чому деякі товари не matchаться
"""
