"""
Google Sheets API клієнт для Furniture Repricer
FINAL VERSION v3.0 - FIXED ALL ISSUES:
✅ URL normalization for Emma Mason matching
✅ Price conversion for competitor data  
✅ Competitors sheet - FIXED structure (SKU in column A)
✅ Price_History - FIXED structure (Date, SKU, URL, Old Price, New Price, Change)
✅ TRUE batch operations (no loops!)
"""

import gspread
from google.oauth2.service_account import Credentials
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
import time
from pathlib import Path
from urllib.parse import urlparse, urlunparse

from .logger import get_logger

logger = get_logger("google_sheets")


def normalize_url(url: str) -> str:
    """
    Нормалізувати URL для порівняння
    
    Приклади:
    - https://emmamason.com/product-name/ → emmamason.com/product-name
    - https://emmamason.com/product-name?param=1 → emmamason.com/product-name
    - HTTPS://EMMAMASON.COM/Product-Name → emmamason.com/product-name
    """
    if not url:
        return ""
    
    try:
        # Parse URL
        parsed = urlparse(url.strip())
        
        # Взяти domain + path (без scheme, params, fragment)
        # netloc = domain, path = /product-name
        domain = parsed.netloc.lower()
        path = parsed.path.lower()
        
        # Видалити trailing slash
        path = path.rstrip('/')
        
        # Повернути domain/path
        normalized = f"{domain}{path}"
        
        return normalized
        
    except Exception as e:
        logger.debug(f"Failed to normalize URL '{url}': {e}")
        return url.strip().lower()


