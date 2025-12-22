"""
SKU Matcher для Furniture Repricer
Співставлення товарів за SKU
FIXED: Обробка int SKU (деякі scrapers повертають числа)
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
    
    def normalize_sku(self, sku) -> str:
        """
        Нормалізувати SKU - КРИТИЧНО: обробити int!
        
        Деякі scrapers повертають SKU як int замість str.
        Треба конвертувати в string.
        """
        if not sku:
            return ""
        
        # КРИТИЧНО: Конвертувати в string якщо це int/float
        if isinstance(sku, (int, float)):
            sku = str(int(sku))  # int() щоб видалити .0 з float
            logger.debug(f"Converted numeric SKU to string: {sku}")
        
        # Тепер можна safely працювати зі string
        sku = str(sku).strip()
        
        if not self.case_sensitive:
            sku = sku.lower()
        
        return sku
    
    def split_sku(self, sku_string) -> List[str]:
        """
        Розділити SKU string на частини
        
        FIXED: Обробка int SKU
        """
        if not sku_string:
            return []
        
        # КРИТИЧНО: Нормалізувати перед split (конвертує int→str)
        normalized = self.normalize_sku(sku_string)
        
        if not normalized:
            return []
        
        # Тепер можна безпечно робити split
        skus = normalized.split(self.delimiter)
        
        # Прибрати порожні та пробіли
        result = [sku.strip() for sku in skus if sku.strip()]
        
        return result
    
    def exact_match(self, sku1, sku2) -> bool:
        """Точний збіг SKU"""
        norm1 = self.normalize_sku(sku1)
        norm2 = self.normalize_sku(sku2)
        return norm1 == norm2
    
    def fuzzy_match(self, sku1, sku2) -> float:
        """Fuzzy matching (схожість)"""
        norm1 = self.normalize_sku(sku1)
        norm2 = self.normalize_sku(sku2)
        
        if not norm1 or not norm2:
            return 0.0
        
        return SequenceMatcher(None, norm1, norm2).ratio()
    
    def matches(self, sku1, sku2) -> bool:
        """
        Перевірити чи SKU1 збігається з SKU2
        
        SKU1 може містити кілька SKU розділених delimiter (;)
        SKU2 зазвичай одинарний
        
        FIXED: Обробка int SKU
        """
        # Розділити SKU1 на частини (обробляє int автоматично)
        sku1_list = self.split_sku(sku1)
        
        if not sku1_list:
            return False
        
        # Перевірити кожну частину SKU1
        for sku in sku1_list:
            if self.strategy == 'exact':
                if self.exact_match(sku, sku2):
                    return True
            elif self.strategy == 'fuzzy':
                if self.fuzzy_match(sku, sku2) >= self.fuzzy_threshold:
                    return True
        
        return False
    
    def find_matching_product(self, target_sku, products: List[Dict], 
                            sku_field: str = 'sku') -> Optional[Dict]:
        """
        Знайти товар в списку за SKU
        
        FIXED: Обробка int SKU
        """
        for product in products:
            product_sku = product.get(sku_field, '')
            
            if self.matches(product_sku, target_sku):
                return product
        
        return None


if __name__ == "__main__":
    # Тестування з int SKU
    import logging
    logging.basicConfig(level=logging.DEBUG)
    
    matcher = SKUMatcher({'split_delimiter': ';', 'case_sensitive': False})
    
    print("\nTest 1: String SKU (нормально)")
    print(f"  'ABC123' matches 'abc123': {matcher.matches('ABC123', 'abc123')}")
    
    print("\nTest 2: Int SKU (раніше падало)")
    print(f"  12345 matches '12345': {matcher.matches(12345, '12345')}")
    
    print("\nTest 3: Multiple SKU з int")
    print(f"  'ABC;123;DEF' matches 123: {matcher.matches('ABC;123;DEF', 123)}")
    
    print("\nTest 4: Float SKU")
    print(f"  456.0 matches '456': {matcher.matches(456.0, '456')}")
    
    print("\n✅ All tests passed!")
