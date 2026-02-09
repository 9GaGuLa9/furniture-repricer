"""
COMPETITORS MATCHED TRACKING
===============================================

Adds columns to the Competitors sheet for tracking matching:
- Matched: TRUE/FALSE
- Matched With: Our SKU
- Matched With URL: URL of our product  
- Used In Pricing: TRUE/FALSE

Format: Boolean (TRUE/FALSE)
Update: Every run
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

            # If already marked as used=True, do not change to False
            existing = self.tracking[source][competitor_sku]
            
            if used:
                # If a new call with used=True → always update
                existing['used'] = True
                existing['matched_with'] = our_sku
                existing['matched_with_url'] = our_url
            else:
                # If a new call with used=False → update only if not already used
                if not existing['used']:
                    existing['matched_with'] = our_sku
                    existing['matched_with_url'] = our_url
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
