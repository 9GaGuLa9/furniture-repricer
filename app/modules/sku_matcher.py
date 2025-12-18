"""
SKU Matcher для Furniture Repricer
Співставлення товарів клієнта та конкурентів за SKU
Підтримує множинні SKU розділені ";"
"""

from typing import List, Dict, Set, Optional, Tuple
from difflib import SequenceMatcher
from .logger import get_logger

logger = get_logger("sku_matcher")


class SKUMatcher:
    """Клас для matching SKU між товарами"""
    
    def __init__(self, config: Dict = None):
        """
        Ініціалізація matcher
        
        Args:
            config: Конфігурація {
                'split_delimiter': ';',
                'case_sensitive': False,
                'trim_whitespace': True,
                'strategy': 'exact',  # exact, fuzzy, hybrid
                'fuzzy_threshold': 0.85
            }
        """
        self.config = config or {}
        self.delimiter = self.config.get('split_delimiter', ';')
        self.case_sensitive = self.config.get('case_sensitive', False)
        self.trim_whitespace = self.config.get('trim_whitespace', True)
        self.strategy = self.config.get('strategy', 'exact')
        self.fuzzy_threshold = self.config.get('fuzzy_threshold', 0.85)
        
        logger.info(f"SKU Matcher initialized with strategy: {self.strategy}")
    
    def normalize_sku(self, sku: str) -> str:
        """
        Нормалізувати SKU
        
        Args:
            sku: SKU для нормалізації
        
        Returns:
            Нормалізований SKU
        """
        if not sku:
            return ""
        
        # Trim whitespace
        if self.trim_whitespace:
            sku = sku.strip()
        
        # Case sensitivity
        if not self.case_sensitive:
            sku = sku.lower()
        
        return sku
    
    def split_sku(self, sku_string: str) -> List[str]:
        """
        Розділити строку з множинними SKU
        
        Args:
            sku_string: Строка з SKU (напр. "ABC123;DEF456;GHI789")
        
        Returns:
            Список окремих SKU
        """
        if not sku_string:
            return []
        
        # Розділити по delimiter
        skus = sku_string.split(self.delimiter)
        
        # Нормалізувати кожен SKU
        normalized = [self.normalize_sku(sku) for sku in skus]
        
        # Видалити пусті
        return [sku for sku in normalized if sku]
    
    def exact_match(self, sku1: str, sku2: str) -> bool:
        """
        Точне співставлення SKU
        
        Args:
            sku1: Перший SKU
            sku2: Другий SKU
        
        Returns:
            True якщо співпадають
        """
        norm1 = self.normalize_sku(sku1)
        norm2 = self.normalize_sku(sku2)
        return norm1 == norm2
    
    def fuzzy_match(self, sku1: str, sku2: str) -> float:
        """
        Нечітке співставлення SKU (схожість)
        
        Args:
            sku1: Перший SKU
            sku2: Другий SKU
        
        Returns:
            Коефіцієнт схожості (0.0 - 1.0)
        """
        norm1 = self.normalize_sku(sku1)
        norm2 = self.normalize_sku(sku2)
        
        if not norm1 or not norm2:
            return 0.0
        
        return SequenceMatcher(None, norm1, norm2).ratio()
    
    def matches(self, sku1: str, sku2: str) -> bool:
        """
        Перевірити чи співпадають SKU згідно стратегії
        
        Args:
            sku1: Перший SKU (може містити множинні через ";")
            sku2: Другий SKU
        
        Returns:
            True якщо співпадають
        """
        # Розділити sku1 на окремі коди
        sku1_list = self.split_sku(sku1)
        
        # Якщо sku1 пустий - немає співпадіння
        if not sku1_list:
            return False
        
        # Перевірити кожен код з sku1
        for sku in sku1_list:
            if self.strategy == 'exact':
                if self.exact_match(sku, sku2):
                    return True
            
            elif self.strategy == 'fuzzy':
                similarity = self.fuzzy_match(sku, sku2)
                if similarity >= self.fuzzy_threshold:
                    return True
            
            elif self.strategy == 'hybrid':
                # Спочатку exact, потім fuzzy
                if self.exact_match(sku, sku2):
                    return True
                similarity = self.fuzzy_match(sku, sku2)
                if similarity >= self.fuzzy_threshold:
                    logger.debug(f"Fuzzy match: {sku} ~ {sku2} ({similarity:.2f})")
                    return True
        
        return False
    
    def find_matching_product(
        self,
        target_sku: str,
        products: List[Dict],
        sku_field: str = 'sku'
    ) -> Optional[Dict]:
        """
        Знайти товар з matching SKU у списку
        
        Args:
            target_sku: SKU для пошуку
            products: Список товарів
            sku_field: Назва поля з SKU у товарі
        
        Returns:
            Товар або None
        """
        for product in products:
            product_sku = product.get(sku_field, '')
            if self.matches(product_sku, target_sku):
                return product
        return None
    
    def match_products(
        self,
        client_products: List[Dict],
        competitor_products: List[Dict],
        client_sku_field: str = 'sku',
        competitor_sku_field: str = 'sku'
    ) -> Dict[str, Dict]:
        """
        Співставити товари клієнта з товарами конкурента
        
        Args:
            client_products: Список товарів клієнта
            competitor_products: Список товарів конкурента
            client_sku_field: Поле SKU у товарах клієнта
            competitor_sku_field: Поле SKU у товарів конкурента
        
        Returns:
            Словник {client_sku: competitor_product}
        """
        matches = {}
        
        for client_product in client_products:
            client_sku = client_product.get(client_sku_field, '')
            
            if not client_sku:
                continue
            
            # Знайти matching товар конкурента
            competitor_product = self.find_matching_product(
                client_sku,
                competitor_products,
                competitor_sku_field
            )
            
            if competitor_product:
                matches[client_sku] = competitor_product
        
        logger.info(f"Matched {len(matches)} products out of {len(client_products)}")
        return matches
    
    def build_sku_index(
        self,
        products: List[Dict],
        sku_field: str = 'sku'
    ) -> Dict[str, Dict]:
        """
        Створити індекс товарів за SKU для швидкого пошуку
        
        Args:
            products: Список товарів
            sku_field: Поле SKU
        
        Returns:
            Словник {normalized_sku: product}
        """
        index = {}
        
        for product in products:
            sku_string = product.get(sku_field, '')
            
            # Розділити на окремі SKU
            skus = self.split_sku(sku_string)
            
            # Додати кожен SKU в індекс
            for sku in skus:
                normalized = self.normalize_sku(sku)
                if normalized:
                    # Якщо SKU вже є - зберегти перший
                    if normalized not in index:
                        index[normalized] = product
        
        logger.info(f"Built SKU index with {len(index)} entries from {len(products)} products")
        return index
    
    def find_unmatched_products(
        self,
        all_products: List[Dict],
        matched_skus: Set[str],
        sku_field: str = 'sku'
    ) -> List[Dict]:
        """
        Знайти товари які не були співставлені
        
        Args:
            all_products: Всі товари
            matched_skus: Set з SKU які були співставлені
            sku_field: Поле SKU
        
        Returns:
            Список несопоставлених товарів
        """
        unmatched = []
        
        for product in all_products:
            sku = product.get(sku_field, '')
            
            # Перевірити кожен код у SKU строці
            skus = self.split_sku(sku)
            
            # Якщо жоден з кодів не співставлений - додати товар
            is_matched = any(
                self.normalize_sku(s) in matched_skus 
                for s in skus
            )
            
            if not is_matched:
                unmatched.append(product)
        
        logger.info(f"Found {len(unmatched)} unmatched products")
        return unmatched
    
    def get_match_statistics(
        self,
        client_count: int,
        competitor_count: int,
        matched_count: int
    ) -> Dict[str, any]:
        """
        Отримати статистику співставлення
        
        Args:
            client_count: Кількість товарів клієнта
            competitor_count: Кількість товарів конкурента
            matched_count: Кількість співставлених
        
        Returns:
            Словник зі статистикою
        """
        match_rate = (matched_count / client_count * 100) if client_count > 0 else 0
        
        return {
            'client_products': client_count,
            'competitor_products': competitor_count,
            'matched': matched_count,
            'unmatched_client': client_count - matched_count,
            'unmatched_competitor': competitor_count - matched_count,
            'match_rate_percent': match_rate
        }


