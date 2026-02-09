"""
Pricing Engine for Furniture Repricer
"""

from typing import Dict, List, Optional, Tuple
import logging

logger = logging.getLogger("pricing")

class PricingEngine:
    """calculating prices"""
    
    def __init__(self, coefficients: Dict[str, float] = None):
        self.coefficients = coefficients or {
            'floor': 1.5,
            'below_lowest': 1.0,
            'max': 2.0
        }
    
    def calculate_floor_price(self, cost: float) -> float:
        """Min price = cost × floor_coef"""
        floor_coef = self.coefficients.get('floor', 1.5)
        return cost * floor_coef
    
    def calculate_max_price(self, cost: float) -> float:
        """Max price = cost × max_coef"""
        max_coef = self.coefficients.get('max', 2.0)
        return cost * max_coef
    
    def get_lowest_competitor_price(self, competitor_prices: List[float]) -> Optional[float]:
        """Find the lowest price among competitors"""
        valid_prices = [p for p in competitor_prices if p and p > 0]
        if not valid_prices:
            return None
        return min(valid_prices)
    
    def calculate_suggested_price(self, cost: float, competitor_prices: List[float],
                                    current_price: Optional[float] = None) -> Tuple[float, Dict]:
        """
        Calculate the recommended price
        
        Logic:
            - There are competitors → min(competitors) - $1.00 (taking into account floor/max)
            - There are no competitors → leave Our Sales Price UNCHANGED
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
        
        # CASE 1: THERE ARE COMPETITORS
        if lowest_competitor is not None:
            below_amount = self.coefficients.get('below_lowest', 1.0)
            suggested_raw = lowest_competitor - below_amount
            
            # Apply floor/max limits
            if suggested_raw < floor_price:
                suggested = floor_price
                metadata['calculation_method'] = 'competitor_capped_at_floor'
                
            elif suggested_raw > max_price:
                suggested = max_price
                metadata['calculation_method'] = 'competitor_capped_at_max'
                
            else:
                suggested = suggested_raw
                metadata['calculation_method'] = 'competitor_based'
            
            # Round to 2 decimal places
            suggested = round(suggested, 2)
        
        # CASE 2: NO COMPETITORS
        else:
            # LEAVE Our Sales Price UNCHANGED
            if current_price and current_price > 0:
                suggested = current_price
                metadata['calculation_method'] = 'no_competitors_keep_current'
            else:
                # If Our Sales Price is missing or 0 → use floor
                suggested = round(floor_price, 2)
                metadata['calculation_method'] = 'no_competitors_use_floor'
        
        # Calculate the price change (if current_price is available)
        if current_price and current_price > 0:
            change = suggested - current_price
            change_percent = (change / current_price * 100) if current_price > 0 else 0
            metadata['current_price'] = current_price
            metadata['price_change'] = round(change, 2)
            metadata['price_change_percent'] = round(change_percent, 2)
        
        return suggested, metadata


class BatchPricingProcessor:
    """Processor for batch price calculation"""
    
    def __init__(self, engine: PricingEngine):
        self.engine = engine
    
    def _safe_float(self, value, field_name: str = "value") -> float:
        '''Simple conversion - all values from Sheets are already floats'''
        if value is None:
            return 0.0
        
        if isinstance(value, (int, float)):
            return float(value)  # It's just a matter of time - just turn it back
        
        # If for some reason string (from scrapers)
        if isinstance(value, str):
            cleaned = value.strip().replace(',', '.').replace(' ', '')
            try:
                return float(cleaned) if cleaned else 0.0
            except:
                logger.warning(f"Cannot convert {field_name}='{value}'")
                return 0.0
        
        return 0.0

    def process_products(self, products: List[Dict]) -> List[Dict]:
        """
        Process the list of goods
        
        For each product:
            1. Obtain cost, current_price (Our Sales Price), competitor prices
            2. Calculate suggested price
            3. Add metadata
        """
        results = []
        error_count = 0
        
        for idx, product in enumerate(products):
            try:
                # Get the cost (Our Cost)
                cost = self._safe_float(
                    product.get('Our Cost') or product.get('cost') or product.get('Cost'),
                    'cost'
                )
                
                # Get the current price (Our Sales Price)
                current_price = self._safe_float(
                    product.get('our_current_price') or 
                    product.get('current_price') or 
                    product.get('Our Sales Price'),
                    'current_price'
                )
                
                # Collect competitors' prices
                competitor_prices = []
                for i in range(1, 6): 
                    price = product.get(f'site{i}_price')
                    if price:
                        price_float = self._safe_float(price, f'site{i}_price')
                        if price_float > 0:
                            competitor_prices.append(price_float)
                
                # Calculate the recommended price
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
        
        # Safe calculation of averages
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
