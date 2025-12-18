"""
Pricing Engine для Furniture Repricer
Розрахунок рекомендованих цін на основі формули та цін конкурентів
"""

from typing import Dict, List, Optional, Tuple
from .logger import get_logger

logger = get_logger("pricing")


class PricingEngine:
    """Движок для розрахунку цін"""
    
    def __init__(self, coefficients: Dict[str, float] = None):
        """
        Ініціалізація pricing engine
        
        Args:
            coefficients: Коефіцієнти {
                'floor': 1.5,       # Мінімальна маржа
                'below_lowest': 1.0, # На скільки $ нижче конкурента
                'max': 2.0          # Максимальна маржа
            }
        """
        self.coefficients = coefficients or {
            'floor': 1.5,
            'below_lowest': 1.0,
            'max': 2.0
        }
        logger.info(f"Pricing engine initialized with coefficients: {self.coefficients}")
    
    def update_coefficients(self, coefficients: Dict[str, float]):
        """
        Оновити коефіцієнти
        
        Args:
            coefficients: Нові коефіцієнти
        """
        self.coefficients.update(coefficients)
        logger.info(f"Coefficients updated: {self.coefficients}")
    
    def calculate_floor_price(self, cost: float) -> float:
        """
        Розрахувати мінімальну ціну (Floor)
        
        Args:
            cost: Собівартість (Our Cost)
        
        Returns:
            Мінімальна ціна
        """
        floor_coef = self.coefficients.get('floor', 1.5)
        floor_price = cost * floor_coef
        
        logger.debug(f"Floor price: ${cost} × {floor_coef} = ${floor_price:.2f}")
        return floor_price
    
    def calculate_max_price(self, cost: float) -> float:
        """
        Розрахувати максимальну ціну (Max)
        
        Args:
            cost: Собівартість (Our Cost)
        
        Returns:
            Максимальна ціна
        """
        max_coef = self.coefficients.get('max', 2.0)
        max_price = cost * max_coef
        
        logger.debug(f"Max price: ${cost} × {max_coef} = ${max_price:.2f}")
        return max_price
    
    def get_lowest_competitor_price(self, competitor_prices: List[float]) -> Optional[float]:
        """
        Знайти найнижчу ціну серед конкурентів
        
        Args:
            competitor_prices: Список цін конкурентів
        
        Returns:
            Найнижча ціна або None якщо немає цін
        """
        # Фільтрувати валідні ціни (більше 0)
        valid_prices = [p for p in competitor_prices if p and p > 0]
        
        if not valid_prices:
            logger.debug("No valid competitor prices found")
            return None
        
        lowest = min(valid_prices)
        logger.debug(f"Lowest competitor price: ${lowest:.2f} from {valid_prices}")
        return lowest
    
    def calculate_suggested_price(
        self,
        cost: float,
        competitor_prices: List[float],
        current_price: Optional[float] = None
    ) -> Tuple[float, Dict[str, any]]:
        """
        Розрахувати рекомендовану ціну
        
        Args:
            cost: Собівартість (Our Cost)
            competitor_prices: Список цін конкурентів
            current_price: Поточна ціна (опціонально)
        
        Returns:
            (suggested_price, metadata) де metadata містить деталі розрахунку
        """
        metadata = {
            'cost': cost,
            'competitors_count': len([p for p in competitor_prices if p and p > 0]),
            'calculation_method': None,
            'floor_price': None,
            'max_price': None,
            'lowest_competitor': None,
            'suggested_raw': None
        }
        
        # Розрахувати Floor та Max
        floor_price = self.calculate_floor_price(cost)
        max_price = self.calculate_max_price(cost)
        
        metadata['floor_price'] = floor_price
        metadata['max_price'] = max_price
        
        # Знайти найнижчу ціну конкурента
        lowest_competitor = self.get_lowest_competitor_price(competitor_prices)
        metadata['lowest_competitor'] = lowest_competitor
        
        if lowest_competitor is None:
            # Немає цін конкурентів - використати середнє між floor та max
            suggested = (floor_price + max_price) / 2
            metadata['calculation_method'] = 'no_competitors_average'
            logger.info(f"No competitors, using average: ${suggested:.2f}")
        
        else:
            # Є ціни конкурентів - розрахувати за формулою
            below_amount = self.coefficients.get('below_lowest', 1.0)
            suggested_raw = lowest_competitor - below_amount
            metadata['suggested_raw'] = suggested_raw
            
            # Застосувати обмеження Floor та Max
            if suggested_raw < floor_price:
                suggested = floor_price
                metadata['calculation_method'] = 'capped_at_floor'
                logger.info(f"Price ${suggested_raw:.2f} below floor, using floor: ${floor_price:.2f}")
            
            elif suggested_raw > max_price:
                suggested = max_price
                metadata['calculation_method'] = 'capped_at_max'
                logger.info(f"Price ${suggested_raw:.2f} above max, using max: ${max_price:.2f}")
            
            else:
                suggested = suggested_raw
                metadata['calculation_method'] = 'competitor_based'
                logger.info(f"Suggested price: ${lowest_competitor:.2f} - ${below_amount} = ${suggested:.2f}")
        
        # Округлити до .99
        suggested = self.round_price(suggested)
        
        # Додати зміну якщо є поточна ціна
        if current_price:
            change = suggested - current_price
            change_percent = (change / current_price * 100) if current_price > 0 else 0
            metadata['current_price'] = current_price
            metadata['price_change'] = change
            metadata['price_change_percent'] = change_percent
        
        return suggested, metadata
    
    def round_price(self, price: float, round_to: float = 0.99) -> float:
        """
        Округлити ціну до .99, .95 або цілого числа
        
        Args:
            price: Ціна для округлення
            round_to: Значення для округлення (0.99, 0.95, 1.0)
        
        Returns:
            Округлена ціна
        """
        if round_to == 1.0:
            # Округлити до цілого числа
            return round(price)
        
        elif round_to == 0.99:
            # Округлити до .99
            import math
            return math.floor(price) + 0.99
        
        elif round_to == 0.95:
            # Округлити до .95
            import math
            return math.floor(price) + 0.95
        
        else:
            return price
    
    def validate_price(
        self,
        price: float,
        cost: float,
        min_allowed: float = 10.0,
        max_allowed: float = 50000.0
    ) -> Tuple[bool, Optional[str]]:
        """
        Валідувати ціну
        
        Args:
            price: Ціна для перевірки
            cost: Собівартість
            min_allowed: Мінімальна дозволена ціна
            max_allowed: Максимальна дозволена ціна
        
        Returns:
            (is_valid, error_message)
        """
        if price < min_allowed:
            return False, f"Price ${price:.2f} below minimum ${min_allowed}"
        
        if price > max_allowed:
            return False, f"Price ${price:.2f} above maximum ${max_allowed}"
        
        floor = self.calculate_floor_price(cost)
        if price < floor:
            return False, f"Price ${price:.2f} below floor ${floor:.2f}"
        
        max_price = self.calculate_max_price(cost)
        if price > max_price:
            return False, f"Price ${price:.2f} above max ${max_price:.2f}"
        
        return True, None
    
    def compare_prices(
        self,
        our_price: float,
        competitor_prices: Dict[str, float]
    ) -> Dict[str, any]:
        """
        Порівняти нашу ціну з конкурентами
        
        Args:
            our_price: Наша ціна
            competitor_prices: Словник {competitor_name: price}
        
        Returns:
            Словник з аналізом
        """
        valid_competitors = {k: v for k, v in competitor_prices.items() if v and v > 0}
        
        if not valid_competitors:
            return {
                'position': 'unknown',
                'price_difference': None,
                'is_cheapest': False,
                'is_most_expensive': False,
                'competitors_count': 0
            }
        
        competitor_values = list(valid_competitors.values())
        lowest = min(competitor_values)
        highest = max(competitor_values)
        
        is_cheapest = our_price < lowest
        is_most_expensive = our_price > highest
        
        # Позиція
        if is_cheapest:
            position = 'cheapest'
        elif is_most_expensive:
            position = 'most_expensive'
        else:
            position = 'competitive'
        
        # Різниця з найдешевшим
        difference = our_price - lowest
        
        return {
            'position': position,
            'price_difference': difference,
            'price_difference_percent': (difference / lowest * 100) if lowest > 0 else 0,
            'is_cheapest': is_cheapest,
            'is_most_expensive': is_most_expensive,
            'competitors_count': len(valid_competitors),
            'lowest_competitor': lowest,
            'highest_competitor': highest,
            'competitor_details': valid_competitors
        }
    
    def analyze_price_change(
        self,
        old_price: float,
        new_price: float,
        threshold_percent: float = 10.0
    ) -> Dict[str, any]:
        """
        Проаналізувати зміну ціни
        
        Args:
            old_price: Стара ціна
            new_price: Нова ціна
            threshold_percent: Поріг для попередження (%)
        
        Returns:
            Словник з аналізом
        """
        change = new_price - old_price
        change_percent = (change / old_price * 100) if old_price > 0 else 0
        
        # Визначити тип зміни
        if abs(change_percent) < 1.0:
            change_type = 'minimal'
        elif abs(change_percent) < threshold_percent:
            change_type = 'normal'
        else:
            change_type = 'significant'
        
        # Напрямок
        if change > 0:
            direction = 'increase'
        elif change < 0:
            direction = 'decrease'
        else:
            direction = 'no_change'
        
        # Чи потрібне попередження
        needs_warning = abs(change_percent) > threshold_percent
        
        return {
            'old_price': old_price,
            'new_price': new_price,
            'change': change,
            'change_percent': change_percent,
            'change_type': change_type,
            'direction': direction,
            'needs_warning': needs_warning
        }


