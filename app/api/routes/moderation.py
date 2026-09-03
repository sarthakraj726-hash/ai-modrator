"""API routes for moderation reviews and HITL actions."""

from typing import Any

from fastapi import APIRouter, HTTPException, Query, status

from app.api.dependencies import AdminUserDep, DBSessionDep
from app.api.schemas.moderation import (
    ModerationReviewResponse,
    ReviewResolutionRequest,
    ReviewResolutionResponse,
)
from app.db.repositories.review_repo import ReviewRepository
from app.moderation.hitl.service import HumanReviewService

router = APIRouter(prefix="/moderation", tags=["moderation"])


@router.get("/status")
async def get_moderation_status(
    admin: AdminUserDep,
) -> dict[str, Any]:
    """Return moderation subsystem operational status."""
    return {
        "status": "HEALTHY",
        "pipeline": "5-layer-progressive",
        "multilingual_support": ["en", "hi", "hinglish"],
        "hitl_enabled": True,
    }


@router.get("/reviews", response_model=list[ModerationReviewResponse])
async def list_pending_reviews(
    admin: AdminUserDep,
    session: DBSessionDep,
    creator_id: str = Query(...),
) -> list[ModerationReviewResponse]:
    """List unexpired pending human-in-the-loop review tickets for a creator."""
    service = HumanReviewService(session)
    reviews = await service.get_pending_reviews(creator_id)
    return [
        ModerationReviewResponse(
            id=r.id,
            creator_id=r.creator_id,
            stream_session_id=r.stream_session_id,
            message_id=r.message_id,
            author_channel_id=r.author_channel_id,
            author_display_name=r.author_display_name,
            message_text=r.message_text,
            status=r.status,
            risk_score=r.risk_score,
            confidence=r.confidence,
            severity=r.severity,
            recommended_action=r.recommended_action,
            final_action=r.final_action,
            reason_code=r.reason_code,
            reason=r.reason,
            language=r.language,
            context_summary=r.context_summary or {},
            expires_at=r.expires_at,
            resolved_at=r.resolved_at,
            resolved_by=r.resolved_by,
        )
        for r in reviews
    ]


@router.get("/reviews/{review_id}", response_model=ModerationReviewResponse)
async def get_review_detail(
    review_id: str,
    admin: AdminUserDep,
    session: DBSessionDep,
) -> ModerationReviewResponse:
    """Fetch details of a single review item."""
    repo = ReviewRepository(session)
    r = await repo.get_by_id(review_id)
    if not r:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Review ticket '{review_id}' not found.",
        )
    return ModerationReviewResponse(
        id=r.id,
        creator_id=r.creator_id,
        stream_session_id=r.stream_session_id,
        message_id=r.message_id,
        author_channel_id=r.author_channel_id,
        author_display_name=r.author_display_name,
        message_text=r.message_text,
        status=r.status,
        risk_score=r.risk_score,
        confidence=r.confidence,
        severity=r.severity,
        recommended_action=r.recommended_action,
        final_action=r.final_action,
        reason_code=r.reason_code,
        reason=r.reason,
        language=r.language,
        context_summary=r.context_summary or {},
        expires_at=r.expires_at,
        resolved_at=r.resolved_at,
        resolved_by=r.resolved_by,
    )


@router.post("/reviews/{review_id}/approve", response_model=ReviewResolutionResponse)
async def approve_moderation_review(
    review_id: str,
    payload: ReviewResolutionRequest,
    admin: AdminUserDep,
    session: DBSessionDep,
) -> ReviewResolutionResponse:
    """Approve a pending review item and execute the moderation action."""
    service = HumanReviewService(session)
    success, reason = await service.approve_review(
        review_id_prefix=review_id,
        moderator_id=payload.moderator_id,
        override_action=payload.override_action,
        notes=payload.notes,
    )
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unable to approve review: {reason}",
        )
    return ReviewResolutionResponse(
        success=True,
        review_id=review_id,
        status="APPROVED",
        message=f"Review successfully approved ({reason}).",
    )


@router.post("/reviews/{review_id}/deny", response_model=ReviewResolutionResponse)
async def deny_moderation_review(
    review_id: str,
    payload: ReviewResolutionRequest,
    admin: AdminUserDep,
    session: DBSessionDep,
) -> ReviewResolutionResponse:
    """Deny a pending review item (no moderation punishment applied)."""
    service = HumanReviewService(session)
    success, reason = await service.deny_review(
        review_id_prefix=review_id,
        moderator_id=payload.moderator_id,
        notes=payload.notes,
    )
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unable to deny review: {reason}",
        )
    return ReviewResolutionResponse(
        success=True,
        review_id=review_id,
        status="DENIED",
        message="Review successfully denied. Message permitted in chat.",
    )
