"""Pydantic schemas for AI API endpoints."""

from pydantic import BaseModel


class AIStatusResponse(BaseModel):
    provider: str
    is_healthy: bool
    default_model: str
    fast_model: str
    primary_model: str
    fallback_model: str


class AIBudgetResponse(BaseModel):
    daily_requests_used: int
    daily_requests_limit: int
    stream_requests_limit: int
    user_requests_limit: int
    monthly_token_budget: int


class AIUsageSummaryResponse(BaseModel):
    creator_id: str
    total_requests: int
    total_tokens: int