class BatchPricingProcessor:
    """Процесор для пакетного розрахунку цін"""
    
    def __init__(self, engine: PricingEngine):
        """
        Ініціалізація процесора
        
        Args:
            engine: PricingEngine instance
        """
        self.engine = engine
        self.logger = get_logger("batch_pricing")
    
    def process_products(
        self,
        products: List[Dict[str, any]]
    ) -> List[Dict[str, any]]:
        """
        Обробити список товарів
        
        Args:
            products: Список товарів з полями:
                - sku
                - cost (Our Cost)
                - current_price (Our Sales Price)
                - site1_price, site2_price, site3_price
        
        Returns:
            Список товарів з додатковими полями:
                - suggested_price
                - pricing_metadata
        """
        results = []
        
        for product in products:
            try:
                cost = float(product.get('cost', 0))
                current_price = float(product.get('current_price') or 0)
                
                # Зібрати ціни конкурентів
                competitor_prices = []
                for i in range(1, 4):  # Site 1, 2, 3
                    price = product.get(f'site{i}_price')
                    if price:
                        try:
                            competitor_prices.append(float(price))
                        except (ValueError, TypeError):
                            pass
                
                # Розрахувати рекомендовану ціну
                suggested, metadata = self.engine.calculate_suggested_price(
                    cost,
                    competitor_prices,
                    current_price if current_price > 0 else None
                )
                
                # Додати результати
                product['suggested_price'] = suggested
                product['pricing_metadata'] = metadata
                
                results.append(product)
                
            except Exception as e:
                self.logger.error(f"Failed to process product {product.get('sku')}: {e}")
                product['suggested_price'] = None
                product['pricing_metadata'] = {'error': str(e)}
                results.append(product)
        
        return results
    
    def get_statistics(self, products: List[Dict[str, any]]) -> Dict[str, any]:
        """
        Отримати статистику по оброблених товарах
        
        Args:
            products: Оброблені товари
        
        Returns:
            Словник зі статистикою
        """
        total = len(products)
        
        # Товари з рекомендованими цінами
        with_suggestions = [p for p in products if p.get('suggested_price')]
        
        # Товари з змінами цін
        price_changes = [
            p for p in with_suggestions 
            if p.get('pricing_metadata', {}).get('price_change')
        ]
        
        # Середні ціни
        avg_cost = sum(float(p.get('cost', 0)) for p in products) / total if total > 0 else 0
        avg_suggested = sum(float(p.get('suggested_price', 0)) for p in with_suggestions) / len(with_suggestions) if with_suggestions else 0
        
        return {
            'total_products': total,
            'with_suggestions': len(with_suggestions),
            'price_changes': len(price_changes),
            'avg_cost': avg_cost,
            'avg_suggested_price': avg_suggested,
            'avg_margin': (avg_suggested / avg_cost - 1) * 100 if avg_cost > 0 else 0
        }


if __name__ == "__main__":
    # Тестування
    print("Testing Pricing Engine...")
    
    engine = PricingEngine({
        'floor': 1.5,
        'below_lowest': 1.0,
        'max': 2.0
    })
    
    # Тест 1: Нормальний випадок
    cost = 60.0
    competitors = [100.0, 95.0, 98.0]
    current = 99.0
    
    suggested, metadata = engine.calculate_suggested_price(cost, competitors, current)
    print(f"\nTest 1:")
    print(f"  Cost: ${cost}")
    print(f"  Competitors: {competitors}")
    print(f"  Current: ${current}")
    print(f"  Suggested: ${suggested:.2f}")
    print(f"  Method: {metadata['calculation_method']}")
    print(f"  Change: ${metadata.get('price_change', 0):.2f} ({metadata.get('price_change_percent', 0):.1f}%)")
    
    # Тест 2: Без конкурентів
    suggested2, metadata2 = engine.calculate_suggested_price(cost, [], current)
    print(f"\nTest 2 (no competitors):")
    print(f"  Suggested: ${suggested2:.2f}")
    print(f"  Method: {metadata2['calculation_method']}")
