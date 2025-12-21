"""
Google Sheets API клієнт для Furniture Repricer
Підтримує читання та запис даних у таблиці
"""

import gspread
from google.oauth2.service_account import Credentials
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
import time
from pathlib import Path

from .logger import get_logger

logger = get_logger("google_sheets")


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
    
    def get_main_data(self) -> List[Dict[str, str]]:
        """Отримати дані з основної таблиці"""
        sheet_id = self.config['main_sheet']['id']
        sheet_name = self.config['main_sheet']['name']
        return self.client.read_as_dict(sheet_id, sheet_name)
    
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
    
    def add_to_history(self, sku: str, prices: Dict[str, Any]):
        """
        Додати запис в історію цін
        ВИМКНЕНО для production через rate limits
        """
        # ТИМЧАСОВО ВИМКНЕНО для уникнення rate limit
        self.logger.debug(f"History tracking disabled for SKU {sku}")
        return
        
        # ОРИГІНАЛЬНИЙ КОД (закоментовано):
        """
        try:
            sheet_id = self.config['main_sheet']['id']
            history_name = self.config.get('history_sheet', {}).get('name', 'Price_History')
            
            # Перевірити чи існує аркуш історії
            if not self.client.worksheet_exists(sheet_id, history_name):
                # Створити аркуш з заголовками
                ws = self.client.create_worksheet(sheet_id, history_name)
                headers = ['Date', 'SKU', 'Our Price', 'Site 1', 'Site 2', 'Site 3', 'Suggested']
                ws.update('A1', [headers])
            
            # Додати запис
            row = [
                datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                sku,
                prices.get('our_price', ''),
                prices.get('site1_price', ''),
                prices.get('site2_price', ''),
                prices.get('site3_price', ''),
                prices.get('suggest_price', '')
            ]
            
            self.client.append_row(sheet_id, row, history_name)
            
        except Exception as e:
            self.logger.error(f"Failed to add history for SKU {sku}: {e}")
        """
    
    def batch_update_all(self, products: List[Dict]) -> int:
        """
        Батчити всі оновлення разом (НАБАГАТО ШВИДШЕ!)
        
        ВИПРАВЛЕННЯ: Прибрано {sheet_name}! з усіх ranges
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
            
            # Знайти колонку SKU (припускаємо A)
            for idx, row in enumerate(all_data, start=1):
                if row and row[0]:  # SKU в колонці A
                    self.row_cache[row[0]] = idx
            
            self.logger.info(f"Cached {len(self.row_cache)} SKU row numbers")
        
        # Підготувати всі оновлення
        all_updates = []
        updated_count = 0
        
        for product in products:
            sku = product.get('sku') or product.get('SKU')
            if not sku or sku not in self.row_cache:
                continue
            
            row_num = self.row_cache[sku]
            prices = product.get('_prices_to_update', {})
            
            if not prices:
                continue
            
            # ✅ ВИПРАВЛЕНО: Прибрано {sheet_name}! з ranges
            # Worksheet вже знає свою назву, не треба дублювати
            
            if 'suggest_price' in prices:
                all_updates.append({
                    'range': f'E{row_num}',  # ✅ Було: f'{sheet_name}!E{row_num}'
                    'values': [[prices['suggest_price']]]
                })
            
            if 'site1_price' in prices:
                all_updates.append({
                    'range': f'G{row_num}:H{row_num}',  # ✅ Було: f'{sheet_name}!G{row_num}:H{row_num}'
                    'values': [[prices.get('site1_price'), prices.get('site1_url', '')]]
                })
            
            if 'site2_price' in prices:
                all_updates.append({
                    'range': f'I{row_num}:J{row_num}',  # ✅ Було: f'{sheet_name}!I{row_num}:J{row_num}'
                    'values': [[prices.get('site2_price'), prices.get('site2_url', '')]]
                })
            
            if 'site3_price' in prices:
                all_updates.append({
                    'range': f'K{row_num}:L{row_num}',  # ✅ Було: f'{sheet_name}!K{row_num}:L{row_num}'
                    'values': [[prices.get('site3_price'), prices.get('site3_url', '')]]
                })
            
            # Last update (колонка Q)
            all_updates.append({
                'range': f'Q{row_num}',  # ✅ Було: f'{sheet_name}!Q{row_num}'
                'values': [[datetime.now().strftime('%Y-%m-%d %H:%M:%S')]]
            })
            
            updated_count += 1
        
        # Виконати ОДИН batch update для всіх товарів
        if all_updates:
            self.logger.info(f"Executing batch update with {len(all_updates)} changes...")
            time.sleep(0.5)
            
            # Google Sheets API дозволяє до 1000 updates за раз
            # Розбити на chunks по 500
            chunk_size = 500
            for i in range(0, len(all_updates), chunk_size):
                chunk = all_updates[i:i+chunk_size]
                self.client.batch_update(sheet_id, chunk, sheet_name)  # ✅ Передаємо sheet_name тут
                
                if i + chunk_size < len(all_updates):
                    time.sleep(1.0)  # Затримка між chunks
            
            self.logger.info(f"✓ Batch update completed: {updated_count} products")
        
        return updated_count


if __name__ == "__main__":
    # Тестування
    print("Testing Google Sheets Client...")
    
    # Потрібен файл credentials.json для тесту
    # client = GoogleSheetsClient("./credentials/service_account.json")
    # print(f"Connection OK: {client.test_connection()}")
