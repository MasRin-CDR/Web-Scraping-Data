"""Routes package — modular FastAPI route modules."""
from app.routes.warmup import router as warmup_router
from app.routes.search import router as search_router
from app.routes.detail import router as detail_router

__all__ = ["warmup_router", "search_router", "detail_router"]
