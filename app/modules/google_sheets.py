"""
Google Sheets API client for Furniture Repricer
"""

import gspread
from google.oauth2.service_account import Credentials
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
import time
from pathlib import Path
from urllib.parse import urlparse, urlunparse

from .logger import get_logger

logger = get_logger("google_sheets")


def normalize_url(url: str) -> str:
    """
    Normalize URLs for comparison
    """
    if not url:
        return ""
    
    try:
        # Parse URL
        parsed = urlparse(url.strip())
        
        # Take domain + path (without schema, parameters, fragment)
        # netloc = domain, path = /product-name
        domain = parsed.netloc.lower()
        path = parsed.path.lower()
        
        # Remove trailing slash
        path = path.rstrip('/')
        
        # Return domain/path
        normalized = f"{domain}{path}"
        
        return normalized
        
    except Exception as e:
        logger.debug(f"Failed to normalize URL '{url}': {e}")
        return url.strip().lower()


class GoogleSheetsClient:
    """Client for working with Google Sheets"""
    
    # Scopes for access
    SCOPES = [
        'https://www.googleapis.com/auth/spreadsheets',
        'https://www.googleapis.com/auth/drive'
    ]
    
    def __init__(self, credentials_path: str):
        """
        Client initialization
        
        Args:
            credentials_path: Path to the JSON file with credentials
        """
        self.credentials_path = Path(credentials_path)
        self.client = None
        self._connect()
    
    def _connect(self):
        """Connect to Google Sheets API"""
        try:
            logger.info(f"Connecting to Google Sheets API...")
            
            if not self.credentials_path.exists():
                raise FileNotFoundError(f"Credentials file not found: {self.credentials_path}")
            
            credentials = Credentials.from_service_account_file(
                str(self.credentials_path),
                scopes=self.SCOPES
            )
            
            self.client = gspread.authorize(credentials)
            logger.info("[OK] Connected to Google Sheets API")
            
        except Exception as e:
            logger.error(f"Failed to connect to Google Sheets: {e}")
            raise
    
    def test_connection(self) -> bool:
        """
        Check the connection
        
        Returns:
            True if the connection is working
        """
        try:
            # Just checking what we can get a list of tables
            self.client.openall()
            logger.info("[OK] Connection test passed")
            return True
        except Exception as e:
            logger.error(f"Connection test failed: {e}")
            return False

    def open_sheet(self, sheet_id: str, worksheet_name: str = None) -> gspread.Worksheet:
        """
        Open table
        
        Args:
            sheet_id: Table ID
            worksheet_name: Sheet name (optional, if None - first sheet)
        
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
        Read all data from the sheet
        
        Args:
            sheet_id: Table ID
            worksheet_name: Worksheet name
        
        Returns:
            List of strings (each string is a list of values)
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
        Read data as a list of dictionaries (header = keys)
        
        Args:
            sheet_id: Table ID
            worksheet_name: Worksheet name
        
        Returns:
            List of dictionaries {header: value}
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
        Write a row to a table
        
        Args:
            sheet_id: Table ID
            row_number: Row number (1-based)
            values: List of values
            worksheet_name: Worksheet name
        """
        try:
            worksheet = self.open_sheet(sheet_id, worksheet_name)
            
            # Convert values to strings
            values_str = [str(v) if v is not None else "" for v in values]
            
            # write a line
            range_name = f"A{row_number}"
            worksheet.update(range_name, [values_str], value_input_option='RAW')
            
            logger.debug(f"Wrote row {row_number}")
            
        except Exception as e:
            logger.error(f"Failed to write row {row_number}: {e}")
            raise
    
    def update_cell(self, sheet_id: str, row: int, col: int, value: Any,
                    worksheet_name: str = None):
        """
        Update one cell
        
        Args:
            sheet_id: Table ID
            row: Row number (1-based)
            col: Column number (1-based)
            value: Value
            worksheet_name: Worksheet name
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
        Refresh cell range
        
        Args:
            sheet_id: Table ID
            range_name: Range (e.g., “A2:D10”)
            values: 2D list of values
            worksheet_name: Worksheet name
        """
        try:
            worksheet = self.open_sheet(sheet_id, worksheet_name)
            worksheet.update(range_name, values, value_input_option='RAW')
            logger.info(f"Updated range {range_name}")
        except Exception as e:
            logger.error(f"Failed to update range: {e}")
            raise
    
    def batch_update(self, sheet_id: str, updates: List[Dict], worksheet_name: str = None):
        """
        Batch update (more efficient for many changes))
        
        Args:
            sheet_id: Table ID
            updates: List of dictionaries {‘range’: ‘A1:B2’, ‘values’: [[1,2],[3,4]]}
            worksheet_name: Worksheet name
        """
        try:
            worksheet = self.open_sheet(sheet_id, worksheet_name)
            
            # Prepare data for batch update
            data = []
            for update in updates:
                data.append({
                    'range': update['range'],
                    'values': update['values']
                })
            
            # Perform a batch update
            worksheet.batch_update(data, value_input_option='RAW')
            logger.info(f"Batch updated {len(updates)} ranges")
            
        except Exception as e:
            logger.error(f"Failed batch update: {e}")
            raise
    
    def append_row(self, sheet_id: str, values: List[Any], worksheet_name: str = None):
        """
        Add a new row to the end of the table
        
        Args:
            sheet_id: Table ID
            values: List of values
            worksheet_name: Worksheet name
        """
        try:
            worksheet = self.open_sheet(sheet_id, worksheet_name)
            values_str = [str(v) if v is not None else "" for v in values]
            worksheet.append_row(values_str, value_input_option='RAW')
            logger.debug(f"Appended row with {len(values)} values")
        except Exception as e:
            logger.error(f"Failed to append row: {e}")
            raise
    
    def find_row_by_sku(self, sheet_id: str, sku: str, worksheet_name: str = None,
                        sku_column: int = 1) -> Optional[int]:
        """
        Find the line number by SKU
        
        Args:
            sheet_id: Table ID
            sku: SKU for search
            worksheet_name: Worksheet name
            sku_column: Column number with SKU (1-based)
        
        Returns:
            Row number or None
        """
        try:
            worksheet = self.open_sheet(sheet_id, worksheet_name)
            
            # Get all SKU values from the column
            sku_values = worksheet.col_values(sku_column)
            
            # Search SKU (case-insensitive)
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
        Get a string by number
        
        Args:
            sheet_id: Table ID
            row_number: Row number (1-based)
            worksheet_name: Worksheet name
        
        Returns:
            List of string values
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
        Create a new sheet in the table
        
        Args:
            sheet_id: Table ID
            title: Name of the new sheet
            rows: Number of rows
            cols: Number of columns
        
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
        Check if a sheet exists
        
        Args:
            sheet_id: Table ID
            worksheet_name: Sheet name
        
        Returns:
            True if it exists
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
        delay to avoid rate limit
        
        Args:
            delay: Delay time in seconds
        """
        time.sleep(delay)


class RepricerSheetsManager:
    """Specialized manager for repricer tables"""
    
    def __init__(self, client: GoogleSheetsClient, config: dict):
        """
        Initialization of the manager
        
        Args:
            client: GoogleSheetsClient instance
            config: Table configuration
        """
        self.client = client
        self.config = config
        self.logger = get_logger("sheets_manager")
        
        # Cache for row numbers (rate limit optimization)
        self.row_cache = {}

    def reset_filters(self, sheet_id: str, worksheet_name: str):
        """
        Reset all filters but KEEP the filter itself
        
        Args:
            sheet_id: Table ID
            worksheet_name: Sheet name
        """
        try:
            worksheet = self.client.open_sheet(sheet_id, worksheet_name)
            worksheet_id = worksheet._properties['sheetId']
            
            # Get current filter range
            all_data = worksheet.get_all_values()
            if not all_data:
                return
            
            num_rows = len(all_data)
            num_cols = len(all_data[0]) if all_data else 0
            
            # Prepare request to RESET filter
            # This sets filter but with no criteria (shows all data)
            requests = [{
                'setBasicFilter': {
                    'filter': {
                        'range': {
                            'sheetId': worksheet_id,
                            'startRowIndex': 0,
                            'endRowIndex': num_rows,
                            'startColumnIndex': 0,
                            'endColumnIndex': num_cols
                        },
                    }
                }
            }]
            
            spreadsheet = self.client.client.open_by_key(sheet_id)
            spreadsheet.batch_update({'requests': requests})
            
            logger.info(f"[OK] Reset filters on {worksheet_name} (filter icon remains)")
            
        except Exception as e:
            logger.error(f"Failed to reset filters: {e}")

    def get_main_data(self) -> List[Dict[str, Any]]:
        """
        Get data from the main table
        """
        sheet_id = self.config['main_sheet']['id']
        sheet_name = self.config['main_sheet']['name']
        
        self.logger.info("Loading data from Google Sheets...")
        
        # Read raw data
        raw_data = self.client.read_all_data(sheet_id, sheet_name)
        
        if not raw_data or len(raw_data) < 2:
            self.logger.warning("No data in main sheet")
            return []
        
        # The first line is the headers (skip this).
        headers = raw_data[0]
        self.logger.debug(f"Headers: {headers[:20]}")  # Show first 20 columns
        
        products = []
        conversion_errors = 0
        
        for idx, row in enumerate(raw_data[1:], start=2):  # Let's start with line 2
            if not row or not row[0]:  # Skip empty lines
                continue
            
            try:
                # KEY POINT: Convert numbers to float IMMEDIATELY!
                product = {
                    # String fields
                    'sku': str(row[0]).strip() if len(row) > 0 else '',
                    'brand': str(row[1]).strip() if len(row) > 1 else '',
                    
                    # NUMERIC FIELDS - convert to float with comma handling!
                    'Our Cost': self._to_float(row[2] if len(row) > 2 else None),
                    'Our Sales Price': self._to_float(row[3] if len(row) > 3 else None),
                    'Suggest Sales Price': self._to_float(row[4] if len(row) > 4 else None),
                    
                    # URL
                    'our_url': str(row[5]).strip() if len(row) > 5 else '',
                    
                    # Competitor 1 (Coleman)
                    'site1_price': self._to_float(row[6] if len(row) > 6 else None),
                    'site1_url': str(row[7]).strip() if len(row) > 7 else '',
                    
                    # Competitor 2 (1StopBedrooms)
                    'site2_price': self._to_float(row[8] if len(row) > 8 else None),
                    'site2_url': str(row[9]).strip() if len(row) > 9 else '',
                    
                    # Competitor 3 (AFA)
                    'site3_price': self._to_float(row[10] if len(row) > 10 else None),
                    'site3_url': str(row[11]).strip() if len(row) > 11 else '',
                    
                    # Site 4 (Future competitor)
                    'site4_price': self._to_float(row[12] if len(row) > 12 else None),
                    'site4_url': str(row[13]).strip() if len(row) > 13 else '',
                    
                    # Site 5 (Future competitor)
                    'site5_price': self._to_float(row[14] if len(row) > 14 else None),
                    'site5_url': str(row[15]).strip() if len(row) > 15 else '',
                    
                    # Competitors_SKU (column S = index 18)
                    'competitors_sku': str(row[18]).strip() if len(row) > 18 else '',
                    
                    # Metadata
                    'row_number': idx,  # keep the line number for updating
                }
                
                products.append(product)
                
            except Exception as e:
                self.logger.error(f"Failed to parse row {idx}: {e}")
                conversion_errors += 1
                continue
        
        self.logger.info(f"[OK] Loaded {len(products)} products from Google Sheets")
        
        if conversion_errors > 0:
            self.logger.warning(f"[!] Had {conversion_errors} conversion errors")
        
        # DIAGNOSTICS: Show an example that everything is correct
        if products:
            sample = products[0]
            # self.logger.info("Sample product (after conversion):")
            # self.logger.info(f"  SKU: {sample['sku']}")
            # self.logger.info(f"  Our Cost: {sample['Our Cost']:.2f} (type: {type(sample['Our Cost']).__name__})")
            # self.logger.info(f"  Competitors_SKU: '{sample['competitors_sku']}'")
            if sample.get('site4_url'):
                self.logger.info(f"  Site4 URL: {sample['site4_url']}")
            if sample.get('site5_url'):
                self.logger.info(f"  Site5 URL: {sample['site5_url']}")
        
        return products
    
    def update_product_prices(self, sku: str, prices: Dict[str, Any]) -> bool:
        """
        Update product prices
        
        Args:
            sku: Product SKU
            prices: Price list {
                'our_price': 100.0,
                'site1_price': 95.0,
                'site1_url': 'http://...',
                'suggest_price': 94.0,
                ...
            }
        
        Returns:
            True if successful
        """
        try:
            sheet_id = self.config['main_sheet']['id']
            sheet_name = self.config['main_sheet']['name']
            
            # Use cache for row_num (optimization!)
            if sku in self.row_cache:
                row_num = self.row_cache[sku]
            else:
                # Delay before search (rate limit protection)
                time.sleep(0.5)
                
                row_num = self.client.find_row_by_sku(sheet_id, sku, sheet_name)
                
                if row_num is None:
                    self.logger.warning(f"SKU {sku} not found in main sheet")
                    return False
                
                # Save to cache
                self.row_cache[sku] = row_num
            
            # Prepare updates
            # Assume structure: SKU, Brand, Our Cost, Our Sales Price, Suggest Sales Price,
            # Our URL, Site 1 Price, Site 1 URL, Site 2 Price, Site 2 URL, Site 3 Price, Site 3 URL, ...
            
            updates = []
            
            # Our Sales Price (D = 4)
            if 'our_price' in prices:
                updates.append({
                    'range': f'D{row_num}',
                    'values': [[prices['our_price']]]
                })
            
            # Suggest Sales Price (E = 5)
            if 'suggest_price' in prices:
                updates.append({
                    'range': f'E{row_num}',
                    'values': [[prices['suggest_price']]]
                })

            # Site 1 (G, H = 7, 8)
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

            # Site 2 (I, J = 9, 10)
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

            # Site 3 (K, L = 11, 12)
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

            # Last update (last column)
            updates.append({
                'range': f'Q{row_num}',  # Q
                'values': [[datetime.now().strftime('%Y-%m-%d %H:%M:%S')]]
            })

            # batch update
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
        Download all updates together
        
        - Converts competitor prices to float BEFORE recording
        - Support for duplicate SKUs
        - Support for integer SKUs
        """
        self.logger.info(f"Batch updating {len(products)} products...")
        
        sheet_id = self.config['main_sheet']['id']
        sheet_name = self.config['main_sheet']['name']
        
        self.reset_filters(sheet_id, sheet_name)  # Reset filters

        # First, download all row numbers with a single request.
        if not self.row_cache:
            self.logger.info("Building SKU row cache...")
            time.sleep(0.5)
            
            worksheet = self.client.open_sheet(sheet_id, sheet_name)
            all_data = worksheet.get_all_values()
            
            # Support for duplicate SKUs - storing a LIST of strings
            from collections import defaultdict
            self.row_cache = defaultdict(list)  # SKU -> [row_num1, row_num2, ...]
            
            # Find the SKU column (A)
            for idx, row in enumerate(all_data, start=1):
                if row and row[0]:  # SKU A
                    # convert to string + strip for integer SKU
                    sku_str = str(row[0]).strip()
                    self.row_cache[sku_str].append(idx)
            
            total_rows = sum(len(rows) for rows in self.row_cache.values())
            unique_skus = len(self.row_cache)
            
            self.logger.info(f"Cached {unique_skus} unique SKUs ({total_rows} total rows)")
            
            # Show examples of duplicates
            duplicates = {sku: rows for sku, rows in self.row_cache.items() if len(rows) > 1}
            if duplicates:
                self.logger.warning(f"Found {len(duplicates)} SKUs with duplicates:")
                for sku, rows in list(duplicates.items())[:5]:  # Show first 5
                    self.logger.warning(f"  SKU '{sku}' appears in rows: {rows}")
        
        # Prepare all updates
        all_updates = []
        updated_count = 0
        skipped_count = 0
        
        for product in products:
            # convert SKU to string for comparison
            sku = product.get('sku') or product.get('SKU')
            if not sku:
                skipped_count += 1
                continue
            
            sku_str = str(sku).strip()  # Convert to string
            
            if sku_str not in self.row_cache:
                self.logger.debug(f"SKU '{sku_str}' not found in cache")
                skipped_count += 1
                continue
            
            # Update ALL rows with this SKU (including duplicates)
            row_numbers = self.row_cache[sku_str]
            
            prices = product.get('_prices_to_update', {})
            
            if not prices:
                skipped_count += 1
                continue
            
            # Add updates for EVERY row with this SKU
            for row_num in row_numbers:
                if 'suggest_price' in prices:
                    # Convert to float if string
                    suggest_price = self._to_float(prices['suggest_price'])
                    all_updates.append({
                        'range': f'E{row_num}',
                        'values': [[suggest_price]]
                    })
                
                # Site 1 (Coleman)
            if 'site1_price' in prices:
                site1_price_raw = prices.get('site1_price')
                site1_price = self._to_float(site1_price_raw) if site1_price_raw else ''
                site1_url = prices.get('site1_url', '')
                site1_sku = prices.get('site1_sku', '')
                
                all_updates.append({
                    'range': f'G{row_num}:H{row_num}',
                    'values': [[site1_price, site1_url]]
                })
            
            # Site 2 (1StopBedrooms)
            if 'site2_price' in prices:
                site2_price_raw = prices.get('site2_price')
                site2_price = self._to_float(site2_price_raw) if site2_price_raw else ''
                site2_url = prices.get('site2_url', '')
                
                all_updates.append({
                    'range': f'I{row_num}:J{row_num}',
                    'values': [[site2_price, site2_url]]
                })
            
            # Site 3 (AFA)
            if 'site3_price' in prices:
                site3_price_raw = prices.get('site3_price')
                site3_price = self._to_float(site3_price_raw) if site3_price_raw else ''
                site3_url = prices.get('site3_url', '')
                
                all_updates.append({
                    'range': f'K{row_num}:L{row_num}',
                    'values': [[site3_price, site3_url]]
                })
            
            # Site 4 (Future)
            if 'site4_price' in prices:
                site4_price_raw = prices.get('site4_price')
                site4_price = self._to_float(site4_price_raw) if site4_price_raw else ''
                site4_url = prices.get('site4_url', '')
                
                all_updates.append({
                    'range': f'M{row_num}:N{row_num}',
                    'values': [[site4_price, site4_url]]
                })
            
            # Site 5 (Future)
            if 'site5_price' in prices:
                site5_price_raw = prices.get('site5_price')
                site5_price = self._to_float(site5_price_raw) if site5_price_raw else ''
                site5_url = prices.get('site5_url', '')
                
                all_updates.append({
                    'range': f'O{row_num}:P{row_num}',
                    'values': [[site5_price, site5_url]]
                })

                # Last update (Q)
                all_updates.append({
                    'range': f'Q{row_num}',
                    'values': [[datetime.now().strftime('%Y-%m-%d %H:%M:%S')]]
                })

            updated_count += 1
        
        # Perform ONE batch update for all products
        if all_updates:
            self.logger.info(f"Executing batch update: {len(all_updates)} changes for {updated_count} products")
            if skipped_count > 0:
                self.logger.info(f"Skipped: {skipped_count} products (no SKU or no prices)")
            time.sleep(0.5)

            # Open the sheet ONCE
            worksheet = self.client.open_sheet(sheet_id, sheet_name)

            # Google Sheets API allows up to 1000 updates at a time.
            # Break into chunks of 500.
            chunk_size = 500
            for i in range(0, len(all_updates), chunk_size):
                chunk = all_updates[i:i+chunk_size]
                worksheet.batch_update(chunk, value_input_option='RAW')

                self.logger.info(f"  Updated chunk {i//chunk_size + 1}/{(len(all_updates)-1)//chunk_size + 1}")

                if i + chunk_size < len(all_updates):
                    time.sleep(1.0)  # Delay between chunks
            
            self.logger.info(f"[OK] Batch update completed: {updated_count} products")
        else:
            self.logger.warning("No updates to perform!")
        
        return updated_count

    def cleanup_price_history(self, retention_days: int = 15) -> int:
        """
        Delete Price_History rows older than retention_days.
        Timestamp format expected in column A: 'YYYY-MM-DD HH:MM:SS'

        Args:
            retention_days: Number of days to keep (default: 15)

        Returns:
            Number of deleted rows
        """
        try:
            sheet_id = self.config['main_sheet']['id']
            history_name = 'Price_History'

            if not self.client.worksheet_exists(sheet_id, history_name):
                self.logger.debug("Price_History sheet does not exist — nothing to clean up")
                return 0

            worksheet = self.client.open_sheet(sheet_id, history_name)
            all_data = worksheet.get_all_values()

            if len(all_data) <= 1:  # Only header or empty
                self.logger.debug("Price_History is empty — nothing to clean up")
                return 0

            cutoff_date = datetime.now() - timedelta(days=retention_days)

            rows_to_delete = []
            for idx, row in enumerate(all_data[1:], start=2):  # Skip header row 1
                if not row or not row[0]:
                    continue
                try:
                    row_timestamp = datetime.strptime(row[0], '%Y-%m-%d %H:%M:%S')
                    if row_timestamp < cutoff_date:
                        rows_to_delete.append(idx)
                except (ValueError, IndexError):
                    continue

            if not rows_to_delete:
                self.logger.debug(
                    f"No Price_History rows older than {retention_days} days"
                )
                return 0

            # Delete from bottom to top so indices stay valid
            deleted = self._delete_rows_batch(worksheet, rows_to_delete)

            self.logger.info(
                f"[CLEANUP] Price_History: deleted {deleted} rows "
                f"(older than {retention_days} days)"
            )
            return deleted

        except Exception as e:
            self.logger.error(f"Failed to cleanup Price_History: {e}")
            return 0

    def _delete_rows_batch(self, worksheet, row_indices: list) -> int:
        """
        Delete multiple rows efficiently (bottom to top).

        Args:
            worksheet: gspread Worksheet instance
            row_indices: List of 1-indexed row numbers to delete

        Returns:
            Number of deleted rows
        """
        if not row_indices:
            return 0

        sorted_indices = sorted(row_indices, reverse=True)
        deleted = 0
        batch_size = 100

        try:
            for i in range(0, len(sorted_indices), batch_size):
                batch = sorted_indices[i:i + batch_size]
                for row_idx in batch:
                    worksheet.delete_rows(row_idx)
                    deleted += 1
                # Small delay between batches to avoid rate limiting
                if i + batch_size < len(sorted_indices):
                    time.sleep(1)
            return deleted

        except Exception as e:
            self.logger.error(f"Failed to delete rows batch: {e}")
            return deleted

    def batch_add_to_history(self, history_records: List[Dict]) -> int:
        """
        TRUE Batch recording Price History with auto-expand
        
        Structure: Date | SKU | URL | Old Price | New Price | Change
        """
        if not history_records:
            return 0
        
        try:
            sheet_id = self.config['main_sheet']['id']
            history_name = 'Price_History'
            
            # Check worksheet ONCE (1 API call)
            if not self.client.worksheet_exists(sheet_id, history_name):
                self.logger.info(f"Creating Price_History worksheet...")
                ws = self.client.create_worksheet(sheet_id, history_name, rows=5000, cols=6)
                headers = ['Date', 'SKU', 'URL', 'Old Price', 'New Price', 'Change']
                ws.update('A1', [headers])
                time.sleep(0.5)
            
            # Prepare ALL lines
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            all_rows = []
            for record in history_records:
                old_price = record.get('old_price', 0)
                new_price = record.get('new_price', 0)
                # Always count on change
                change = new_price - old_price
                
                row = [
                    timestamp,
                    record.get('sku', ''),
                    record.get('url', ''),
                    old_price,
                    new_price,
                    change
                ]
                all_rows.append(row)
            
            # Record EVERYTHING in one batch update
            if all_rows:
                time.sleep(0.5)
                worksheet = self.client.open_sheet(sheet_id, history_name)
                
                # Determine the initial line (after the header)
                existing_data = worksheet.get_all_values()
                start_row = len(existing_data) + 1
                end_row = start_row + len(all_rows) - 1
                
                # Expand the worksheet if necessary
                current_rows = worksheet.row_count
                rows_needed = end_row
                
                if current_rows < rows_needed:
                    self.logger.info(f"Expanding Price_History from {current_rows} to {rows_needed} rows...")
                    worksheet.resize(rows=rows_needed)
                    time.sleep(0.3)
                
                # Update one range
                range_name = f'A{start_row}:F{end_row}'
                worksheet.update(range_name, all_rows, value_input_option='RAW')
                
                self.logger.info(f"[OK] Added {len(all_rows)} records to Price_History")
                return len(all_rows)
            
            return 0
            
        except Exception as e:
            self.logger.error(f"Failed to batch add price history: {e}", exc_info=True)
            return 0


    def update_emma_mason_data(self, url: str, emma_id: str, new_price: float) -> bool:
        """
        Update Emma Mason data for a product by URL
        
        Args:
            url: Product URL (for string search)
            emma_id: ID from Emma Mason
            new_price: New price
        
        Returns:
            True if successful
        """
        try:
            sheet_id = self.config['main_sheet']['id']
            sheet_name = self.config['main_sheet']['name']
            
            # Find a string by URL
            time.sleep(0.5)
            worksheet = self.client.open_sheet(sheet_id, sheet_name)
            
            # Get all URLs (column F = Our URL)
            all_urls = worksheet.col_values(6)  # F = 6
            
            # Find index
            url_normalized = url.strip().lower()
            row_num = None
            
            for idx, cell_url in enumerate(all_urls, start=1):
                if cell_url.strip().lower() == url_normalized:
                    row_num = idx
                    break
            
            if not row_num:
                self.logger.warning(f"URL not found in sheet: {url[:60]}")
                return False
            
            # Get the old price (Our Sales Price = column D)
            old_price_cell = worksheet.cell(row_num, 4).value  # D = 4
            old_price = float(old_price_cell) if old_price_cell else 0.0
            
            # Prepare updates
            updates = []
            
            # Our Sales Price (column D = 4)
            updates.append({
                'range': f'D{row_num}',
                'values': [[new_price]]
            })
            
            # ID from emmamason (column R = 18)
            updates.append({
                'range': f'R{row_num}',
                'values': [[emma_id]]
            })
            
            # Last update (column Q = 17)
            updates.append({
                'range': f'Q{row_num}',
                'values': [[datetime.now().strftime('%Y-%m-%d %H:%M:%S')]]
            })
            
            # Perform a batch update
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
        Batch update for Emma Mason products
        
        - URL normalization
        - ID fallback
        - Matching logic: URL first, then ID
        - Price conversion
        - Batch history with SKU
        
        Args:
            scraped_products: List of products from Emma Mason [{‘id’: ‘’, ‘url’: ‘’, ‘price’: ‘’}]
        
        Returns:
            Number of updated products
        """
        try:
            sheet_id = self.config['main_sheet']['id']
            sheet_name = self.config['main_sheet']['name']
            
            self.logger.info(f"Batch updating Emma Mason data for {len(scraped_products)} products...")
            
            # Download all data from the table
            time.sleep(0.5)
            worksheet = self.client.open_sheet(sheet_id, sheet_name)
            all_data = worksheet.get_all_values()
            
            # Create TWO dictionaries - one for URLs and one for IDs
            url_to_row = {}
            id_to_row = {}
            
            for idx, row in enumerate(all_data, start=1):
                if len(row) > 5:  # F = index 5 (0-based)
                    sku = row[0] if len(row) > 0 else ''  # A = SKU
                    url_raw = row[5].strip() if len(row) > 5 else ''  # F = Our URL
                    emma_id = row[17].strip() if len(row) > 17 else ''  # R = ID from emmamason
                    old_price = row[3] if len(row) > 3 else ''  # D = Our Sales Price
                    
                    # URL mapping (with normalization)
                    if url_raw:
                        url_normalized = normalize_url(url_raw)
                        url_to_row[url_normalized] = {
                            'row_num': idx,
                            'sku': sku,
                            'old_price': old_price,
                            'original_url': url_raw,
                            'emma_id': emma_id
                        }
                    
                    # ID mapping
                    if emma_id:
                        id_to_row[emma_id] = {
                            'row_num': idx,
                            'sku': sku,
                            'old_price': old_price,
                            'original_url': url_raw,
                            'emma_id': emma_id
                        }
            
            self.logger.info(f"Loaded {len(url_to_row)} URLs and {len(id_to_row)} IDs from sheet")
            
            # Find matches and prepare updates
            all_updates = []
            updated_count = 0
            history_records = []
            
            # Matching statistics
            matched_by_url = 0
            matched_by_id = 0
            no_match_count = 0
            price_conversion_errors = 0
            
            for product in scraped_products:
                url_raw = product.get('url', '').strip()
                emma_id = product.get('id', '').strip()
                price_raw = product.get('price', '')
                
                # Check if there is at least a URL or ID
                if not url_raw and not emma_id:
                    no_match_count += 1
                    continue
                
                # First URL then ID
                row_info = None
                matched_by = None
                
                # Try to find by URL
                if url_raw:
                    url_normalized = normalize_url(url_raw)
                    if url_normalized in url_to_row:
                        row_info = url_to_row[url_normalized]
                        matched_by = 'URL'
                        matched_by_url += 1
                
                # If not found by URL, try by ID
                if not row_info and emma_id:
                    if emma_id in id_to_row:
                        row_info = id_to_row[emma_id]
                        matched_by = 'ID'
                        matched_by_id += 1
                
                # If not found by URL or ID
                if not row_info:
                    no_match_count += 1
                    continue
                
                # Get data from row_info
                row_num = row_info['row_num']
                sku = row_info['sku']
                old_price_str = row_info['old_price']
                
                # Convert price
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
                
                # Prepare updates
                # Our Sales Price (D = 4)
                all_updates.append({
                    'range': f'D{row_num}',
                    'values': [[new_price]]
                })
                
                # ID from emmamason (R = 18) - update if there is a new ID
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
                
                # Save for history with SKU!
                if abs(new_price - old_price) > 0.01:
                    history_records.append({
                        'sku': sku,
                        'url': url_raw or row_info.get('original_url', ''),
                        'old_price': old_price,
                        'new_price': new_price
                    })
            
            # MATCHING REPORT
            self.logger.info("="*60)
            self.logger.info("EMMA MASON MATCHING RESULTS:")
            self.logger.info(f"  Total products from scraper: {len(scraped_products)}")
            self.logger.info(f"  URLs in sheet: {len(url_to_row)}")
            self.logger.info(f"  IDs in sheet: {len(id_to_row)}")
            self.logger.info("")
            self.logger.info(f"  [OK] Matched by URL: {matched_by_url}")
            self.logger.info(f"  [OK] Matched by ID (fallback): {matched_by_id}")
            self.logger.info(f"  [ERROR] No match: {no_match_count}")
            
            if price_conversion_errors > 0:
                self.logger.warning(f"  [!]  Price conversion errors: {price_conversion_errors}")
            
            total_matched = matched_by_url + matched_by_id
            if len(scraped_products) > 0:
                match_rate = total_matched / len(scraped_products) * 100
                self.logger.info(f"  Match rate: {match_rate:.1f}%")
            
            self.logger.info("="*60)
            
            # Perform a batch update
            if all_updates:
                self.logger.info(f"Executing batch update with {len(all_updates)} changes...")
                
                chunk_size = 500
                for i in range(0, len(all_updates), chunk_size):
                    chunk = all_updates[i:i+chunk_size]
                    time.sleep(0.5)
                    self.client.batch_update(sheet_id, chunk, sheet_name)
                    
                    if i + chunk_size < len(all_updates):
                        time.sleep(1.0)
                
                self.logger.info(f"[OK] Batch update completed: {updated_count} products")
            
            # Add entries to history
            if history_records:
                self.logger.info(f"Adding {len(history_records)} records to Price_History (batch mode)...")
                added = self.batch_add_to_history(history_records)
                self.logger.info(f"[OK] Price History: {added} records added")
            
            return updated_count
            
        except Exception as e:
            self.logger.error(f"Failed batch update Emma Mason: {e}", exc_info=True)
            return 0

    def _to_float(self, value, default: float = 0.0) -> float:
        """
        Convert values to float with handling of different formats
        """
        if value is None or value == '':
            return default
        
        # If the number
        if isinstance(value, (int, float)):
            return float(value)
        
        # If the stringRemove spaces
        if isinstance(value, str):
            try:
                # Remove spaces
                cleaned = value.strip()
                
                if not cleaned:
                    return default
                
                # Replace comma with period
                cleaned = cleaned.replace(',', '.')
                
                # Remove spaces inside
                cleaned = cleaned.replace(' ', '')
                
                # Remove $ if present
                cleaned = cleaned.replace('$', '')
                
                # Convert
                result = float(cleaned)
                
                return result
                
            except (ValueError, TypeError) as e:
                self.logger.warning(
                    f"Failed to convert '{value}' to float: {e}. Using default: {default}"
                )
                return default

        try:
            return float(value)
        except:
            self.logger.warning(f"Cannot convert {type(value)} '{value}' to float")
            return default

    def batch_update_competitors_raw(
        self, 
        competitor_data: Dict[str, List[Dict]],
        matched_tracker=None
    ) -> int:
        """
        Update Competitors sheet with matched tracking
        """
        
        try:
            sheet_id = self.config['main_sheet']['id']
            sheet_name = "Competitors"
            
            #Headers with 4 additional columns
            headers = [
                'Source',
                'SKU',
                'Price',
                'URL',
                'Brand',
                'Title',
                'Date Scraped',
                'Matched',
                'Matched With',
                'Matched With URL',
                'Used In Pricing'
            ]
            
            all_rows = []
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            source_names = {
                'coleman': 'Coleman',
                'onestopbedrooms': '1StopBedrooms',
                'afastores': 'AFA Stores'
            }
            
            for source, products in competitor_data.items():
                source_display = source_names.get(source, source)
                
                for product in products:
                    sku = str(product.get('sku', ''))
                    
                    # Get tracking info
                    matched = False
                    matched_with = ''
                    matched_with_url = ''
                    used = False
                    
                    if matched_tracker:
                        tracking = matched_tracker.get_tracking(source, sku)
                        if tracking.get('matched_with'):
                            matched = True
                            matched_with = tracking.get('matched_with', '')
                            matched_with_url = tracking.get('matched_with_url', '')
                            used = tracking.get('used', False)
                    
                    row = [
                        source_display,
                        sku,
                        self._to_float(product.get('price', 0)),
                        product.get('url', ''),
                        product.get('brand', ''),
                        product.get('title', ''),
                        timestamp,
                        matched,              # Boolean TRUE/FALSE
                        matched_with,         # Our SKU
                        matched_with_url,     # Our URL
                        used                  # Boolean TRUE/FALSE
                    ]
                    all_rows.append(row)
            
            if not all_rows:
                self.logger.warning("No competitor data to write")
                return 0
            
            # Use correct API (like batch_update_emma_mason_raw)
            self.logger.info(f"Updating {sheet_name} sheet with {len(all_rows)} products...")
            
            # Check if worksheet exists
            if not self.client.worksheet_exists(sheet_id, sheet_name):
                self.logger.info(f"Creating {sheet_name} worksheet...")
                ws = self.client.create_worksheet(sheet_id, sheet_name, rows=20000, cols=11)
                ws.update('A1', [headers])
                time.sleep(0.5)
            
            # Open worksheet
            worksheet = self.client.open_sheet(sheet_id, sheet_name)
            
            # Resize if needed
            rows_needed = len(all_rows) + 1  # +1 for headers
            current_rows = worksheet.row_count
            
            if current_rows < rows_needed:
                self.logger.info(f"Expanding worksheet from {current_rows} to {rows_needed} rows...")
                worksheet.resize(rows=rows_needed)
                time.sleep(0.3)
            
            # Clear old data (keep headers)
            if current_rows > 1:
                self.logger.info("Clearing old data...")
                clear_range = f'A2:K{current_rows}'
                worksheet.batch_clear([clear_range])
                time.sleep(0.3)
            
            # Update headers (in case they changed)
            worksheet.update('A1:K1', [headers], value_input_option='RAW')
            time.sleep(0.3)
            
            # Write all competitor data
            start_row = 2
            end_row = start_row + len(all_rows) - 1
            range_name = f'A{start_row}:K{end_row}'
            
            self.logger.info(f"Writing {len(all_rows)} competitor products...")
            worksheet.update(range_name, all_rows, value_input_option='RAW')
            
            self.logger.info(f"[OK] {sheet_name} sheet updated: {len(all_rows)} products")
            
            return len(all_rows)
            
        except Exception as e:
            self.logger.error(f"Failed to update Competitors sheet: {e}", exc_info=True)
            return 0
    
    def batch_update_emma_mason_raw(self, scraped_products: List[Dict]) -> int:
        """
        Record ALL RAW data from Emma Mason scraper
        
        Args:
            scraped_products: List of products from Emma Mason scraper
                [{‘id’: ‘’, ‘url’: ‘’, ‘price’: ‘’, ‘brand’: ‘’, ‘scraped_at’: ‘’}, ...]
        
        Returns:
            Number of items recorded
        """
        try:
            sheet_id = self.config['main_sheet']['id']
            emma_raw_sheet = "Emma_Mason_Raw"
            
            if not scraped_products:
                self.logger.warning("No Emma Mason products to save (empty list)")
                return 0
            
            self.logger.info(f"Updating Emma_Mason_Raw sheet with {len(scraped_products)} RAW products...")
            
            # Check if a sheet exists
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
            
            # Prepare ALL lines
            all_rows = []
            
            for product in scraped_products:
                row = [
                    product.get('id', ''),
                    product.get('url', ''),
                    self._to_float(product.get('price', 0)),  # Convert to float
                    product.get('brand', ''),
                    product.get('scraped_at', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
                ]
                all_rows.append(row)
            
            # Write EVERYTHING in one batch update
            if all_rows:
                self.logger.info(f"Writing {len(all_rows)} Emma Mason RAW products...")
                
                time.sleep(0.5)
                worksheet = self.client.open_sheet(sheet_id, emma_raw_sheet)
                
                # Expand the worksheet before writing
                rows_needed = len(all_rows) + 1  # +1 for header
                current_rows = worksheet.row_count
                
                if current_rows < rows_needed:
                    self.logger.info(f"Expanding worksheet from {current_rows} to {rows_needed} rows...")
                    worksheet.resize(rows=rows_needed)
                    time.sleep(0.3)
                
                # Clear old data (leave only header)
                if current_rows > 1:
                    self.logger.info("Clearing old data...")
                    clear_range = f'A2:E{current_rows}'
                    worksheet.batch_clear([clear_range])
                    time.sleep(0.3)
                
                # Determine the range
                start_row = 2  # After header
                end_row = start_row + len(all_rows) - 1
                
                # Update one range with USER_ENTERED for correct formatting
                range_name = f'A{start_row}:E{end_row}'
                worksheet.update(range_name, all_rows, value_input_option='RAW')
                
                self.logger.info(f"[OK] Emma_Mason_Raw sheet updated: {len(all_rows)} RAW products")
                
                # Show statistics by brand
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
