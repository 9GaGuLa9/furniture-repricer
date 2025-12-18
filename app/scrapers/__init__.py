"""
Scrapers package для Furniture Repricer
Модулі для парсингу даних з різних сайтів
"""

from .emmamason import EmmaMasonScraper
from .onestopbedrooms import OneStopBedroomsScraper
from .coleman import ColemanScraper
from .afa import AFAScraper

__all__ = [
    'EmmaMasonScraper',
    'OneStopBedroomsScraper',
    'ColemanScraper',
    'AFAScraper',
]
