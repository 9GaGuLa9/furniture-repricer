"""
COMPETITORS MATCHED TRACKING - Варіант 2 + URL
===============================================

Додає до Competitors sheet колонки для tracking matching:
- Matched: TRUE/FALSE
- Matched With: Наш SKU
- Matched With URL: URL нашого товару  
- Used In Pricing: TRUE/FALSE

Формат: Boolean (TRUE/FALSE)
Оновлення: Кожен run (fresh data)
Статистика: Мінімальна (тільки цифри)
"""

from typing import Dict, List
from datetime import datetime


class CompetitorsMatchedTracker:
    """Track which competitor products matched and were used in pricing"""
    
    def __init__(self):
        self.tracking = {
            'coleman': {},
            'onestopbedrooms': {},
            'afastores': {}
        }
        
        # Track our products URLs for "Matched With URL"
        self.our_products_urls = {}  # {sku: url}
    
    def add_our_product(self, sku: str, url: str):
        """Store our product URL for later reference"""
        if sku and url:
            self.our_products_urls[sku] = url
    
    def track_match(self, source: str, competitor_sku: str, our_sku: str, used: bool = False):
        """
        Track that competitor product matched with our product
        
        Args:
            source: 'coleman', 'onestopbedrooms', 'afastores'
            competitor_sku: Competitor's SKU
            our_sku: Our SKU that matched
            used: True if this was the best match used in pricing
        """
        if source not in self.tracking:
            return
        
        # Get our product URL
        our_url = self.our_products_urls.get(our_sku, '')
        
        # Track or update
        if competitor_sku in self.tracking[source]:
            # Update existing (e.g., mark as used)
            self.tracking[source][competitor_sku]['used'] = used
        else:
            # Add new tracking
            self.tracking[source][competitor_sku] = {
                'matched_with': our_sku,
                'matched_with_url': our_url,
                'used': used
            }
    
    def get_tracking(self, source: str, competitor_sku: str) -> Dict:
        """Get tracking info for specific competitor product"""
        return self.tracking.get(source, {}).get(competitor_sku, {
            'matched_with': '',
            'matched_with_url': '',
            'used': False
        })
    
    def get_statistics(self, total_counts: Dict[str, int]) -> Dict:
        """
        Get matching statistics
        
        Args:
            total_counts: {'coleman': 1500, 'onestopbedrooms': 800, ...}
        
        Returns:
            {
                'coleman': {'total': 1500, 'matched': 450, 'used': 150},
                ...
            }
        """
        stats = {}
        
        for source in ['coleman', 'onestopbedrooms', 'afastores']:
            total = total_counts.get(source, 0)
            matched = len(self.tracking.get(source, {}))
            used = sum(1 for t in self.tracking.get(source, {}).values() if t['used'])
            
            stats[source] = {
                'total': total,
                'matched': matched,
                'used': used,
                'match_rate': (matched / total * 100) if total > 0 else 0,
                'usage_rate': (used / matched * 100) if matched > 0 else 0
            }
        
        return stats


# ═══════════════════════════════════════════════════════════════
# INTEGRATION WITH MAIN.PY
# ═══════════════════════════════════════════════════════════════

