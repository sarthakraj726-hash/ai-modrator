"""FastAPI dependency injection providers."""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rbac import UserContext
from app.core.security import verify_admin_secret
from app.db.session import get_db_session
from app.services.creator_service import CreatorService
from app.services.health_service import HealthService
from app.services.stream_service import StreamService

# Type annotations for clean route handlers
DBSessionDep = Annotated[AsyncSession, Depends(get_db_session)]
AdminUserDep = Annotated[UserContext, Depends(verify_admin_secret)]


def get_creator_service(session: DBSessionDep) -> CreatorService:
    return CreatorService(session)


def get_stream_service(session: DBSessionDep) -> StreamService:
    return StreamService(session)


def get_health_service(session: DBSessionDep) -> HealthService:
    return HealthService(session=session)


CreatorServiceDep = Annotated[CreatorService, Depends(get_creator_service)]
StreamServiceDep = Annotated[StreamService, Depends(get_stream_service)]
HealthServiceDep = Annotated[HealthService, Depends(get_health_service)]
