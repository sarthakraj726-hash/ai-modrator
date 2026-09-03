"""API routes for AI status, budget metrics, and usage tracking."""

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, Query

from app.ai.budget import AIBudgetManager, get_ai_budget_manager
from app.ai.openrouter import get_ai_provider
from app.ai.provider import AIProvider
from app.api.dependencies import AdminUserDep, DBSessionDep
from app.api.schemas.ai import (
    AIBudgetResponse,
    AIStatusResponse,
    AIUsageSummaryResponse,
)
from app.core.config import Settings, get_settings
from app.db.repositories.ai_usage_repo import AIUsageRepository

router = APIRouter(prefix="/ai", tags=["ai"])


@router.get("/status", response_model=AIStatusResponse)
async def get_ai_status(
    admin: AdminUserDep,
    ai_provider: AIProvider = Depends(get_ai_provider),
    settings: Settings = Depends(get_settings),
) -> AIStatusResponse:
    """Return health status and model routing map for the AI provider."""
    is_healthy = await ai_provider.health_check()
    return AIStatusResponse(
        provider=ai_provider.get_provider_name(),
        is_healthy=is_healthy,
        default_model=settings.OPENROUTER_DEFAULT_MODEL,
        fast_model=settings.OPENROUTER_MODEL_FAST,
        primary_model=settings.OPENROUTER_MODEL_PRIMARY,
        fallback_model=settings.OPENROUTER_MODEL_FALLBACK,
    )


@router.get("/budget", response_model=AIBudgetResponse)
async def get_ai_budget(
    admin: AdminUserDep,
    budget_manager: AIBudgetManager = Depends(get_ai_budget_manager),
) -> AIBudgetResponse:
    """Return current daily AI request budget and rate limit statistics."""
    metrics = await budget_manager.get_metrics()
    return AIBudgetResponse(**metrics)


@router.get("/usage/{creator_id}", response_model=AIUsageSummaryResponse)
async def get_creator_usage(
    creator_id: str,
    session: DBSessionDep,
    admin: AdminUserDep,
    days: int = Query(default=7, ge=1, le=90),
) -> AIUsageSummaryResponse:
    """Return aggregated token and request usage for a creator."""
    repo = AIUsageRepository(session)
    since = datetime.now(UTC) - timedelta(days=days)
    summary = await repo.get_creator_usage_summary(creator_id, since=since)
    return AIUsageSummaryResponse(
        creator_id=creator_id,
        total_requests=summary["requests"],
        total_tokens=summary["total_tokens"],
    )
