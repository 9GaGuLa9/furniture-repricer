"""
Pricing Engine для Furniture Repricer
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
        floor_coef = self.coefficients.get('floor', 1.5)
        return cost * floor_coef
    
    def calculate_max_price(self, cost: float) -> float:
        max_coef = self.coefficients.get('max', 2.0)
        return cost * max_coef
    
    def get_lowest_competitor_price(self, competitor_prices: List[float]) -> Optional[float]:
        valid_prices = [p for p in competitor_prices if p and p > 0]
        if not valid_prices:
            return None
        return min(valid_prices)
    
    def calculate_suggested_price(self, cost: float, competitor_prices: List[float],
                                 current_price: Optional[float] = None) -> Tuple[float, Dict]:
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
        
        if lowest_competitor is None:
            suggested = (floor_price + max_price) / 2
            metadata['calculation_method'] = 'no_competitors_average'
        else:
            below_amount = self.coefficients.get('below_lowest', 1.0)
            suggested_raw = lowest_competitor - below_amount
            
            if suggested_raw < floor_price:
                suggested = floor_price
                metadata['calculation_method'] = 'capped_at_floor'
            elif suggested_raw > max_price:
                suggested = max_price
                metadata['calculation_method'] = 'capped_at_max'
            else:
                suggested = suggested_raw
                metadata['calculation_method'] = 'competitor_based'
        
        suggested = self.round_price(suggested)
        
        if current_price:
            change = suggested - current_price
            change_percent = (change / current_price * 100) if current_price > 0 else 0
            metadata['current_price'] = current_price
            metadata['price_change'] = change
            metadata['price_change_percent'] = change_percent
        
        return suggested, metadata
    
    def round_price(self, price: float, round_to: float = 0.99) -> float:
        if round_to == 1.0:
            return round(price)
        elif round_to == 0.99:
            import math
            return math.floor(price) + 0.99
        else:
            return price

class BatchPricingProcessor:
    """Процесор для пакетного розрахунку цін"""
    
    def __init__(self, engine: PricingEngine):
        self.engine = engine
    
    def process_products(self, products: List[Dict]) -> List[Dict]:
        results = []
        for product in products:
            try:
                cost = float(product.get('cost', 0))
                current_price = float(product.get('current_price') or 0)
                
                competitor_prices = []
                for i in range(1, 4):
                    price = product.get(f'site{i}_price')
                    if price:
                        try:
                            competitor_prices.append(float(price))
                        except:
                            pass
                
                suggested, metadata = self.engine.calculate_suggested_price(
                    cost, competitor_prices,
                    current_price if current_price > 0 else None
                )
                
                product['suggested_price'] = suggested
                product['pricing_metadata'] = metadata
                results.append(product)
            except Exception as e:
                logger.error(f"Failed to process product: {e}")
                product['suggested_price'] = None
                product['pricing_metadata'] = {'error': str(e)}
                results.append(product)
        return results
    
    def get_statistics(self, products: List[Dict]) -> Dict:
        total = len(products)
        with_suggestions = [p for p in products if p.get('suggested_price')]
        
        avg_cost = sum(float(p.get('cost', 0)) for p in products) / total if total > 0 else 0
        avg_suggested = sum(float(p.get('suggested_price', 0)) for p in with_suggestions) / len(with_suggestions) if with_suggestions else 0
        
        return {
            'total_products': total,
            'with_suggestions': len(with_suggestions),
            'avg_cost': avg_cost,
            'avg_suggested_price': avg_suggested,
        }