def integrate_with_main_class():
    """
    Код який треба додати до класу в main.py
    """
    
    # ───────────────────────────────────────────────────────────
    # 1. Ініціалізація в __init__
    # ───────────────────────────────────────────────────────────
    
    def __init__(self, config_path: str = 'config.yaml'):
        # ... existing code ...
        
        # NEW: Initialize matched tracker
        from app.modules.competitors_tracker import CompetitorsMatchedTracker
        self.matched_tracker = CompetitorsMatchedTracker()
    
    # ───────────────────────────────────────────────────────────
    # 2. Збереження наших URLs в _load_client_data
    # ───────────────────────────────────────────────────────────
    
    def _load_client_data(self) -> List[Dict]:
        """Load client products from Google Sheets"""
        self.logger.info("Loading client products...")
        
        client_products = self.sheets_manager.get_all_products()
        
        # NEW: Store our products URLs
        for product in client_products:
            sku = product.get('sku')
            url = product.get('url')  # Або інше поле з URL
            if sku:
                self.matched_tracker.add_our_product(sku, url)
        
        self.logger.info(f"Loaded {len(client_products)} products")
        return client_products
    
    # ───────────────────────────────────────────────────────────
    # 3. Оновлення _match_and_track_competitor (NEW METHOD)
    # ───────────────────────────────────────────────────────────
    
    def _match_and_track_competitor(
        self, 
        product: Dict,
        our_sku: str,
        source: str,
        competitor_products: List[Dict],
        site_prefix: str
    ):
        """
        Match product with competitor and track results
        
        Args:
            product: Our product
            our_sku: Our SKU
            source: 'coleman', 'onestopbedrooms', 'afastores'
            competitor_products: List of competitor products
            site_prefix: 'site1', 'site2', 'site3'
        """
        
        # Find ALL matches (для tracking)
        all_matches = self.sku_matcher.find_all_matching_products(
            our_sku,
            competitor_products,
            sku_field='sku',
            source=source
        )
        
        # Track ALL matches (not used yet)
        for match in all_matches:
            comp_sku = match.get('sku')
            self.matched_tracker.track_match(
                source=source,
                competitor_sku=comp_sku,
                our_sku=our_sku,
                used=False  # Буде оновлено для best match
            )
        
        # Find BEST match
        best_match = self.sku_matcher.find_best_match(
            our_sku,
            competitor_products,
            sku_field='sku',
            price_field='price',
            source=source
        )
        
        if best_match:
            best_sku = best_match.get('sku')
            
            # Mark as USED in pricing
            self.matched_tracker.track_match(
                source=source,
                competitor_sku=best_sku,
                our_sku=our_sku,
                used=True  # ✓ Used!
            )
            
            # Save to product
            product[f'{site_prefix}_sku'] = best_sku
            product[f'{site_prefix}_price'] = best_match.get('price')
            product[f'{site_prefix}_url'] = best_match.get('url')
            
            return True
        
        return False
    
    # ───────────────────────────────────────────────────────────
    # 4. Замінити _match_products на версію з tracking
    # ───────────────────────────────────────────────────────────
    
    def _match_products(self, client_products: List[Dict], 
                        competitor_data: Dict[str, List[Dict]]) -> List[Dict]:
        """Match products з конкурентами за SKU"""
        
        self.logger.info("\n" + "="*60)
        self.logger.info("MATCHING PRODUCTS WITH COMPETITORS")
        self.logger.info("="*60)
        
        matched_products = []
        match_stats = {
            'coleman': 0,
            'onestopbedrooms': 0,
            'afastores': 0
        }
        
        for product in client_products:
            our_sku = product.get('sku')
            if not our_sku:
                continue
            
            # Coleman matching with tracking
            if self._match_and_track_competitor(
                product, our_sku, 'coleman',
                competitor_data.get('coleman', []),
                'site1'
            ):
                match_stats['coleman'] += 1
            
            # 1StopBedrooms matching with tracking
            if self._match_and_track_competitor(
                product, our_sku, 'onestopbedrooms',
                competitor_data.get('onestopbedrooms', []),
                'site2'
            ):
                match_stats['onestopbedrooms'] += 1
            
            # AFA matching with tracking
            if self._match_and_track_competitor(
                product, our_sku, 'afastores',
                competitor_data.get('afastores', []),
                'site3'
            ):
                match_stats['afastores'] += 1
            
            matched_products.append(product)
        
        # Мінімальна статистика (тільки цифри)
        self.logger.info(f"Coleman: {match_stats['coleman']} | "
                        f"1StopBedrooms: {match_stats['onestopbedrooms']} | "
                        f"AFA: {match_stats['afastores']}")
        
        return matched_products


# ═══════════════════════════════════════════════════════════════
# INTEGRATION WITH SHEETS_MANAGER
# ═══════════════════════════════════════════════════════════════

