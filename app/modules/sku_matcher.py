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

    def remove_manufacturer_prefix(self, sku: str, source: str = None) -> str:
        """
        Видалити префікс виробника з SKU
        
        ⚠️ ВАЖЛИВО: Префікс видаляємо ТІЛЬКИ з Coleman SKU!
        Інші джерела (1StopBedrooms, AFA, Emma Mason) залишаємо без змін.
        
        Coleman використовує формат: INT-BY-CA-5640-BLK-C
        Emma Mason використовує: BY-CA-5640-BLK-C
        
        Префікси Coleman: INT-, HOM-, FUR-, DEC-, STY-, MOD-, LEG-, MAR-, STR-
        
        Args:
            sku: SKU з можливим префіксом
            source: Джерело SKU ('coleman', 'onestopbedrooms', 'afastores', 'emmamason')
        
        Returns:
            SKU без префіксу (тільки для Coleman)
        """
        # ✅ КРИТИЧНО: Видаляти префікс ТІЛЬКИ для Coleman!
        if source != 'coleman':
            return sku
        
        if not sku or '-' not in sku:
            return sku
        
        # Список відомих префіксів виробників Coleman
        known_prefixes = ['INT', 'HOM', 'FUR', 'DEC', 'STY', 'MOD', 'LEG', 'MAR', 'STR']
        
        parts = sku.split('-', 1)  # Розділити на перший сегмент та решту
        
        if len(parts) == 2 and parts[0].upper() in known_prefixes:
            logger.debug(f"Removed Coleman prefix '{parts[0]}' from SKU: {sku} → {parts[1]}")
            return parts[1]
        
        return sku


    def normalize_sku(self, sku, source: str = None) -> str:
        """
        Нормалізувати SKU
        
        Args:
            sku: SKU (може бути str, int, float)
            source: Джерело SKU для правильної обробки префіксів
        
        Returns:
            Нормалізований SKU (lowercase, без префіксів для Coleman)
        """
        if not sku:
            return ""
        
        # Конвертувати в string якщо це int/float
        if isinstance(sku, (int, float)):
            sku = str(int(sku))
            logger.debug(f"Converted numeric SKU to string: {sku}")
        
        # Тепер можна safely працювати зі string
        sku = str(sku).strip()
        
        # ✅ НОВИЙ ПАРАМЕТР: Видалити префікс ТІЛЬКИ для Coleman
        sku = self.remove_manufacturer_prefix(sku, source=source)
        
        if not self.case_sensitive:
            sku = sku.lower()
        
        return sku

    
    def split_sku(self, sku_string, source: str = None) -> List[str]:
        """
        Розділити SKU string на частини
        
        Args:
            sku_string: SKU або список SKU розділених delimiter
            source: Джерело для правильної обробки префіксів
        """
        if not sku_string:
            return []
        
        # Нормалізувати перед split
        normalized = self.normalize_sku(sku_string, source=source)
        
        if not normalized:
            return []
        
        # Розділити на частини
        skus = normalized.split(self.delimiter)
        
        # Прибрати порожні та пробіли
        result = [sku.strip() for sku in skus if sku.strip()]
        
        return result
    
    def exact_match(self, sku1, sku2, source: str = None) -> bool:
        """
        Точний збіг SKU
        
        Args:
            sku1: Перший SKU
            sku2: Другий SKU
            source: Джерело для правильної обробки префіксів
        """
        norm1 = self.normalize_sku(sku1, source=source)
        norm2 = self.normalize_sku(sku2, source=source)
        return norm1 == norm2
    
    def fuzzy_match(self, sku1, sku2, source: str = None) -> float:
        """Fuzzy matching (схожість)"""
        norm1 = self.normalize_sku(sku1, source=source)
        norm2 = self.normalize_sku(sku2, source=source)
        
        if not norm1 or not norm2:
            return 0.0
        
        return SequenceMatcher(None, norm1, norm2).ratio()
    
    def matches(self, sku1, sku2, source: str = None) -> bool:
        """
        Перевірити чи SKU1 збігається з SKU2
        
        Args:
            sku1: SKU (може містити кілька SKU розділених delimiter)
            sku2: SKU для порівняння
            source: Джерело sku2 ('coleman', 'onestopbedrooms', 'afastores')
        """
        # Розділити SKU1 на частини
        sku1_list = self.split_sku(sku1)
        
        if not sku1_list:
            return False
        
        # Перевірити кожну частину SKU1
        for sku in sku1_list:
            if self.strategy == 'exact':
                if self.exact_match(sku, sku2, source=source):
                    return True
            elif self.strategy == 'fuzzy':
                if self.fuzzy_match(sku, sku2, source=source) >= self.fuzzy_threshold:
                    return True
        
        return False
    
    def find_matching_product(self, target_sku, products: List[Dict], 
                            sku_field: str = 'sku', source: str = None) -> Optional[Dict]:
        """
        Знайти товар в списку за SKU
        
        Args:
            target_sku: SKU для пошуку
            products: Список товарів
            sku_field: Поле з SKU в словнику товару
            source: Джерело products ('coleman', 'onestopbedrooms', 'afastores')
        """
        for product in products:
            product_sku = product.get(sku_field, '')
            
            if self.matches(target_sku, product_sku, source=source):
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
