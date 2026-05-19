"""
main.py — CLI Launcher
Run from BACKEND directory: python main.py
Delegates to app.main where the FastAPI app is defined.
"""

import uvicorn
from app.config import settings


if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_level=settings.log_level.lower(),
    )
