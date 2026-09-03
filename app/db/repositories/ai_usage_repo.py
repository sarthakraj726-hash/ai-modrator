"""Repository for AIUsageRecord records."""

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.ai_usage import AIUsageRecord
from app.db.repositories.base import BaseRepository


class AIUsageRepository(BaseRepository[AIUsageRecord]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(AIUsageRecord, session)

    async def record_usage(
        self,
        model: str,
        task_type: str,
        prompt_tokens: int,
        completion_tokens: int,
        latency_ms: float,
        creator_id: str | None = None,
        stream_session_id: str | None = None,
        provider: str = "openrouter",
        success: bool = True,
        fallback_used: bool = False,
        error_message: str | None = None,
    ) -> AIUsageRecord:
        """Persist a single AI usage transaction."""
        record = AIUsageRecord(
            creator_id=creator_id,
            stream_session_id=stream_session_id,
            provider=provider,
            model=model,
            task_type=task_type,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
            latency_ms=latency_ms,
            success=success,
            fallback_used=fallback_used,
            error_message=error_message,
        )
        self.session.add(record)
        await self.session.flush()
        return record

    async def get_daily_token_usage(self, day_start: datetime) -> int:
        """Calculate total tokens consumed across all tasks since day_start."""
        result = await self.session.execute(
            select(func.coalesce(func.sum(AIUsageRecord.total_tokens), 0)).where(
                AIUsageRecord.created_at >= day_start
            )
        )
        return int(result.scalar() or 0)

    async def get_stream_token_usage(self, stream_session_id: str) -> int:
        """Calculate total tokens consumed for a specific stream session."""
        result = await self.session.execute(
            select(func.coalesce(func.sum(AIUsageRecord.total_tokens), 0)).where(
                AIUsageRecord.stream_session_id == stream_session_id
            )
        )
        return int(result.scalar() or 0)

    async def get_creator_usage_summary(self, creator_id: str, since: datetime) -> dict[str, int]:
        """Aggregate token and request counts for a creator."""
        result = await self.session.execute(
            select(
                func.count(AIUsageRecord.id),
                func.coalesce(func.sum(AIUsageRecord.total_tokens), 0),
            ).where(
                AIUsageRecord.creator_id == creator_id,
                AIUsageRecord.created_at >= since,
            )
        )
        row = result.first()
        if not row:
            return {"requests": 0, "total_tokens": 0}
        return {"requests": int(row[0] or 0), "total_tokens": int(row[1] or 0)}