class MultiSiteMatchercompiler:
    """Менеджер для співставлення з множиною конкурентів"""
    
    def __init__(self, matcher: SKUMatcher):
        """
        Ініціалізація
        
        Args:
            matcher: SKUMatcher instance
        """
        self.matcher = matcher
        self.logger = get_logger("multi_matcher")
    
    def match_all_competitors(
        self,
        client_products: List[Dict],
        competitors: Dict[str, List[Dict]],
        client_sku_field: str = 'sku',
        competitor_sku_field: str = 'sku'
    ) -> Dict[str, Dict[str, Dict]]:
        """
        Співставити товари клієнта з усіма конкурентами
        
        Args:
            client_products: Товари клієнта
            competitors: Словник {competitor_name: products_list}
            client_sku_field: Поле SKU клієнта
            competitor_sku_field: Поле SKU конкурентів
        
        Returns:
            Словник {
                'site1': {client_sku: competitor_product},
                'site2': {client_sku: competitor_product},
                ...
            }
        """
        all_matches = {}
        
        for competitor_name, competitor_products in competitors.items():
            self.logger.info(f"Matching with {competitor_name}...")
            
            matches = self.matcher.match_products(
                client_products,
                competitor_products,
                client_sku_field,
                competitor_sku_field
            )
            
            all_matches[competitor_name] = matches
            
            # Статистика
            stats = self.matcher.get_match_statistics(
                len(client_products),
                len(competitor_products),
                len(matches)
            )
            
            self.logger.info(
                f"{competitor_name}: {stats['matched']} matches "
                f"({stats['match_rate_percent']:.1f}%)"
            )
        
        return all_matches
    
    def merge_competitor_data(
        self,
        client_product: Dict,
        competitor_matches: Dict[str, Optional[Dict]]
    ) -> Dict:
        """
        Об'єднати дані клієнта з даними конкурентів
        
        Args:
            client_product: Товар клієнта
            competitor_matches: {
                'site1': competitor_product or None,
                'site2': competitor_product or None,
                ...
            }
        
        Returns:
            Об'єднаний товар з усіма даними
        """
        merged = client_product.copy()
        
        # Додати дані кожного конкурента
        for site_name, competitor_product in competitor_matches.items():
            if competitor_product:
                # Додати ціну та URL конкурента
                merged[f'{site_name}_price'] = competitor_product.get('price')
                merged[f'{site_name}_url'] = competitor_product.get('url')
                merged[f'{site_name}_brand'] = competitor_product.get('brand')
            else:
                # Немає співпадіння
                merged[f'{site_name}_price'] = None
                merged[f'{site_name}_url'] = None
        
        return merged


