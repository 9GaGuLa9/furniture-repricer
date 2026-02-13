"""
1StopBedrooms Scraper
Parses prices from 1stopbedrooms.com via GraphQL API for specific manufacturers
"""

import requests
import time
import logging
from typing import List, Dict, Optional
from datetime import datetime
from ..modules.error_logger import ScraperErrorMixin

logger = logging.getLogger("onestopbedrooms")

class OneStopBedroomsScraper(ScraperErrorMixin):
    """Scraper for 1stopbedrooms.com - collects by manufacturers"""

    BASE_URL = "https://www.1stopbedrooms.com"
    GRAPHQL_URL = "https://www.1stopbedrooms.com/graphql/1"
    BRANDS = [
        {"name": "Steve Silver", "slug": "brand/steve-silver"},
        {"name": "Martin Furniture", "slug": "brand/martin-furniture"},
        {"name": "Legacy Classic", "slug": "brand/legacy-classic"},
        {"name": "Aspenhome", "slug": "brand/aspenhome"},
        {"name": "ACME", "slug": "brand/acme"},
    ]

    GRAPHQL_QUERY = """
fragment fragmentImage on catalogSearchImage {
    style
    alt
    src
    sources { media srcset }
    classes
}
fragment fragmentDynamicAttribute on catalogSearchPrimaryDynamicAttributeInterface {
    __typename
    type
    ... on catalogSearchPrimaryDynamicAttributeTextType { count label }
    ... on catalogSearchPrimaryDynamicAttributeThumbnailType { additional items { image webId classes } }
    ... on catalogSearchPrimaryDynamicAttributeSwatchThumbnailType { additional items { image webId classes } }
}
fragment fragmentCatalogProduct on catalogSearchProductInterface {
    __typename
    id
    webId
    name
    labels
    outOfStock
    brand { id name }
    cat_names
    collection
    sku
    useInCriteoFeed
    slug
    url
    shippingType
    price { finalPrice msrp showMsrp getExcludePromo getSale }
    tags {
        allTags
        primaryDealTag
        primaryDealTagVisibility
        secondaryTag
        secondaryTagVisibility
        tertiaryTag
        tertiaryTagVisibility
        __typename
    }
    couponData { discount code }
    images { mainImage { ...fragmentImage } }
    reviews { number rating }
    mattressData { comfort height type top_type label }
    ... on catalogSearchProductDynamicItem {
        dynamicAttribute { ...fragmentDynamicAttribute }
        secondaryDynamicAttribute { ...fragmentDynamicAttribute }
    }
    freewg
}
query getListingData($slug: String!, $request: catalogSearchFilterInput, $zipcode: String) {
    listing {
        listingCategory(slug: $slug, request: $request, zipcode: $zipcode) {
            itemsCount
            perPage
            pages
            page
            header: title
            items {
                ...fragmentCatalogProduct
                ... on catalogSearchProductDynamicItem { items { ...fragmentCatalogProduct } }
            }
        }
        topSellerProducts(categorySlug: $slug) {
            webId
            title
            brand { name }
            url
            slug
            labels
            outOfStock
            price { price regularPrice finalPrice msrp showMsrp }
            reviews { number rating }
            images {
                mainImage {
                    style
                    alt
                    src
                    sources { media srcset }
                    classes
                }
            }
        }
    }
}
"""

    def __init__(self, config: dict, error_logger=None):
        self.config = config
        self.error_logger = error_logger
        self.scraper_name = "OneStopBedroomsScraper"
        self.delay_min = config.get('delay_min', 1.0)
        self.delay_max = config.get('delay_max', 3.0)
        self.retry_attempts = config.get('retry_attempts', 3)
        self.timeout = config.get('timeout', 20)

        self.stats = {
            'total_products': 0,
            'unique_products': 0,
            'errors': 0,
            'brands_processed': 0,
            'successful_retries': 0,      #  NEW
            'failed_requests': 0           #  NEW
        }

        # Track failed requests details
        self.failed_requests_list = []

        logger.info("1StopBedrooms scraper initialized (brand-based - FAST!)")

    def _random_delay(self):
        """Delay between requests"""
        import random
        time.sleep(random.uniform(self.delay_min, self.delay_max))

    def _safe_request(self, payload: dict, headers: dict,
                    brand_name: str = None, page: int = None) -> Optional[dict]:
        """
        Executes a GraphQL query with retry logic
            IMPROVED: Detailed logging for logs and Google Sheets

        Args:
            payload: GraphQL query
            headers: HTTP headers
            brand_name: Brand name (for logging)
            page: Page number (for logging)

        Returns:
            JSON dict or None if error
        """

        last_error = None
        last_status_code = None

        for attempt in range(self.retry_attempts):
            try:
                response = requests.post(
                    self.GRAPHQL_URL,
                    headers=headers,
                    json=payload,
                    timeout=self.timeout
                )
                response.raise_for_status()
                if attempt > 0:
                    logger.info(
                        f"[DONE] Retry SUCCESS - Brand: '{brand_name}', "
                        f"Page: {page} (succeeded on attempt {attempt + 1}/{self.retry_attempts})"
                    )
                    self.stats['successful_retries'] += 1

                return response.json()

            except requests.exceptions.HTTPError as e:
                last_error = e
                status_code = e.response.status_code
                last_status_code = status_code
                logger.warning(
                    f"[!]  HTTP {status_code} - Brand: '{brand_name}', "
                    f"Page: {page}, Attempt: {attempt + 1}/{self.retry_attempts}"
                )
                self.log_scraping_error(
                    error=e,
                    url=self.GRAPHQL_URL,
                    context={
                        'method': '_safe_request',
                        'brand': brand_name,
                        'page': page,
                        'attempt': f"{attempt + 1}/{self.retry_attempts}",
                        'status_code': status_code,
                        'query_type': 'GraphQL'
                    }
                )

            except Exception as e:
                last_error = e
                error_str = str(e)

                logger.warning(
                    f"[!]  Request error - Brand: '{brand_name}', "
                    f"Page: {page}, Attempt: {attempt + 1}/{self.retry_attempts}, "
                    f"Error: {error_str[:100]}"
                )
                self.log_scraping_error(
                    error=e,
                    url=self.GRAPHQL_URL,
                    context={
                        'method': '_safe_request',
                        'brand': brand_name,
                        'page': page,
                        'attempt': f"{attempt + 1}/{self.retry_attempts}",
                        'error_type': type(e).__name__
                    }
                )

            # Retry delay
            if attempt < self.retry_attempts - 1:
                time.sleep(5)
        if last_error:
            logger.error(
                f"[X] FINAL FAILURE - Brand: '{brand_name}', Page: {page} - "
                f"gave up after {self.retry_attempts} attempts"
            )

            # Track failed request
            self.failed_requests_list.append({
                'brand': brand_name,
                'page': page,
                'error': str(last_error)[:100],
                'status_code': last_status_code
            })
            self.stats['failed_requests'] += 1

        self.stats['errors'] += 1
        return None

    def _extract_products(self, items: List[dict], seen_skus: set) -> List[Dict[str, str]]:
        """Extracts items from the items list"""
        products = []

        for item in items:
            typename = item.get("__typename")

            # We determine the type of product
            if typename == "catalogSearchProductSimpleItem":
                sub_items = [item]
            elif typename == "catalogSearchProductDynamicItem":
                sub_items = item.get("items") or [item]
            elif typename == "catalogSearchProductBundleItem":
                sub_items = [item]
            else:
                logger.debug(f"Unknown product type: {typename}")
                sub_items = []

            # We process every sub-product
            for prod in sub_items:
                if not prod:
                    continue

                sku = prod.get("sku")
                if not sku or sku in seen_skus:
                    continue

                seen_skus.add(sku)

                # Extracting data
                brand = prod.get("brand", {})
                price_data = prod.get("price", {})

                products.append({
                    "sku": sku,
                    "brand": brand.get("name") if brand else None,
                    "price": price_data.get("finalPrice"),
                    "url": prod.get("url")
                })

        return products

    def _print_scraping_summary(self, products: List[Dict[str, str]], seen_skus: set):
        """
        Print detailed scraping statistics
            NEW: Shows successful retries, failed requests, detailed analysis

        Args:
            products: List of all collected products
            seen_skus: Set of unique SKUs
        """
        logger.info("")
        logger.info("="*70)
        logger.info("1STOPBEDROOMS SCRAPER SUMMARY")
        logger.info("="*70)

        # Main statistics
        logger.info(f"[DATA] STATISTICS:")
        logger.info(f"   Brands processed: {self.stats['brands_processed']}/{len(self.BRANDS)}")
        logger.info(f"   Total products: {len(products)}")
        logger.info(f"   Unique SKUs: {len(seen_skus)}")

        logger.info("")
        logger.info(f"[RETRY] RETRIES:")
        logger.info(f"   Total errors: {self.stats['errors']}")
        logger.info(f"   Successful retries: {self.stats['successful_retries']}")
        logger.info(f"   Failed requests: {self.stats['failed_requests']}")
        if self.stats['errors'] > 0:
            success_rate = (self.stats['successful_retries'] / self.stats['errors']) * 100
            logger.info(f"   Retry success rate: {success_rate:.1f}%")
        if self.failed_requests_list:
            logger.warning("")
            logger.warning(f"[!]  FAILED REQUESTS ({len(self.failed_requests_list)}):")

            # Show first 10
            for i, fr in enumerate(self.failed_requests_list[:10], 1):
                status = f"HTTP {fr['status_code']}" if fr['status_code'] else "Error"
                logger.warning(
                    f"   {i}. '{fr['brand']}' page {fr['page']} - "
                    f"{status}: {fr['error']}"
                )

            if len(self.failed_requests_list) > 10:
                remaining = len(self.failed_requests_list) - 10
                logger.warning(f"   ... and {remaining} more failed requests")

            logger.warning("")
            logger.warning("[i] TIP: Check 'Scraping_Errors' sheet in Google Sheets for full details")
            logger.warning("[i] TIP: Use grep 'FINAL FAILURE' in logs to see all failed requests")
        else:
            logger.info("")
            logger.info("[DONE] No failed requests - all retries successful!")

        logger.info("="*70)

    def scrape_brand(self, brand_info: dict, seen_skus: set) -> List[Dict[str, str]]:
        """Parses all products from one manufacturer"""
        brand_name = brand_info["name"]
        brand_slug = brand_info["slug"]

        logger.info(f"Processing brand: {brand_name} ({brand_slug})")

        brand_products = []
        page = 1

        headers = {
            "Content-Type": "application/json",
            "Accept": "*/*",
            "Origin": self.BASE_URL,
            "Referer": f"{self.BASE_URL}/{brand_slug}",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }

        # First request to find out the number of pages
        payload = {
            "operationName": "getListingData",
            "query": self.GRAPHQL_QUERY,
            "variables": {
                "slug": brand_slug,
                "request": {
                    "sortBy": "RELEVANCE",
                    "perPage": "PER_PAGE_48",
                    "page": 1,
                    "facet": []
                },
                "zipcode": "11229"
            }
        }

        data = self._safe_request(payload, headers,
                            brand_name=brand_name, page=1)
        if not data or "data" not in data:
            logger.error(f"Failed to get data for brand {brand_name}")
            return []

        try:
            listing = data["data"]["listing"]["listingCategory"]
            max_page = listing["pages"]
            items_count = listing["itemsCount"]

            logger.info(f"Brand {brand_name}: {items_count} items, {max_page} pages")

            # Remove products from the first page
            items = listing.get("items", [])
            products = self._extract_products(items, seen_skus)
            brand_products.extend(products)

            logger.info(f"  Page 1/{max_page}: found {len(products)} new products (total: {len(brand_products)})")

        except KeyError as e:
            logger.error(f"Missing data in response: {e}")
            return []

        # We will parse the rest of the pages.
        for page in range(2, max_page + 1):
            payload["variables"]["request"]["page"] = page

            data = self._safe_request(payload, headers,
                            brand_name=brand_name, page=page)

            if not data:
                logger.warning(f"Failed to load page {page}, skipping...")
                continue

            try:
                items = data["data"]["listing"]["listingCategory"]["items"]
                products = self._extract_products(items, seen_skus)
                brand_products.extend(products)

                logger.info(f"  Page {page}/{max_page}: found {len(products)} new products (total: {len(brand_products)})")

            except KeyError as e:
                logger.error(f"Missing data on page {page}: {e}")
                continue

            # Delay between pages
            if page < max_page:
                self._random_delay()

        logger.info(f"Brand {brand_name}: collected {len(brand_products)} unique products")
        self.stats['brands_processed'] += 1

        return brand_products

    def scrape_all_products(self) -> List[Dict[str, str]]:
        """Parses all products"""

        all_products = []
        seen_skus = set()

        try:
            for idx, brand_info in enumerate(self.BRANDS, 1):
                try:
                    products = self.scrape_brand(brand_info, seen_skus)
                    all_products.extend(products)

                except Exception as e:
                    self.log_scraping_error(
                        error=e,
                        context={'brand': brand_info['name']}
                    )
                    logger.error(f"Failed {brand_info['name']}: {e}")
                    continue

                time.sleep(2)

        except Exception as e:
            self.log_scraping_error(error=e, context={'stage': 'main'})
            raise
        self._print_scraping_summary(all_products, seen_skus)

        return all_products

    def get_stats(self) -> dict:
        """Returns statistics"""
        return self.stats.copy()


def scrape_onestopbedrooms(config: dict, error_logger=None) -> List[Dict[str, str]]:
    """Main function for parsing 1StopBedrooms"""
    scraper = OneStopBedroomsScraper(config, error_logger=error_logger)
    results = scraper.scrape_all_products()
    return results


if __name__ == "__main__":
    pass