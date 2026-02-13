"""
SKU Matcher for Furniture Repricer
Comparing products by SKU

- First checks for a FULL match (the entire string)
- Then splits it into parts (if there is a delimiter)
- Processes int SKU (some scrapers return numbers)
"""

from typing import List, Dict, Optional
from difflib import SequenceMatcher
import logging

logger = logging.getLogger("sku_matcher")

class SKUMatcher:
    """Class for matching SKUs between products"""
    
    def __init__(self, config: Dict = None):
        self.config = config or {}
        self.delimiter = self.config.get('split_delimiter', ';')
        self.case_sensitive = self.config.get('case_sensitive', False)
        self.strategy = self.config.get('strategy', 'exact')
        self.fuzzy_threshold = self.config.get('fuzzy_threshold', 0.85)

    def remove_manufacturer_prefix(self, sku: str, source: str = None) -> str:
        """
        Remove manufacturer prefix from SKU
        
        [!] IMPORTANT: Remove the prefix for Coleman and 1StopBedrooms!
        Leave other sources (AFA, Emma Mason) unchanged.
        
        Args:
            sku: SKU with possible prefix
            source: SKU source (‘coleman’, ‘onestopbedrooms’, ‘afastores’, ‘emmamason’)
        
        Returns:
            SKU without prefix (for Coleman and 1StopBedrooms)
        """
        # Remove the prefix ONLY for Coleman and 1StopBedrooms!
        if source not in ('coleman', 'onestopbedrooms'):
            return sku
        
        if not sku or '-' not in sku:
            return sku
        
        # UNIVERSAL APPROACH: Always remove the first segment before the first hyphen.
        # This works for any prefixes.
        parts = sku.split('-', 1)  # Divide into the first segment and the rest
        
        if len(parts) == 2:
            logger.debug(f"Removed {source} prefix '{parts[0]}' from SKU: {sku} → {parts[1]}")
            return parts[1]
        
        return sku


    def normalize_sku(self, sku, source: str = None) -> str:
        """
        Normalize SKU
        
        Args:
            sku: SKU (can be str, int, float)
            source: SKU source for correct prefix handling
        
        Returns:
            Normalized SKU (lowercase, no prefixes for Coleman)
        """
        if not sku:
            return ""
        
        # Convert to string if it is int/float
        if isinstance(sku, (int, float)):
            sku = str(int(sku))
            logger.debug(f"Converted numeric SKU to string: {sku}")
        
        # Now you can safely work with strings
        sku = str(sku).strip()
        
        # Remove prefix ONLY for Coleman
        sku = self.remove_manufacturer_prefix(sku, source=source)
        
        if not self.case_sensitive:
            sku = sku.lower()
        
        return sku

    
    def split_sku(self, sku_string, source: str = None) -> List[str]:
        """
        Split SKU string into parts
        
        Args:
            sku_string: SKU or list of SKUs separated by a delimiter
            source: Source for correct prefix processing
                    [!] For Emma SKU, pass source=None to avoid removing the “prefix”
        """
        if not sku_string:
            return []
        
        # Normalize before split
        normalized = self.normalize_sku(sku_string, source=source)
        
        if not normalized:
            return []
        
        # Divide into parts
        skus = normalized.split(self.delimiter)
        
        # Remove empty and blank spaces
        result = [sku.strip() for sku in skus if sku.strip()]
        
        return result
    
    def exact_match(self, sku1, sku2, source: str = None) -> bool:
        """
        Exact SKU match
        
        Args:
            sku1: First SKU
            sku2: Second SKU
            source: Source for correct prefix processing
        """
        norm1 = self.normalize_sku(sku1, source=source)
        norm2 = self.normalize_sku(sku2, source=source)
        return norm1 == norm2
    
    def fuzzy_match(self, sku1, sku2, source: str = None) -> float:
        """Fuzzy matching (similarity)"""
        norm1 = self.normalize_sku(sku1, source=source)
        norm2 = self.normalize_sku(sku2, source=source)
        
        if not norm1 or not norm2:
            return 0.0
        
        return SequenceMatcher(None, norm1, norm2).ratio()
    
    def matches(self, sku1, sku2, source: str = None) -> bool:
        """
        Check whether SKU1 matches SKU2
        
        OPTIMIZED LOGIC for Coleman and 1StopBedrooms:
            1. First, check for a FULL match (the entire string)
            2. Split the Emma SKU at “;” and check each part
            3. For each part: remove the prefix from the Coleman/1StopBedrooms SKU and check again
        
        Args:
            sku1: Emma SKU (may contain multiple SKUs separated by “;”)
            sku2: Competitor SKU (Coleman, 1StopBedrooms, AFA)
            source: Source sku2 (‘coleman’, ‘onestopbedrooms’, ‘afastores’)
        """

        # STEP 1: Check for a PERFECT match (the entire string)
        if self.strategy == 'exact':
            if self.exact_match(sku1, sku2, source=source):
                logger.debug(f"[OK] Full SKU match: '{sku1}' == '{sku2}'")
                return True
        elif self.strategy == 'fuzzy':
            similarity = self.fuzzy_match(sku1, sku2, source=source)
            if similarity >= self.fuzzy_threshold:
                logger.debug(f"[OK] Full SKU fuzzy match: '{sku1}' ~= '{sku2}' (similarity: {similarity:.2f})")
                return True
        
        # STEP 2: Split Emma SKU into parts (if there is a “;”)
        sku1_list = self.split_sku(sku1, source=None)
        
        if not sku1_list:
            return False
        
        # If SKU1 did not contain a delimiter - already checked above
        if len(sku1_list) == 1 and self.delimiter not in str(sku1):

            # STEP 3: For a simple SKU, check with the prefix removed
            if source in ('coleman', 'onestopbedrooms'):
                # Normalize Emma SKU (without source)
                norm_sku1 = self.normalize_sku(sku1, source=None)
                # Normalize competitor SKU WITHOUT prefix
                norm_sku2_no_prefix = self.normalize_sku(sku2, source=source)
                
                if norm_sku1 == norm_sku2_no_prefix:
                    logger.debug(f"[OK] SKU match after prefix removal: '{sku1}' == '{sku2}' (without prefix)")
                    return True
            
            return False  # All options have already been checked
        
        # STEP 4: Check each part of Emma SKU
        # ═══════════════════════════════════════════════════════════════
        for emma_part in sku1_list:
            # First, check for a regular coincidence
            if self.strategy == 'exact':
                if self.exact_match(emma_part, sku2, source=source):
                    logger.debug(f"[OK] Partial SKU match: '{emma_part}' (from '{sku1}') == '{sku2}'")
                    return True
            elif self.strategy == 'fuzzy':
                similarity = self.fuzzy_match(emma_part, sku2, source=source)
                if similarity >= self.fuzzy_threshold:
                    logger.debug(f"[OK] Partial SKU fuzzy match: '{emma_part}' ~= '{sku2}' (similarity: {similarity:.2f})")
                    return True
            
            # If Coleman/1StopBedrooms - check WITHOUT prefix
            if source in ('coleman', 'onestopbedrooms'):
                norm_emma = self.normalize_sku(emma_part, source=None)
                norm_competitor_no_prefix = self.normalize_sku(sku2, source=source)
                
                if norm_emma == norm_competitor_no_prefix:
                    logger.debug(f"[OK] Partial SKU match after prefix removal: '{emma_part}' == '{sku2}' (without prefix)")
                    return True
        
        return False
    
    def find_matching_product(self, target_sku, products: List[Dict], 
                            sku_field: str = 'sku', source: str = None) -> Optional[Dict]:
        """
        Find a product in the list by SKU
        
        [!] WARNING: Returns the FIRST match found!
        To select the best price, use find_best_match()
        
        Args:
            target_sku: SKU for search
            products: List of products
            sku_field: Field with SKU in the product dictionary
            source: Source products (‘coleman’, ‘onestopbedrooms’, ‘afastores’)
        """
        for product in products:
            product_sku = product.get(sku_field, '')
            
            if self.matches(target_sku, product_sku, source=source):
                return product
        
        return None
    
    def find_all_matching_products(self, target_sku, products: List[Dict],
                                    sku_field: str = 'sku', source: str = None) -> List[Dict]:
        """
        Find ALL products that match target_sku
        
        Args:
            target_sku: SKU for search (may contain multiple items separated by a delimiter)
            products: List of competitor products
            sku_field: Field with SKU in the dictionary
            source: Source (‘coleman’, ‘onestopbedrooms’, ‘afastores’)
        
        Returns:
            List of ALL matching products (may be empty)
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
        Find the best match (with the lowest price)
        
        Logic:
            1. Finds ALL matching products
            2. Selects the one with the lowest price among them
            3. If none match, returns None
            
        Args:
            target_sku: SKU for search
            products: List of products
            sku_field: Field with SKU
            price_field: Field with price for comparison
            source: Source for matching logic
        
        Returns:
            Product with the lowest price or None
        """
        # Find all matches
        all_matches = self.find_all_matching_products(
            target_sku, 
            products, 
            sku_field=sku_field,
            source=source
        )
        
        if not all_matches:
            return None
        
        # If there is one match, return immediately
        if len(all_matches) == 1:
            return all_matches[0]
        
        # If there are several, choose the one with the lowest price
        logger.debug(f"Found {len(all_matches)} matches for SKU '{target_sku}', selecting best price...")
        
        best_product = None
        best_price = float('inf')
        
        for product in all_matches:
            price = product.get(price_field)
            
            # Convert price to float
            try:
                if isinstance(price, str):
                    price = float(price.replace(',', '.').replace('$', '').strip())
                elif isinstance(price, (int, float)):
                    price = float(price)
                else:
                    continue  # Skip if there is no price
                
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
    pass