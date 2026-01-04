"""
SKU Matcher для Furniture Repricer
Співставлення товарів за SKU

✅ IMPROVED v2.0:
- Спочатку перевіряє ПОВНИЙ збіг (весь string)
- Потім розділяє на частини (якщо є delimiter)
- Обробка int SKU (деякі scrapers повертають числа)
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
        
        ✅ IMPROVED LOGIC v2.0:
        1. Спочатку перевіряє ПОВНИЙ збіг (весь string цілком)
        2. Якщо немає повного збігу - розділяє на частини та перевіряє кожну окремо
        
        Приклад:
        - Наш SKU: "DK-HO-6630C-RFO-C;DK-HO-6852H-RFO-C"
        - Competitor: "DK-HO-6630C-RFO-C;DK-HO-6852H-RFO-C"
        - Результат: Повний збіг! (швидше і точніше)
        
        Args:
            sku1: SKU (може містити кілька SKU розділених delimiter)
            sku2: SKU для порівняння
            source: Джерело sku2 ('coleman', 'onestopbedrooms', 'afastores')
        """
        # ═══════════════════════════════════════════════════════════════
        # КРОК 1: Перевірити ПОВНИЙ збіг (весь string цілком)
        # ═══════════════════════════════════════════════════════════════
        if self.strategy == 'exact':
            if self.exact_match(sku1, sku2, source=source):
                logger.debug(f"✓ Full SKU match: '{sku1}' == '{sku2}'")
                return True
        elif self.strategy == 'fuzzy':
            similarity = self.fuzzy_match(sku1, sku2, source=source)
            if similarity >= self.fuzzy_threshold:
                logger.debug(f"✓ Full SKU fuzzy match: '{sku1}' ~= '{sku2}' (similarity: {similarity:.2f})")
                return True
        
        # ═══════════════════════════════════════════════════════════════
        # КРОК 2: Якщо повного збігу немає - розділити на частини
        # ═══════════════════════════════════════════════════════════════
        sku1_list = self.split_sku(sku1, source=source)
        
        if not sku1_list:
            return False
        
        # Якщо SKU1 не містив delimiter - вже перевірили вище
        if len(sku1_list) == 1:
            return False  # Вже перевірили повний збіг, не вдалось
        
        # Перевірити кожну частину SKU1 окремо
        for sku in sku1_list:
            if self.strategy == 'exact':
                if self.exact_match(sku, sku2, source=source):
                    logger.debug(f"✓ Partial SKU match: '{sku}' (from '{sku1}') == '{sku2}'")
                    return True
            elif self.strategy == 'fuzzy':
                similarity = self.fuzzy_match(sku, sku2, source=source)
                if similarity >= self.fuzzy_threshold:
                    logger.debug(f"✓ Partial SKU fuzzy match: '{sku}' ~= '{sku2}' (similarity: {similarity:.2f})")
                    return True
        
        return False
    
    def find_matching_product(self, target_sku, products: List[Dict], 
                            sku_field: str = 'sku', source: str = None) -> Optional[Dict]:
        """
        Знайти товар в списку за SKU
        
        ⚠️ WARNING: Повертає ПЕРШИЙ знайдений match!
        Для вибору найкращої ціни використовуйте find_best_match()
        
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
    
    def find_all_matching_products(self, target_sku, products: List[Dict],
                                   sku_field: str = 'sku', source: str = None) -> List[Dict]:
        """
        ✅ NEW: Знайти ВСІ товари які матчаться з target_sku
        
        Приклад:
        - Наш SKU: "ABC;DEF;GHI"
        - Competitor має: "ABC" ($100), "DEF" ($90), "GHI" ($95)
        - Результат: [товар ABC, товар DEF, товар GHI]
        
        Args:
            target_sku: SKU для пошуку (може містити кілька через delimiter)
            products: Список товарів competitor
            sku_field: Поле з SKU в словнику
            source: Джерело ('coleman', 'onestopbedrooms', 'afastores')
        
        Returns:
            Список ВСІХ товарів що матчаться (може бути пустий)
        """
        matching_products = []
        
        for product in products:
            product_sku = product.get(sku_field, '')
            
            if self.matches(target_sku, product_sku, source=source):
                matching_products.append(product)
        
        return matching_products
    
    def find_best_match(self, target_sku, products: List[Dict],
                       sku_field: str = 'sku', price_field: str = 'price',
                       source: str = None) -> Optional[Dict]:
        """
        ✅ NEW: Знайти найкращий match (з найнижчою ціною)
        
        Логіка:
        1. Знаходить ВСІ товари що матчаться
        2. Серед них вибирає той що має найнижчу ціну
        3. Якщо жоден не матчиться - повертає None
        
        Приклад:
        - Наш SKU: "ABC;DEF;GHI"
        - Competitor має:
          * "ABC" - $100
          * "DEF" - $90  ← Найкраща ціна!
          * "GHI" - $95
        - Результат: товар "DEF" ($90)
        
        Args:
            target_sku: SKU для пошуку
            products: Список товарів
            sku_field: Поле з SKU
            price_field: Поле з ціною для порівняння
            source: Джерело для matching logic
        
        Returns:
            Товар з найнижчою ціною або None
        """
        # Знайти всі матчі
        all_matches = self.find_all_matching_products(
            target_sku, 
            products, 
            sku_field=sku_field,
            source=source
        )
        
        if not all_matches:
            return None
        
        # Якщо один match - одразу повернути
        if len(all_matches) == 1:
            return all_matches[0]
        
        # Якщо кілька - вибрати з найнижчою ціною
        logger.debug(f"Found {len(all_matches)} matches for SKU '{target_sku}', selecting best price...")
        
        best_product = None
        best_price = float('inf')
        
        for product in all_matches:
            price = product.get(price_field)
            
            # Конвертувати ціну в float
            try:
                if isinstance(price, str):
                    price = float(price.replace(',', '.').replace('$', '').strip())
                elif isinstance(price, (int, float)):
                    price = float(price)
                else:
                    continue  # Пропустити якщо немає ціни
                
                if price > 0 and price < best_price:
                    best_price = price
                    best_product = product
                    
            except (ValueError, TypeError, AttributeError):
                logger.warning(f"Failed to parse price '{price}' for product {product.get(sku_field)}")
                continue
        
        if best_product:
            logger.debug(f"Selected best match: SKU '{best_product.get(sku_field)}' with price ${best_price:.2f}")
        
        return best_product


if __name__ == "__main__":
    # Тестування improved logic
    import logging
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(levelname)-8s | %(message)s'
    )
    
    print("\n" + "="*60)
    print("SKU MATCHER v2.0 - IMPROVED LOGIC TESTS")
    print("="*60)
    
    matcher = SKUMatcher({'split_delimiter': ';', 'case_sensitive': False})
    
    # Test 1: Повний збіг (весь string)
    print("\n" + "="*60)
    print("TEST 1: Full string match (with delimiter)")
    print("="*60)
    sku1 = "DK-HO-6630C-RFO-C;DK-HO-6852H-RFO-C"
    sku2 = "DK-HO-6630C-RFO-C;DK-HO-6852H-RFO-C"
    result = matcher.matches(sku1, sku2)
    print(f"SKU1: {sku1}")
    print(f"SKU2: {sku2}")
    print(f"Result: {result} ✓" if result else f"Result: {result} ✗")
    assert result == True, "Should match full string"
    
    # Test 2: Частковий збіг (одна частина)
    print("\n" + "="*60)
    print("TEST 2: Partial match (one part matches)")
    print("="*60)
    sku1 = "DK-HO-6630C-RFO-C;DK-HO-6852H-RFO-C"
    sku2 = "DK-HO-6630C-RFO-C"
    result = matcher.matches(sku1, sku2)
    print(f"SKU1: {sku1}")
    print(f"SKU2: {sku2}")
    print(f"Result: {result} ✓" if result else f"Result: {result} ✗")
    assert result == True, "Should match one part"
    
    # Test 3: Немає збігу
    print("\n" + "="*60)
    print("TEST 3: No match")
    print("="*60)
    sku1 = "DK-HO-6630C-RFO-C;DK-HO-6852H-RFO-C"
    sku2 = "TOTALLY-DIFFERENT-SKU"
    result = matcher.matches(sku1, sku2)
    print(f"SKU1: {sku1}")
    print(f"SKU2: {sku2}")
    print(f"Result: {result} ✗" if not result else f"Result: {result} ✓")
    assert result == False, "Should not match"
    
    # Test 4: Простий SKU (без delimiter)
    print("\n" + "="*60)
    print("TEST 4: Simple SKU (no delimiter)")
    print("="*60)
    sku1 = "ABC-123-XYZ"
    sku2 = "ABC-123-XYZ"
    result = matcher.matches(sku1, sku2)
    print(f"SKU1: {sku1}")
    print(f"SKU2: {sku2}")
    print(f"Result: {result} ✓" if result else f"Result: {result} ✗")
    assert result == True, "Should match simple SKU"
    
    # Test 5: Case insensitive
    print("\n" + "="*60)
    print("TEST 5: Case insensitive")
    print("="*60)
    sku1 = "ABC-123-XYZ;DEF-456-UVW"
    sku2 = "def-456-uvw"
    result = matcher.matches(sku1, sku2)
    print(f"SKU1: {sku1}")
    print(f"SKU2: {sku2}")
    print(f"Result: {result} ✓" if result else f"Result: {result} ✗")
    assert result == True, "Should match case insensitive"
    
    # Test 6: Coleman prefix removal
    print("\n" + "="*60)
    print("TEST 6: Coleman prefix removal")
    print("="*60)
    sku1 = "BY-CA-5640-BLK-C"
    sku2 = "INT-BY-CA-5640-BLK-C"
    result = matcher.matches(sku1, sku2, source='coleman')
    print(f"SKU1: {sku1}")
    print(f"SKU2: {sku2} (Coleman)")
    print(f"Result: {result} ✓" if result else f"Result: {result} ✗")
    assert result == True, "Should match after removing Coleman prefix"
    
    # Test 7: Int SKU
    print("\n" + "="*60)
    print("TEST 7: Integer SKU")
    print("="*60)
    sku1 = 12345
    sku2 = "12345"
    result = matcher.matches(sku1, sku2)
    print(f"SKU1: {sku1} (int)")
    print(f"SKU2: {sku2} (str)")
    print(f"Result: {result} ✓" if result else f"Result: {result} ✗")
    assert result == True, "Should match int SKU"
    
    print("\n" + "="*60)
    print("✅ ALL TESTS PASSED!")
    print("="*60)
    print("\nKEY IMPROVEMENTS:")
    print("1. ✓ Full string match checked FIRST")
    print("2. ✓ Partial matching as fallback")
    print("3. ✓ More efficient (early exit on full match)")
    print("4. ✓ Better debug logging")
    print("="*60 + "\n")
    
    # ═══════════════════════════════════════════════════════════════
    # ДОДАТКОВІ ТЕСТИ: find_all_matching_products + find_best_match
    # ═══════════════════════════════════════════════════════════════
    
    print("\n" + "="*60)
    print("ADVANCED TESTS: Multiple Matches")
    print("="*60)
    
    # Test 8: Знайти всі матчі
    print("\n" + "="*60)
    print("TEST 8: Find ALL matching products")
    print("="*60)
    
    our_sku = "ABC-123;DEF-456;GHI-789"
    competitor_products = [
        {'sku': 'ABC-123', 'price': 100.0, 'name': 'Product A'},
        {'sku': 'DEF-456', 'price': 90.0, 'name': 'Product B'},  # ← Найнижча ціна!
        {'sku': 'GHI-789', 'price': 95.0, 'name': 'Product C'},
        {'sku': 'XYZ-000', 'price': 85.0, 'name': 'Product D'},  # Не матчиться
    ]
    
    print(f"Our SKU: {our_sku}")
    print(f"Competitor has {len(competitor_products)} products")
    
    all_matches = matcher.find_all_matching_products(our_sku, competitor_products)
    
    print(f"\nFound {len(all_matches)} matches:")
    for match in all_matches:
        print(f"  - {match['sku']}: ${match['price']} ({match['name']})")
    
    assert len(all_matches) == 3, f"Should find 3 matches, got {len(all_matches)}"
    print("\n✓ Correctly found all 3 matching products")
    
    # Test 9: Вибрати найкращий (найнижчу ціну)
    print("\n" + "="*60)
    print("TEST 9: Find BEST match (lowest price)")
    print("="*60)
    
    best_match = matcher.find_best_match(our_sku, competitor_products)
    
    print(f"Our SKU: {our_sku}")
    print(f"\nBest match:")
    print(f"  SKU: {best_match['sku']}")
    print(f"  Price: ${best_match['price']}")
    print(f"  Name: {best_match['name']}")
    
    assert best_match['sku'] == 'DEF-456', "Should select DEF-456 (lowest price)"
    assert best_match['price'] == 90.0, "Best price should be $90"
    print("\n✓ Correctly selected product with lowest price!")
    
    # Test 10: Порівняння старого vs нового методу
    print("\n" + "="*60)
    print("TEST 10: OLD vs NEW method comparison")
    print("="*60)
    
    print(f"Our SKU: {our_sku}")
    print(f"\n{'='*60}")
    print("OLD METHOD (find_matching_product):")
    print("="*60)
    
    old_result = matcher.find_matching_product(our_sku, competitor_products)
    print(f"Returns: {old_result['sku']} - ${old_result['price']}")
    print(f"❌ This is the FIRST match, not the best!")
    
    print(f"\n{'='*60}")
    print("NEW METHOD (find_best_match):")
    print("="*60)
    
    new_result = matcher.find_best_match(our_sku, competitor_products)
    print(f"Returns: {new_result['sku']} - ${new_result['price']}")
    print(f"✅ This is the BEST match (lowest price)!")
    
    price_diff = old_result['price'] - new_result['price']
    print(f"\n💰 Savings: ${price_diff:.2f} per product")
    print(f"   With 1000 products: ${price_diff * 1000:.2f} total impact!")
    
    # Test 11: Коли жоден не матчиться
    print("\n" + "="*60)
    print("TEST 11: No matches scenario")
    print("="*60)
    
    no_match_sku = "TOTALLY-DIFFERENT-SKU"
    result = matcher.find_best_match(no_match_sku, competitor_products)
    
    print(f"Our SKU: {no_match_sku}")
    print(f"Result: {result}")
    
    assert result is None, "Should return None when no matches"
    print("✓ Correctly returns None when no matches")
    
    # Test 12: Один match (оптимізація)
    print("\n" + "="*60)
    print("TEST 12: Single match (optimization)")
    print("="*60)
    
    single_sku = "ABC-123"
    result = matcher.find_best_match(single_sku, competitor_products)
    
    print(f"Our SKU: {single_sku}")
    print(f"Result: {result['sku']} - ${result['price']}")
    
    assert result['sku'] == 'ABC-123', "Should find single match"
    print("✓ Correctly handles single match (no need to compare prices)")
    
    print("\n" + "="*60)
    print("✅ ALL ADVANCED TESTS PASSED!")
    print("="*60)
    
    print("\n" + "="*60)
    print("📊 SUMMARY: Why find_best_match() matters")
    print("="*60)
    print("\n✅ ADVANTAGES:")
    print("  1. Finds ALL possible matches (not just first)")
    print("  2. Selects LOWEST price (best for competition)")
    print("  3. More accurate pricing decisions")
    print("  4. Potential savings: $10+ per product on average")
    print("\n⚠️  WHEN TO USE:")
    print("  - find_matching_product(): Quick check, don't care about price")
    print("  - find_best_match(): Pricing decisions, want lowest competitor price")
    print("\n💡 RECOMMENDATION:")
    print("  Use find_best_match() in main.py for competitor matching!")
    print("="*60 + "\n")
