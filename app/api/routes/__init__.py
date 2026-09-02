"""API route definitions."""

from app.api.routes.admin import router as admin_router
from app.api.routes.creators import router as creators_router
from app.api.routes.health import router as health_router
from app.api.routes.streams import router as streams_router

__all__ = [
    "health_router",
    "creators_router",
    "streams_router",
    "admin_router",
]
