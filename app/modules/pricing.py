"""
Pricing Engine для Furniture Repricer
FINAL VERSION with correct logic
"""

from typing import Dict, List, Optional, Tuple
import logging

logger = logging.getLogger("pricing")

class PricingEngine:
    """Движок для розрахунку цін"""
    
    def __init__(self, coefficients: Dict[str, float] = None):
        self.coefficients = coefficients or {
            'floor': 1.5,
            'below_lowest': 1.0,
            'max': 2.0
        }
    
    def calculate_floor_price(self, cost: float) -> float:
        """Мінімальна ціна = cost × floor_coef"""
        floor_coef = self.coefficients.get('floor', 1.5)
        return cost * floor_coef
    
    def calculate_max_price(self, cost: float) -> float:
        """Максимальна ціна = cost × max_coef"""
        max_coef = self.coefficients.get('max', 2.0)
        return cost * max_coef
    
    def get_lowest_competitor_price(self, competitor_prices: List[float]) -> Optional[float]:
        """Знайти найнижчу ціну серед конкурентів"""
        valid_prices = [p for p in competitor_prices if p and p > 0]
        if not valid_prices:
            return None
        return min(valid_prices)
    
    def calculate_suggested_price(self, cost: float, competitor_prices: List[float],
                                 current_price: Optional[float] = None) -> Tuple[float, Dict]:
        """
        Розрахувати рекомендовану ціну
        
        Логіка:
        - Є конкуренти → min(competitors) - $1.00 (з урахуванням floor/max)
        - Немає конкурентів → залишити Our Sales Price БЕЗ ЗМІН
        """
        
        metadata = {
            'cost': cost,
            'competitors_count': len([p for p in competitor_prices if p and p > 0]),
            'calculation_method': None,
            'floor_price': None,
            'max_price': None,
            'lowest_competitor': None,
        }
        
        floor_price = self.calculate_floor_price(cost)
        max_price = self.calculate_max_price(cost)
        
        metadata['floor_price'] = floor_price
        metadata['max_price'] = max_price
        
        lowest_competitor = self.get_lowest_competitor_price(competitor_prices)
        metadata['lowest_competitor'] = lowest_competitor
        
        # ===================================================================
        # ВИПАДОК 1: Є КОНКУРЕНТИ
        # ===================================================================
        if lowest_competitor is not None:
            below_amount = self.coefficients.get('below_lowest', 1.0)
            suggested_raw = lowest_competitor - below_amount
            
            # Застосувати floor/max межі
            if suggested_raw < floor_price:
                suggested = floor_price
                metadata['calculation_method'] = 'competitor_capped_at_floor'
                
            elif suggested_raw > max_price:
                suggested = max_price
                metadata['calculation_method'] = 'competitor_capped_at_max'
                
            else:
                suggested = suggested_raw
                metadata['calculation_method'] = 'competitor_based'
            
            # ✅ Округлити до 2 знаків після коми
            suggested = round(suggested, 2)
        
        # ===================================================================
        # ВИПАДОК 2: НЕМАЄ КОНКУРЕНТІВ
        # ===================================================================
        else:
            # ✅ ЗАЛИШИТИ Our Sales Price БЕЗ ЗМІН
            if current_price and current_price > 0:
                suggested = current_price
                metadata['calculation_method'] = 'no_competitors_keep_current'
            else:
                # Якщо Our Sales Price відсутня або 0 → використати floor
                suggested = round(floor_price, 2)
                metadata['calculation_method'] = 'no_competitors_use_floor'
        
        # Розрахувати зміну ціни (якщо є current_price)
        if current_price and current_price > 0:
            change = suggested - current_price
            change_percent = (change / current_price * 100) if current_price > 0 else 0
            metadata['current_price'] = current_price
            metadata['price_change'] = round(change, 2)
            metadata['price_change_percent'] = round(change_percent, 2)
        
        return suggested, metadata


class BatchPricingProcessor:
    """Процесор для пакетного розрахунку цін"""
    
    def __init__(self, engine: PricingEngine):
        self.engine = engine
    
    def _safe_float(self, value, field_name: str = "value") -> float:
        """
        Безпечна конвертація в float
        Обробка: коми як десяткового роздільника, None, порожніх строк
        """
        if value is None or value == '':
            return 0.0
        
        try:
            # Якщо вже float/int
            if isinstance(value, (float, int)):
                return float(value)
            
            # Якщо string - обробити кому як десятковий роздільник
            if isinstance(value, str):
                # "507,66" → "507.66"
                value_cleaned = value.strip().replace(',', '.')
                return float(value_cleaned)
            
            # Інший тип
            return float(value)
            
        except (ValueError, TypeError) as e:
            logger.warning(f"Failed to convert {field_name}='{value}' to float: {e}")
            return 0.0
    
    def process_products(self, products: List[Dict]) -> List[Dict]:
        """
        Обробити список товарів
        
        Для кожного товару:
        1. Отримати cost, current_price (Our Sales Price), competitor prices
        2. Розрахувати suggested price
        3. Додати metadata
        """
        results = []
        error_count = 0
        
        for idx, product in enumerate(products):
            try:
                # ✅ Отримати вартість (Our Cost)
                cost = self._safe_float(
                    product.get('Our Cost') or product.get('cost') or product.get('Cost'),
                    'cost'
                )
                
                # ✅ Отримати поточну ціну (Our Sales Price)
                # Може бути з скрапера (our_current_price) або з таблиці
                current_price = self._safe_float(
                    product.get('our_current_price') or 
                    product.get('current_price') or 
                    product.get('Our Sales Price'),
                    'current_price'
                )
                
                # ✅ Зібрати ціни конкурентів
                competitor_prices = []
                for i in range(1, 4):
                    price = product.get(f'site{i}_price')
                    if price:
                        price_float = self._safe_float(price, f'site{i}_price')
                        if price_float > 0:
                            competitor_prices.append(price_float)
                
                # ✅ Розрахувати рекомендовану ціну
                suggested, metadata = self.engine.calculate_suggested_price(
                    cost, 
                    competitor_prices,
                    current_price if current_price > 0 else None
                )
                
                product['suggested_price'] = suggested
                product['pricing_metadata'] = metadata
                results.append(product)
                
            except Exception as e:
                error_count += 1
                logger.error(f"Failed to process product {idx+1}: {e}", exc_info=True)
                product['suggested_price'] = None
                product['pricing_metadata'] = {'error': str(e)}
                results.append(product)
        
        if error_count > 0:
            logger.warning(f"Processed with {error_count} errors out of {len(products)} products")
        
        return results
    
    def get_statistics(self, products: List[Dict]) -> Dict:
        """Статистика по товарах"""
        total = len(products)
        with_suggestions = [p for p in products if p.get('suggested_price')]
        
        # Безпечний розрахунок середніх
        costs = []
        suggestions = []
        
        for p in products:
            cost = self._safe_float(p.get('cost') or p.get('Our Cost'), 'cost')
            if cost > 0:
                costs.append(cost)
        
        for p in with_suggestions:
            suggested = self._safe_float(p.get('suggested_price'), 'suggested_price')
            if suggested > 0:
                suggestions.append(suggested)
        
        avg_cost = sum(costs) / len(costs) if costs else 0
        avg_suggested = sum(suggestions) / len(suggestions) if suggestions else 0
        
        return {
            'total_products': total,
            'with_suggestions': len(with_suggestions),
            'avg_cost': round(avg_cost, 2),
            'avg_suggested_price': round(avg_suggested, 2),
        }
