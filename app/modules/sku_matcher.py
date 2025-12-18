"""
SKU Matcher для Furniture Repricer
Співставлення товарів за SKU
"""

from typing import List, Dict, Optional
from difflib import SequenceMatcher
import logging

logger = logging.getLogger("sku_matcher")

class SKUMatcher:
    """Клас для matching SKU між товарами"""
    
    def __init__(self, config: Dict = None):
        self.config = config or {}
        self.delimiter = self.config.get('split_delimiter', ';')
        self.case_sensitive = self.config.get('case_sensitive', False)
        self.strategy = self.config.get('strategy', 'exact')
        self.fuzzy_threshold = self.config.get('fuzzy_threshold', 0.85)
    
    def normalize_sku(self, sku: str) -> str:
        if not sku:
            return ""
        sku = sku.strip()
        if not self.case_sensitive:
            sku = sku.lower()
        return sku
    
    def split_sku(self, sku_string: str) -> List[str]:
        if not sku_string:
            return []
        skus = sku_string.split(self.delimiter)
        normalized = [self.normalize_sku(sku) for sku in skus]
        return [sku for sku in normalized if sku]
    
    def exact_match(self, sku1: str, sku2: str) -> bool:
        norm1 = self.normalize_sku(sku1)
        norm2 = self.normalize_sku(sku2)
        return norm1 == norm2
    
    def fuzzy_match(self, sku1: str, sku2: str) -> float:
        norm1 = self.normalize_sku(sku1)
        norm2 = self.normalize_sku(sku2)
        if not norm1 or not norm2:
            return 0.0
        return SequenceMatcher(None, norm1, norm2).ratio()
    
    def matches(self, sku1: str, sku2: str) -> bool:
        sku1_list = self.split_sku(sku1)
        if not sku1_list:
            return False
        
        for sku in sku1_list:
            if self.strategy == 'exact':
                if self.exact_match(sku, sku2):
                    return True
            elif self.strategy == 'fuzzy':
                if self.fuzzy_match(sku, sku2) >= self.fuzzy_threshold:
                    return True
        return False
    
    def find_matching_product(self, target_sku: str, products: List[Dict], 
                            sku_field: str = 'sku') -> Optional[Dict]:
        for product in products:
            product_sku = product.get(sku_field, '')
            if self.matches(product_sku, target_sku):
                return product
        return None