class GoogleSheetsClient:
    """Клієнт для роботи з Google Sheets"""
    
    # Scopes для доступу
    SCOPES = [
        'https://www.googleapis.com/auth/spreadsheets',
        'https://www.googleapis.com/auth/drive'
    ]
    
    def __init__(self, credentials_path: str):
        """
        Ініціалізація клієнта
        
        Args:
            credentials_path: Шлях до JSON файлу з credentials
        """
        self.credentials_path = Path(credentials_path)
        self.client = None
        self._connect()
    
    def _connect(self):
        """Підключитись до Google Sheets API"""
        try:
            logger.info(f"Connecting to Google Sheets API...")
            
            if not self.credentials_path.exists():
                raise FileNotFoundError(f"Credentials file not found: {self.credentials_path}")
            
            credentials = Credentials.from_service_account_file(
                str(self.credentials_path),
                scopes=self.SCOPES
            )
            
            self.client = gspread.authorize(credentials)
            logger.info("✓ Connected to Google Sheets API")
            
        except Exception as e:
            logger.error(f"Failed to connect to Google Sheets: {e}")
            raise
    
    def test_connection(self) -> bool:
        """
        Перевірити підключення
        
        Returns:
            True якщо підключення працює
        """
        try:
            # Просто перевіряємо що можемо отримати список таблиць
            self.client.openall()
            logger.info("✓ Connection test passed")
            return True
        except Exception as e:
            logger.error(f"Connection test failed: {e}")
            return False
    
    def open_sheet(self, sheet_id: str, worksheet_name: str = None) -> gspread.Worksheet:
        """
        Відкрити таблицю
        
        Args:
            sheet_id: ID таблиці
            worksheet_name: Назва аркушу (опціонально, якщо None - перший аркуш)
        
        Returns:
            Worksheet object
        """
        try:
            spreadsheet = self.client.open_by_key(sheet_id)
            
            if worksheet_name:
                worksheet = spreadsheet.worksheet(worksheet_name)
            else:
                worksheet = spreadsheet.sheet1
            
            logger.debug(f"Opened sheet: {sheet_id}/{worksheet_name or 'first'}")
            return worksheet
            
        except gspread.exceptions.WorksheetNotFound:
            logger.error(f"Worksheet '{worksheet_name}' not found in sheet {sheet_id}")
            raise
        except Exception as e:
            logger.error(f"Failed to open sheet: {e}")
            raise
    
    def read_all_data(self, sheet_id: str, worksheet_name: str = None) -> List[List[str]]:
        """
        Прочитати всі дані з аркушу
        
        Args:
            sheet_id: ID таблиці
            worksheet_name: Назва аркушу
        
        Returns:
            Список рядків (кожен рядок - список значень)
        """
        try:
            worksheet = self.open_sheet(sheet_id, worksheet_name)
            data = worksheet.get_all_values()
            logger.info(f"Read {len(data)} rows from {worksheet_name or 'sheet'}")
            return data
        except Exception as e:
            logger.error(f"Failed to read data: {e}")
            raise
    
    def read_as_dict(self, sheet_id: str, worksheet_name: str = None) -> List[Dict[str, str]]:
        """
        Прочитати дані як список словників (header = keys)
        
        Args:
            sheet_id: ID таблиці
            worksheet_name: Назва аркушу
        
        Returns:
            Список словників {header: value}
        """
        try:
            worksheet = self.open_sheet(sheet_id, worksheet_name)
            data = worksheet.get_all_records()
            logger.info(f"Read {len(data)} records from {worksheet_name or 'sheet'}")
            return data
        except Exception as e:
            logger.error(f"Failed to read records: {e}")
            raise
    
    def write_row(self, sheet_id: str, row_number: int, values: List[Any], 
                    worksheet_name: str = None):
        """
        Записати рядок у таблицю
        
        Args:
            sheet_id: ID таблиці
            row_number: Номер рядка (1-based)
            values: Список значень
            worksheet_name: Назва аркушу
        """
        try:
            worksheet = self.open_sheet(sheet_id, worksheet_name)
            
            # Конвертувати значення у строки
            values_str = [str(v) if v is not None else "" for v in values]
            
            # Записати рядок
            range_name = f"A{row_number}"
            worksheet.update(range_name, [values_str], value_input_option='USER_ENTERED')
            
            logger.debug(f"Wrote row {row_number}")
            
        except Exception as e:
            logger.error(f"Failed to write row {row_number}: {e}")
            raise
    
    def update_cell(self, sheet_id: str, row: int, col: int, value: Any,
                    worksheet_name: str = None):
        """
        Оновити одну клітинку
        
        Args:
            sheet_id: ID таблиці
            row: Номер рядка (1-based)
            col: Номер колонки (1-based)
            value: Значення
            worksheet_name: Назва аркушу
        """
        try:
            worksheet = self.open_sheet(sheet_id, worksheet_name)
            worksheet.update_cell(row, col, value)
            logger.debug(f"Updated cell ({row}, {col})")
        except Exception as e:
            logger.error(f"Failed to update cell: {e}")
            raise
    
    def update_range(self, sheet_id: str, range_name: str, values: List[List[Any]],
                    worksheet_name: str = None):
        """
        Оновити діапазон клітинок
        
        Args:
            sheet_id: ID таблиці
            range_name: Діапазон (напр. "A2:D10")
            values: 2D список значень
            worksheet_name: Назва аркушу
        """
        try:
            worksheet = self.open_sheet(sheet_id, worksheet_name)
            worksheet.update(range_name, values, value_input_option='USER_ENTERED')
            logger.info(f"Updated range {range_name}")
        except Exception as e:
            logger.error(f"Failed to update range: {e}")
            raise
    
    def batch_update(self, sheet_id: str, updates: List[Dict], worksheet_name: str = None):
        """
        Пакетне оновлення (ефективніше для багатьох змін)
        
        Args:
            sheet_id: ID таблиці
            updates: Список словників {'range': 'A1:B2', 'values': [[1,2],[3,4]]}
            worksheet_name: Назва аркушу
        """
        try:
            worksheet = self.open_sheet(sheet_id, worksheet_name)
            
            # Підготувати дані для batch update
            data = []
            for update in updates:
                data.append({
                    'range': update['range'],
                    'values': update['values']
                })
            
            # Виконати batch update
            worksheet.batch_update(data, value_input_option='USER_ENTERED')
            logger.info(f"Batch updated {len(updates)} ranges")
            
        except Exception as e:
            logger.error(f"Failed batch update: {e}")
            raise
    
    def append_row(self, sheet_id: str, values: List[Any], worksheet_name: str = None):
        """
        Додати новий рядок в кінець таблиці
        
        Args:
            sheet_id: ID таблиці
            values: Список значень
            worksheet_name: Назва аркушу
        """
        try:
            worksheet = self.open_sheet(sheet_id, worksheet_name)
            values_str = [str(v) if v is not None else "" for v in values]
            worksheet.append_row(values_str, value_input_option='USER_ENTERED')
            logger.debug(f"Appended row with {len(values)} values")
        except Exception as e:
            logger.error(f"Failed to append row: {e}")
            raise
    
    def find_row_by_sku(self, sheet_id: str, sku: str, worksheet_name: str = None,
                        sku_column: int = 1) -> Optional[int]:
        """
        Знайти номер рядка за SKU
        
        Args:
            sheet_id: ID таблиці
            sku: SKU для пошуку
            worksheet_name: Назва аркушу
            sku_column: Номер колонки з SKU (1-based)
        
        Returns:
            Номер рядка або None
        """
        try:
            worksheet = self.open_sheet(sheet_id, worksheet_name)
            
            # Отримати всі значення SKU колонки
            sku_values = worksheet.col_values(sku_column)
            
            # Шукати SKU (case-insensitive)
            sku_lower = sku.lower().strip()
            for i, cell_value in enumerate(sku_values, start=1):
                if cell_value.lower().strip() == sku_lower:
                    logger.debug(f"Found SKU '{sku}' at row {i}")
                    return i
            
            logger.debug(f"SKU '{sku}' not found")
            return None
            
        except Exception as e:
            logger.error(f"Failed to find SKU: {e}")
            return None
    
    def get_row_by_number(self, sheet_id: str, row_number: int, 
                        worksheet_name: str = None) -> List[str]:
        """
        Отримати рядок за номером
        
        Args:
            sheet_id: ID таблиці
            row_number: Номер рядка (1-based)
            worksheet_name: Назва аркушу
        
        Returns:
            Список значень рядка
        """
        try:
            worksheet = self.open_sheet(sheet_id, worksheet_name)
            row_data = worksheet.row_values(row_number)
            return row_data
        except Exception as e:
            logger.error(f"Failed to get row {row_number}: {e}")
            raise
    
    def create_worksheet(self, sheet_id: str, title: str, rows: int = 1000, 
                        cols: int = 26) -> gspread.Worksheet:
        """
        Створити новий аркуш у таблиці
        
        Args:
            sheet_id: ID таблиці
            title: Назва нового аркушу
            rows: Кількість рядків
            cols: Кількість колонок
        
        Returns:
            Worksheet object
        """
        try:
            spreadsheet = self.client.open_by_key(sheet_id)
            worksheet = spreadsheet.add_worksheet(title=title, rows=rows, cols=cols)
            logger.info(f"Created worksheet '{title}'")
            return worksheet
        except Exception as e:
            logger.error(f"Failed to create worksheet: {e}")
            raise
    
    def worksheet_exists(self, sheet_id: str, worksheet_name: str) -> bool:
        """
        Перевірити чи існує аркуш
        
        Args:
            sheet_id: ID таблиці
            worksheet_name: Назва аркушу
        
        Returns:
            True якщо існує
        """
        try:
            spreadsheet = self.client.open_by_key(sheet_id)
            worksheet_list = [ws.title for ws in spreadsheet.worksheets()]
            return worksheet_name in worksheet_list
        except Exception as e:
            logger.error(f"Failed to check worksheet existence: {e}")
            return False
    
    def rate_limit_delay(self, delay: float = 1.0):
        """
        Затримка для уникнення rate limit
        
        Args:
            delay: Час затримки в секундах
        """
        time.sleep(delay)