if __name__ == "__main__":
    # Тестування
    print("Testing SKU Matcher...")
    
    matcher = SKUMatcher({
        'split_delimiter': ';',
        'case_sensitive': False,
        'strategy': 'exact'
    })
    
    # Тест 1: Exact match
    print("\nTest 1: Exact match")
    print(f"  'ABC123' == 'abc123': {matcher.matches('ABC123', 'abc123')}")
    print(f"  'ABC123' == 'DEF456': {matcher.matches('ABC123', 'DEF456')}")
    
    # Тест 2: Multiple SKUs
    print("\nTest 2: Multiple SKUs")
    multi_sku = "ABC123;DEF456;GHI789"
    print(f"  Split '{multi_sku}': {matcher.split_sku(multi_sku)}")
    print(f"  Matches 'def456': {matcher.matches(multi_sku, 'def456')}")
    print(f"  Matches 'xyz999': {matcher.matches(multi_sku, 'xyz999')}")
    
    # Тест 3: Build index
    print("\nTest 3: Build index")
    products = [
        {'sku': 'ABC123', 'name': 'Product 1'},
        {'sku': 'DEF456;GHI789', 'name': 'Product 2'},
        {'sku': 'JKL012', 'name': 'Product 3'}
    ]
    index = matcher.build_sku_index(products)
    print(f"  Index size: {len(index)}")
    print(f"  Keys: {list(index.keys())}")
