"""API route definitions."""

from app.api.routes.admin import router as admin_router
from app.api.routes.ai import router as ai_router
from app.api.routes.creators import router as creators_router
from app.api.routes.health import router as health_router
from app.api.routes.moderation import router as moderation_router
from app.api.routes.streams import router as streams_router
from app.api.routes.webhooks import router as webhooks_router
from app.api.routes.youtube import router as youtube_router

__all__ = [
    "health_router",
    "creators_router",
    "streams_router",
    "admin_router",
    "webhooks_router",
    "youtube_router",
    "ai_router",
    "moderation_router",
]
