"""Services package — expose all service singletons."""
from app.services.cookie_manager import cookie_manager
from app.services.cloudflare_service import cloudflare_service
from app.services.browser_manager import browser_manager_service
from app.services.search_service import search_service
from app.services.scraper_service import scraper_service

__all__ = [
    "cookie_manager",
    "cloudflare_service",
    "browser_manager_service",
    "search_service",
    "scraper_service",
]
