"""FastAPI main application entrypoint."""

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import (
    admin_router,
    ai_router,
    commands_router,
    creators_router,
    dashboard_alias_router,
    dashboard_router,
    health_router,
    moderation_router,
    streams_router,
    web_router,
    webhooks_router,
    youtube_router,
)
from app.core.config import get_settings
from app.core.exceptions import AppException
from app.core.lifecycle import lifespan
from app.core.logging import get_logger

logger = get_logger("app.main")


def create_application() -> FastAPI:
    """Application factory for Goddess AI / AI-Modrator."""
    settings = get_settings()

    app = FastAPI(
        title="Goddess AI / AI-Modrator",
        description="Production-grade multi-channel YouTube Live AI Co-Host + AI Moderator foundation",
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/docs" if not settings.is_production else None,
        redoc_url="/redoc" if not settings.is_production else None,
    )

    # 1. CORS Middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 2. Global Exception Handlers
    @app.exception_handler(AppException)
    async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
        logger.warning(
            f"AppException on {request.method} {request.url.path}: {exc.message} (status: {exc.status_code})"
        )
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "type": exc.__class__.__name__,
                    "message": exc.message,
                    "details": exc.details,
                }
            },
        )

    _last_error_log_times: dict[str, float] = {}

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        import time

        error_key = f"{request.method}:{request.url.path}:{type(exc).__name__}:{str(exc)[:80]}"
        now = time.time()
        last_logged = _last_error_log_times.get(error_key, 0.0)

        # Log full traceback at most once every 10 seconds per unique endpoint+error pattern
        if now - last_logged > 10.0:
            _last_error_log_times[error_key] = now
            if len(_last_error_log_times) > 200:
                _last_error_log_times.clear()
            logger.error(
                f"Unhandled exception on {request.method} {request.url.path}: {exc}",
                exc_info=True,
            )
        else:
            logger.debug(
                f"Throttled duplicate exception on {request.method} {request.url.path}: {exc}"
            )

        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": {
                    "type": "InternalServerError",
                    "message": "An unexpected server error occurred.",
                    "detail": str(exc) if not settings.is_production else "Internal server error",
                }
            },
        )

    # 3. Include Routers
    app.include_router(web_router)
    app.include_router(health_router)
    app.include_router(creators_router)
    app.include_router(streams_router)
    app.include_router(admin_router)
    app.include_router(webhooks_router)
    app.include_router(youtube_router)
    app.include_router(ai_router)
    app.include_router(moderation_router)
    app.include_router(commands_router)
    app.include_router(dashboard_router, prefix="/api/v1")
    app.include_router(dashboard_alias_router, prefix="/api/v1")

    return app


app = create_application()