def integrate_with_sheets_manager():
    """
    Код для оновлення sheets_manager.py або аналогічного модуля
    """
    
    def batch_update_competitors_raw(
        self, 
        competitor_data: Dict[str, List[Dict]],
        matched_tracker=None  # NEW: Pass tracker
    ) -> int:
        """
        Update Competitors sheet with matched tracking
        
        Args:
            competitor_data: {'coleman': [...], 'onestopbedrooms': [...], ...}
            matched_tracker: CompetitorsMatchedTracker instance
        
        Returns:
            Number of rows updated
        """
        
        # NEW: Headers with tracking columns
        headers = [
            'Source',
            'SKU',
            'Price',
            'URL',
            'Brand',
            'Title',
            'Date Scraped',
            'Matched',              # NEW: Boolean
            'Matched With',         # NEW: Our SKU
            'Matched With URL',     # NEW: Our product URL
            'Used In Pricing'       # NEW: Boolean
        ]
        
        all_rows = []
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # Source mapping
        source_names = {
            'coleman': 'Coleman',
            'onestopbedrooms': '1StopBedrooms',
            'afastores': 'AFA Stores'
        }
        
        for source, products in competitor_data.items():
            source_display = source_names.get(source, source)
            
            for product in products:
                sku = str(product.get('sku', ''))
                
                # NEW: Get tracking info
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
                    matched,              # NEW: Boolean TRUE/FALSE
                    matched_with,         # NEW: Our SKU
                    matched_with_url,     # NEW: Our URL
                    used                  # NEW: Boolean TRUE/FALSE
                ]
                all_rows.append(row)
        
        if not all_rows:
            return 0
        
        # Write to sheet
        try:
            # Clear existing data
            self.sheet.values().clear(
                spreadsheetId=self.spreadsheet_id,
                range='Competitors!A1:K'  # Updated range (was A1:G)
            ).execute()
            
            # Write new data with headers
            body = {'values': [headers] + all_rows}
            
            result = self.sheet.values().update(
                spreadsheetId=self.spreadsheet_id,
                range='Competitors!A1',
                valueInputOption='USER_ENTERED',
                body=body
            ).execute()
            
            # Print minimal statistics
            if matched_tracker:
                total_counts = {src: len(prods) for src, prods in competitor_data.items()}
                stats = matched_tracker.get_statistics(total_counts)
                
                # Мінімальна статистика (тільки цифри)
                for source in ['coleman', 'onestopbedrooms', 'afastores']:
                    s = stats[source]
                    self.logger.info(f"{source}: {s['total']} total | "
                                   f"{s['matched']} matched | "
                                   f"{s['used']} used")
            
            return len(all_rows)
            
        except Exception as e:
            self.logger.error(f"Failed to update Competitors sheet: {e}")
            return 0


# ═══════════════════════════════════════════════════════════════
# USAGE EXAMPLE
# ═══════════════════════════════════════════════════════════════

def example_usage():
    """Приклад використання в main.py"""
    
    # In __init__:
    self.matched_tracker = CompetitorsMatchedTracker()
    
    # After loading client data:
    for product in client_products:
        self.matched_tracker.add_our_product(
            product.get('sku'),
            product.get('url')
        )
    
    # During matching:
    # ... matching logic ...
    self.matched_tracker.track_match(
        source='coleman',
        competitor_sku='INT-ABC',
        our_sku='ABC;DEF;GHI',
        used=True  # If this was best match
    )
    
    # When updating sheets:
    self.sheets_manager.batch_update_competitors_raw(
        competitor_data=self.competitor_data,
        matched_tracker=self.matched_tracker  # Pass tracker!
    )
    
    # Result in Competitors sheet:
    # | Source | SKU     | Price | ... | Matched | Matched With | Matched With URL    | Used In Pricing |
    # |--------|---------|-------|-----|---------|--------------|---------------------|-----------------|
    # | Coleman| INT-ABC | $105  | ... | TRUE    | ABC;DEF;GHI  | emma.com/abc-def-gh | FALSE           |
    # | Coleman| INT-DEF | $98   | ... | TRUE    | ABC;DEF;GHI  | emma.com/abc-def-gh | TRUE            |
    # | Coleman| INT-XYZ | $95   | ... | FALSE   |              |                     | FALSE           |


# ═══════════════════════════════════════════════════════════════
# TESTING
# ═══════════════════════════════════════════════════════════════

if __name__ == '__main__':
    # Test tracker
    tracker = CompetitorsMatchedTracker()
    
    # Add our products
    tracker.add_our_product('ABC;DEF;GHI', 'https://emma.com/product/abc-def-ghi')
    
    # Track matches
    tracker.track_match('coleman', 'INT-ABC', 'ABC;DEF;GHI', used=False)
    tracker.track_match('coleman', 'INT-DEF', 'ABC;DEF;GHI', used=True)
    tracker.track_match('coleman', 'INT-GHI', 'ABC;DEF;GHI', used=False)
    
    # Get tracking
    info = tracker.get_tracking('coleman', 'INT-DEF')
    print(f"INT-DEF matched with: {info['matched_with']}")
    print(f"URL: {info['matched_with_url']}")
    print(f"Used: {info['used']}")
    
    # Get statistics
    stats = tracker.get_statistics({'coleman': 1500, 'onestopbedrooms': 800, 'afastores': 600})
    print(f"\nStatistics:")
    for source, s in stats.items():
        print(f"{source}: {s['total']} total | {s['matched']} matched | {s['used']} used")
