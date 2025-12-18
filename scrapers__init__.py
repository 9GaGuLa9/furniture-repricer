"""
Scrapers package для Furniture Repricer
Експорт всіх scrapers
"""

from .emmamason import EmmaMasonScraper, scrape_emmamason
from .onestopbedrooms import OneStopBedroomsScraper, scrape_onestopbedrooms
from .coleman import ColemanScraper, scrape_coleman
from .afa import AFAScraper, scrape_afa

__all__ = [
    'EmmaMasonScraper',
    'scrape_emmamason',
    'OneStopBedroomsScraper',
    'scrape_onestopbedrooms',
    'ColemanScraper',
    'scrape_coleman',
    'AFAScraper',
    'scrape_afa',
]