class RepricerSheetsManager:
    """Спеціалізований менеджер для таблиць репрайсера"""
    
    def __init__(self, client: GoogleSheetsClient, config: dict):
        """
        Ініціалізація менеджера
        
        Args:
            client: GoogleSheetsClient instance
            config: Конфігурація таблиць
        """
        self.client = client
        self.config = config
        self.logger = get_logger("sheets_manager")
        
        # Cache для row numbers (оптимізація rate limit)
        self.row_cache = {}
    
    def get_main_data(self) -> List[Dict[str, Any]]:
        """
        Отримати дані з основної таблиці
        
        ✅ FIXED v4.0:
        - Конвертує числові поля в float ОДРАЗУ
        - Більше ніяких проблем з комою!
        - Всі ціни вже правильні float після цього методу
        """
        sheet_id = self.config['main_sheet']['id']
        sheet_name = self.config['main_sheet']['name']
        
        self.logger.info("Loading data from Google Sheets...")
        
        # Прочитати сирі дані
        raw_data = self.client.read_all_data(sheet_id, sheet_name)
        
        if not raw_data or len(raw_data) < 2:
            self.logger.warning("No data in main sheet")
            return []
        
        # Перший рядок - заголовки (пропускаємо)
        headers = raw_data[0]
        self.logger.debug(f"Headers: {headers[:12]}")  # Показати перші 12 колонок
        
        products = []
        conversion_errors = 0
        
        for idx, row in enumerate(raw_data[1:], start=2):  # Починаємо з рядка 2
            if not row or not row[0]:  # Пропустити порожні рядки
                continue
            
            try:
                # ✅ КЛЮЧОВИЙ МОМЕНТ: Конвертувати числа в float ОДРАЗУ!
                product = {
                    # String поля
                    'sku': str(row[0]).strip() if len(row) > 0 else '',
                    'brand': str(row[1]).strip() if len(row) > 1 else '',
                    
                    # ✅ ЧИСЛОВІ ПОЛЯ - конвертувати в float з обробкою коми!
                    'Our Cost': self._to_float(row[2] if len(row) > 2 else None),
                    'Our Sales Price': self._to_float(row[3] if len(row) > 3 else None),
                    'Suggest Sales Price': self._to_float(row[4] if len(row) > 4 else None),
                    
                    # URL
                    'our_url': str(row[5]).strip() if len(row) > 5 else '',
                    
                    # Competitor 1
                    'site1_price': self._to_float(row[6] if len(row) > 6 else None),
                    'site1_url': str(row[7]).strip() if len(row) > 7 else '',
                    
                    # Competitor 2
                    'site2_price': self._to_float(row[8] if len(row) > 8 else None),
                    'site2_url': str(row[9]).strip() if len(row) > 9 else '',
                    
                    # Competitor 3
                    'site3_price': self._to_float(row[10] if len(row) > 10 else None),
                    'site3_url': str(row[11]).strip() if len(row) > 11 else '',
                    
                    # Metadata
                    'row_number': idx,  # Зберегти номер рядка для оновлення
                }
                
                products.append(product)
                
            except Exception as e:
                self.logger.error(f"Failed to parse row {idx}: {e}")
                conversion_errors += 1
                continue
        
        self.logger.info(f"✓ Loaded {len(products)} products from Google Sheets")
        
        if conversion_errors > 0:
            self.logger.warning(f"⚠️ Had {conversion_errors} conversion errors")
        
        # ✅ ДІАГНОСТИКА: Показати приклад що все правильно
        if products:
            sample = products[0]
            self.logger.info("Sample product (after conversion):")
            self.logger.info(f"  SKU: {sample['sku']}")
            self.logger.info(f"  Our Cost: {sample['Our Cost']:.2f} (type: {type(sample['Our Cost']).__name__})")
            self.logger.info(f"  Our Sales Price: {sample['Our Sales Price']:.2f} (type: {type(sample['Our Sales Price']).__name__})")
            
            # Перевірка що всі ціни float
            if not isinstance(sample['Our Cost'], float):
                self.logger.error("❌ Our Cost is NOT float! Still has conversion problem!")
            else:
                self.logger.info("✓ All prices are proper float types")
        
        return products
    
    def update_product_prices(self, sku: str, prices: Dict[str, Any]) -> bool:
        """
        Оновити ціни товару
        
        Args:
            sku: SKU товару
            prices: Словник з цінами {
                'our_price': 100.0,
                'site1_price': 95.0,
                'site1_url': 'http://...',
                'suggest_price': 94.0,
                ...
            }
        
        Returns:
            True якщо успішно
        """
        try:
            sheet_id = self.config['main_sheet']['id']
            sheet_name = self.config['main_sheet']['name']
            
            # Використати кеш для row_num (оптимізація!)
            if sku in self.row_cache:
                row_num = self.row_cache[sku]
            else:
                # Затримка перед пошуком (rate limit protection)
                time.sleep(0.5)
                
                row_num = self.client.find_row_by_sku(sheet_id, sku, sheet_name)
                
                if row_num is None:
                    self.logger.warning(f"SKU {sku} not found in main sheet")
                    return False
                
                # Зберегти в кеш
                self.row_cache[sku] = row_num
            
            # Підготувати оновлення
            # Припускаємо структуру: SKU, Brand, Our Cost, Our Sales Price, Suggest Sales Price,
            # Our URL, Site 1 Price, Site 1 URL, Site 2 Price, Site 2 URL, Site 3 Price, Site 3 URL, ...
            
            updates = []
            
            # Our Sales Price (колонка D = 4)
            if 'our_price' in prices:
                updates.append({
                    'range': f'D{row_num}',
                    'values': [[prices['our_price']]]
                })
            
            # Suggest Sales Price (колонка E = 5)
            if 'suggest_price' in prices:
                updates.append({
                    'range': f'E{row_num}',
                    'values': [[prices['suggest_price']]]
                })
            
            # Site 1 (колонки G, H = 7, 8)
            if 'site1_price' in prices:
                updates.append({
                    'range': f'G{row_num}',
                    'values': [[prices['site1_price']]]
                })
            if 'site1_url' in prices:
                updates.append({
                    'range': f'H{row_num}',
                    'values': [[prices['site1_url']]]
                })
            
            # Site 2 (колонки I, J = 9, 10)
            if 'site2_price' in prices:
                updates.append({
                    'range': f'I{row_num}',
                    'values': [[prices['site2_price']]]
                })
            if 'site2_url' in prices:
                updates.append({
                    'range': f'J{row_num}',
                    'values': [[prices['site2_url']]]
                })
            
            # Site 3 (колонки K, L = 11, 12)
            if 'site3_price' in prices:
                updates.append({
                    'range': f'K{row_num}',
                    'values': [[prices['site3_price']]]
                })
            if 'site3_url' in prices:
                updates.append({
                    'range': f'L{row_num}',
                    'values': [[prices['site3_url']]]
                })
            
            # Last update (остання колонка)
            updates.append({
                'range': f'Q{row_num}',  # Припускаємо колонка Q
                'values': [[datetime.now().strftime('%Y-%m-%d %H:%M:%S')]]
            })
            
            # Виконати batch update
            if updates:
                time.sleep(0.3)  # Rate limit protection
                self.client.batch_update(sheet_id, updates, sheet_name)
                self.logger.info(f"Updated prices for SKU {sku}")
                return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"Failed to update prices for SKU {sku}: {e}")
            return False

    
    def batch_update_all(self, products: List[Dict]) -> int:
        """
        Батчити всі оновлення разом (НАБАГАТО ШВИДШЕ!)
        
        ✅ FIXED v3.0:
        - Конвертує competitor prices в float ПЕРЕД записом
        - Підтримка дублюючих SKU
        - Підтримка integer SKU
        """
        self.logger.info(f"Batch updating {len(products)} products...")
        
        sheet_id = self.config['main_sheet']['id']
        sheet_name = self.config['main_sheet']['name']
        
        # Спочатку завантажити всі row numbers одним запитом
        if not self.row_cache:
            self.logger.info("Building SKU row cache...")
            time.sleep(0.5)
            
            worksheet = self.client.open_sheet(sheet_id, sheet_name)
            all_data = worksheet.get_all_values()
            
            # ✅ Підтримка дублюючих SKU - зберігаємо LIST рядків
            from collections import defaultdict
            self.row_cache = defaultdict(list)  # SKU -> [row_num1, row_num2, ...]
            
            # Знайти колонку SKU (припускаємо A)
            for idx, row in enumerate(all_data, start=1):
                if row and row[0]:  # SKU в колонці A
                    # ✅ конвертуємо в string + strip для integer SKU
                    sku_str = str(row[0]).strip()
                    self.row_cache[sku_str].append(idx)
            
            total_rows = sum(len(rows) for rows in self.row_cache.values())
            unique_skus = len(self.row_cache)
            
            self.logger.info(f"Cached {unique_skus} unique SKUs ({total_rows} total rows)")
            
            # Показати приклади дублікатів
            duplicates = {sku: rows for sku, rows in self.row_cache.items() if len(rows) > 1}
            if duplicates:
                self.logger.warning(f"Found {len(duplicates)} SKUs with duplicates:")
                for sku, rows in list(duplicates.items())[:5]:  # Показати перші 5
                    self.logger.warning(f"  SKU '{sku}' appears in rows: {rows}")
        
        # Підготувати всі оновлення
        all_updates = []
        updated_count = 0
        skipped_count = 0
        
        for product in products:
            # ✅ конвертувати SKU в string для співставлення
            sku = product.get('sku') or product.get('SKU')
            if not sku:
                skipped_count += 1
                continue
            
            sku_str = str(sku).strip()  # ✅ Конвертувати в string
            
            if sku_str not in self.row_cache:
                self.logger.debug(f"SKU '{sku_str}' not found in cache")
                skipped_count += 1
                continue
            
            # ✅ Оновити ВСІ рядки з цим SKU (включно дублікати)
            row_numbers = self.row_cache[sku_str]
            
            prices = product.get('_prices_to_update', {})
            
            if not prices:
                skipped_count += 1
                continue
            
            # Додати updates для КОЖНОГО рядка з цим SKU
            for row_num in row_numbers:
                if 'suggest_price' in prices:
                    # ✅ Конвертувати в float якщо string
                    suggest_price = self._to_float(prices['suggest_price'])
                    all_updates.append({
                        'range': f'E{row_num}',
                        'values': [[suggest_price]]
                    })
                
                if 'site1_price' in prices:
                    # ✅ КРИТИЧНО: Конвертувати competitor price в float!
                    site1_price = self._to_float(prices.get('site1_price'))
                    site1_url = prices.get('site1_url', '')
                    
                    all_updates.append({
                        'range': f'G{row_num}:H{row_num}',
                        'values': [[site1_price, site1_url]]
                    })
                
                if 'site2_price' in prices:
                    # ✅ Конвертувати в float
                    site2_price = self._to_float(prices.get('site2_price'))
                    site2_url = prices.get('site2_url', '')
                    
                    all_updates.append({
                        'range': f'I{row_num}:J{row_num}',
                        'values': [[site2_price, site2_url]]
                    })
                
                if 'site3_price' in prices:
                    # ✅ Конвертувати в float
                    site3_price = self._to_float(prices.get('site3_price'))
                    site3_url = prices.get('site3_url', '')
                    
                    all_updates.append({
                        'range': f'K{row_num}:L{row_num}',
                        'values': [[site3_price, site3_url]]
                    })
                
                # Last update (колонка Q)
                all_updates.append({
                    'range': f'Q{row_num}',
                    'values': [[datetime.now().strftime('%Y-%m-%d %H:%M:%S')]]
                })
            
            updated_count += 1
        
        # Виконати ОДИН batch update для всіх товарів
        if all_updates:
            self.logger.info(f"Executing batch update: {len(all_updates)} changes for {updated_count} products")
            if skipped_count > 0:
                self.logger.info(f"Skipped: {skipped_count} products (no SKU or no prices)")
            time.sleep(0.5)
            
            # Google Sheets API дозволяє до 1000 updates за раз
            # Розбити на chunks по 500
            chunk_size = 500
            for i in range(0, len(all_updates), chunk_size):
                chunk = all_updates[i:i+chunk_size]
                self.client.batch_update(sheet_id, chunk, sheet_name)
                
                self.logger.info(f"  Updated chunk {i//chunk_size + 1}/{(len(all_updates)-1)//chunk_size + 1}")
                
                if i + chunk_size < len(all_updates):
                    time.sleep(1.0)  # Затримка між chunks
            
            self.logger.info(f"✓ Batch update completed: {updated_count} products")
        else:
            self.logger.warning("No updates to perform!")
        
        return updated_count
    
    def batch_add_to_history(self, history_records: List[Dict]) -> int:
        """
        ✅ FIXED v3.0: TRUE Batch запис Price History
        
        Структура: Date | SKU | URL | Old Price | New Price | Change
        
        Args:
            history_records: [{
                'sku': str,        # ← ДОДАНО SKU!
                'url': str,
                'old_price': float,
                'new_price': float
            }, ...]
        
        Returns:
            Кількість записаних рядків
        """
        if not history_records:
            return 0
        
        try:
            sheet_id = self.config['main_sheet']['id']
            history_name = 'Price_History'
            
            # ✅ 1. Перевірити worksheet ОДИН РАЗ (1 API call)
            if not self.client.worksheet_exists(sheet_id, history_name):
                self.logger.info(f"Creating Price_History worksheet...")
                ws = self.client.create_worksheet(sheet_id, history_name)
                # ✅ FIXED: Правильні headers
                headers = ['Date', 'SKU', 'URL', 'Old Price', 'New Price', 'Change']
                ws.update('A1', [headers])
                time.sleep(0.5)
            
            # ✅ 2. Підготувати ВСІ рядки
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            # Формат для batch update: рядки починаються з A2
            all_rows = []
            for record in history_records:
                old_price = record.get('old_price', 0)
                new_price = record.get('new_price', 0)
                change = new_price - old_price if old_price else 0
                
                row = [
                    timestamp,
                    record.get('sku', ''),      # ✅ ДОДАНО SKU!
                    record.get('url', ''),
                    old_price,
                    new_price,
                    change
                ]
                all_rows.append(row)
            
            # ✅ 3. Записати ВСЕ одним batch update (1 API call)
            if all_rows:
                time.sleep(0.5)
                worksheet = self.client.open_sheet(sheet_id, history_name)
                
                # Визначити початковий рядок (після header)
                existing_data = worksheet.get_all_values()
                start_row = len(existing_data) + 1
                end_row = start_row + len(all_rows) - 1
                
                # Update одним range
                range_name = f'A{start_row}:F{end_row}'
                worksheet.update(range_name, all_rows, value_input_option='USER_ENTERED')
                
                self.logger.info(f"✓ Added {len(all_rows)} records to Price_History")
                return len(all_rows)
            
            return 0
            
        except Exception as e:
            self.logger.error(f"Failed to batch add price history: {e}", exc_info=True)
            return 0

    def update_emma_mason_data(self, url: str, emma_id: str, new_price: float) -> bool:
        """
        Оновити дані Emma Mason для товару по URL
        
        Args:
            url: URL товару (для пошуку рядка)
            emma_id: ID з Emma Mason
            new_price: Нова ціна
        
        Returns:
            True якщо успішно
        """
        try:
            sheet_id = self.config['main_sheet']['id']
            sheet_name = self.config['main_sheet']['name']
            
            # Знайти рядок по URL
            time.sleep(0.5)
            worksheet = self.client.open_sheet(sheet_id, sheet_name)
            
            # Отримати всі URL (колонка F = Our URL)
            all_urls = worksheet.col_values(6)  # F = 6
            
            # Знайти індекс
            url_normalized = url.strip().lower()
            row_num = None
            
            for idx, cell_url in enumerate(all_urls, start=1):
                if cell_url.strip().lower() == url_normalized:
                    row_num = idx
                    break
            
            if not row_num:
                self.logger.warning(f"URL not found in sheet: {url[:60]}")
                return False
            
            # Отримати стару ціну (Our Sales Price = колонка D)
            old_price_cell = worksheet.cell(row_num, 4).value  # D = 4
            old_price = float(old_price_cell) if old_price_cell else 0.0
            
            # Підготувати оновлення
            updates = []
            
            # Our Sales Price (колонка D = 4)
            updates.append({
                'range': f'D{row_num}',
                'values': [[new_price]]
            })
            
            # ID from emmamason (колонка R = 18)
            updates.append({
                'range': f'R{row_num}',
                'values': [[emma_id]]
            })
            
            # Last update (колонка Q = 17)
            updates.append({
                'range': f'Q{row_num}',
                'values': [[datetime.now().strftime('%Y-%m-%d %H:%M:%S')]]
            })
            
            # Виконати batch update
            if updates:
                time.sleep(0.3)
                self.client.batch_update(sheet_id, updates, sheet_name)
                self.logger.info(f"Updated Emma Mason data for row {row_num}: ${old_price} -> ${new_price}")
                
                return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"Failed to update Emma Mason data: {e}")
            return False

    def batch_update_emma_mason(self, scraped_products: List[Dict]) -> int:
        """
        Batch оновлення для Emma Mason товарів
        
        ✅ FIXED v3.0:
        - URL normalization
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
            
            # ✅ Створити словник з НОРМАЛІЗОВАНИМИ URL + SKU
            url_to_row = {}
            for idx, row in enumerate(all_data, start=1):
                if len(row) > 5:  # F = index 5 (0-based)
                    sku = row[0] if len(row) > 0 else ''  # A = SKU
                    url_raw = row[5].strip()  # F = Our URL
                    if url_raw:
                        url_normalized = normalize_url(url_raw)
                        url_to_row[url_normalized] = {
                            'row_num': idx,
                            'sku': sku,  # ✅ ЗБЕРЕГТИ SKU!
                            'old_price': row[3] if len(row) > 3 else '',  # D = Our Sales Price
                            'original_url': url_raw
                        }
            
            self.logger.info(f"Loaded {len(url_to_row)} URLs from sheet (normalized)")
            
            # Знайти співпадіння та підготувати оновлення
            all_updates = []
            updated_count = 0
            history_records = []
            no_match_count = 0
            price_conversion_errors = 0
            
            for product in scraped_products:
                url_raw = product.get('url', '').strip()
                emma_id = product.get('id', '')
                price_raw = product.get('price', '')
                
                if not url_raw:
                    no_match_count += 1
                    continue
                
                # ✅ Нормалізувати URL для matching
                url_normalized = normalize_url(url_raw)
                
                if url_normalized not in url_to_row:
                    no_match_count += 1
                    continue
                
                row_info = url_to_row[url_normalized]
                row_num = row_info['row_num']
                sku = row_info['sku']  # ✅ ОТРИМАТИ SKU!
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
                
                # Our Sales Price (D = 4)
                all_updates.append({
                    'range': f'D{row_num}',
                    'values': [[new_price]]
                })
                
                # ID from emmamason (R = 18)
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
                        'sku': sku,  # ✅ ДОДАНО SKU!
                        'url': url_raw,
                        'old_price': old_price,
                        'new_price': new_price
                    })
            
            # ✅ Звіт про matching
            self.logger.info("="*60)
            self.logger.info("EMMA MASON MATCHING RESULTS:")
            self.logger.info(f"  Total products from scraper: {len(scraped_products)}")
            self.logger.info(f"  URLs in sheet: {len(url_to_row)}")
            self.logger.info(f"  Matched: {updated_count}")
            self.logger.info(f"  No match: {no_match_count}")
            self.logger.info(f"  Price conversion errors: {price_conversion_errors}")
            self.logger.info(f"  Match rate: {updated_count/len(scraped_products)*100:.1f}%")
            self.logger.info("="*60)
            
            # Виконати batch update
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

    def batch_update_competitors_sheet(self, products: List[Dict]) -> int:
        """
        ✅ FIXED v4.0: Оновити аркуш "Competitors"
        
        Структура: Site 1 SKU | Site 1 Price | Site 1 URL | Site 2 SKU | Site 2 Price | Site 2 URL | Site 3 SKU | Site 3 Price | Site 3 URL
        
        ⚠️ БЕЗ колонки SKU товару! Тільки дані конкурентів!
        
        Args:
            products: Список товарів з competitor data
        
        Returns:
            Кількість оновлених рядків
        """
        try:
            sheet_id = self.config['main_sheet']['id']
            competitors_sheet = "Competitors"
            
            self.logger.info(f"Updating Competitors sheet for {len(products)} products...")
            
            # Перевірити чи існує аркуш
            if not self.client.worksheet_exists(sheet_id, competitors_sheet):
                self.logger.info("Creating Competitors worksheet...")
                ws = self.client.create_worksheet(sheet_id, competitors_sheet, rows=10000, cols=9)
                
                # ✅ FIXED v4.0: Тільки дані конкурентів (БЕЗ SKU товару)
                headers = [
                    'Site 1 SKU',    # A
                    'Site 1 Price',  # B
                    'Site 1 URL',    # C
                    'Site 2 SKU',    # D
                    'Site 2 Price',  # E
                    'Site 2 URL',    # F
                    'Site 3 SKU',    # G
                    'Site 3 Price',  # H
                    'Site 3 URL',    # I
                ]
                ws.update('A1', [headers])
                time.sleep(0.5)
            
            # Завантажити існуючі дані
            time.sleep(0.5)
            worksheet = self.client.open_sheet(sheet_id, competitors_sheet)
            all_data = worksheet.get_all_values()
            
            # Підготувати batch update
            # Стратегія: append нові рядки (не оновлюємо існуючі, бо немає унікального ключа)
            new_rows = []
            
            for product in products:
                # ✅ Дані конкурентів (конвертувати в float для чисел!)
                site1_sku = product.get('site1_sku', '')
                site1_price = self._to_float(product.get('site1_price'))
                site1_url = product.get('site1_url', '')
                
                site2_sku = product.get('site2_sku', '')
                site2_price = self._to_float(product.get('site2_price'))
                site2_url = product.get('site2_url', '')
                
                site3_sku = product.get('site3_sku', '')
                site3_price = self._to_float(product.get('site3_price'))
                site3_url = product.get('site3_url', '')
                
                # Якщо немає жодних даних конкурентів - пропустити
                if not any([site1_sku, site2_sku, site3_sku]):
                    continue
                
                # ✅ FIXED: Тільки дані конкурентів (БЕЗ SKU товару!)
                row_data = [
                    site1_sku,    # A
                    site1_price,  # B - як ЧИСЛО!
                    site1_url,    # C
                    site2_sku,    # D
                    site2_price,  # E - як ЧИСЛО!
                    site2_url,    # F
                    site3_sku,    # G
                    site3_price,  # H - як ЧИСЛО!
                    site3_url     # I
                ]
                
                new_rows.append(row_data)
            
            # ✅ Додати нові рядки одним batch update!
            if new_rows:
                self.logger.info(f"Adding {len(new_rows)} rows to Competitors sheet (batch mode)...")
                
                # Визначити початковий рядок
                existing_data = worksheet.get_all_values()
                start_row = len(existing_data) + 1
                end_row = start_row + len(new_rows) - 1
                
                # Update одним range з USER_ENTERED для правильного форматування чисел
                range_name = f'A{start_row}:I{end_row}'
                worksheet.update(range_name, new_rows, value_input_option='USER_ENTERED')
                
                self.logger.info(f"✓ Competitors sheet updated: {len(new_rows)} rows added")
                return len(new_rows)
            else:
                self.logger.info("No competitor data to add")
                return 0
            
        except Exception as e:
            self.logger.error(f"Failed to update Competitors sheet: {e}", exc_info=True)
            return 0

    def _to_float(self, value, default: float = 0.0) -> float:
        """
        Конвертувати значення в float з обробкою різних форматів
        
        ✅ ПРАВИЛЬНЕ РІШЕННЯ замість костилів!
        
        Підтримка:
        - "507.66" (крапка)
        - "507,66" (кома - європейський формат) ✅
        - "507 66" (пробіл)
        - 507.66 (вже float)
        - 507 (int)
        - "" або None (повертає default)
        """
        if value is None or value == '':
            return default
        
        # Якщо вже число
        if isinstance(value, (int, float)):
            return float(value)
        
        # Якщо string
        if isinstance(value, str):
            try:
                # Прибрати пробіли
                cleaned = value.strip()
                
                if not cleaned:
                    return default
                
                # ✅ КЛЮЧОВИЙ МОМЕНТ: Замінити кому на крапку
                cleaned = cleaned.replace(',', '.')
                
                # Прибрати пробіли всередині (для "1 000.50")
                cleaned = cleaned.replace(' ', '')
                
                # Прибрати $ якщо є
                cleaned = cleaned.replace('$', '')
                
                # Конвертувати
                result = float(cleaned)
                
                return result
                
            except (ValueError, TypeError) as e:
                self.logger.warning(
                    f"Failed to convert '{value}' to float: {e}. Using default: {default}"
                )
                return default
        
        # Інший тип - спробувати
        try:
            return float(value)
        except:
            self.logger.warning(f"Cannot convert {type(value)} '{value}' to float")
            return default
