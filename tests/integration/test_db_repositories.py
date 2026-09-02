"""Integration tests for Database repositories."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.stream_session import StreamStatus
from app.db.models.system_event import SystemSeverity
from app.db.repositories.audit_repo import AuditRepository
from app.db.repositories.creator_repo import CreatorRepository
from app.db.repositories.stream_repo import StreamRepository
from app.db.repositories.system_event_repo import SystemEventRepository


@pytest.mark.asyncio
async def test_database_repositories_crud(db_session: AsyncSession):
    creator_repo = CreatorRepository(db_session)
    stream_repo = StreamRepository(db_session)
    audit_repo = AuditRepository(db_session)
    sys_repo = SystemEventRepository(db_session)

    # 1. Creator CRUD
    creator = await creator_repo.create(
        youtube_channel_id="UC_REPO_TEST",
        channel_name="Repo Test Creator",
    )
    assert creator.id is not None

    found_creator = await creator_repo.get_by_youtube_channel_id("UC_REPO_TEST")
    assert found_creator is not None
    assert found_creator.id == creator.id

    # 2. Stream Session CRUD
    stream = await stream_repo.create(
        creator_id=creator.id,
        youtube_video_id="vid_12345",
        status=StreamStatus.ACTIVE.value,
    )
    assert stream.id is not None

    streams = await stream_repo.list_by_creator(creator.id)
    assert len(streams) == 1

    # 3. Audit log
    audit = await audit_repo.log_event(
        event_type="TEST_ACTION",
        actor_type="DEVELOPER",
        creator_id=creator.id,
        stream_session_id=stream.id,
        payload={"action": "test"},
    )
    assert audit.id is not None

    # 4. System Event
    sys_evt = await sys_repo.log_system_event(
        event_type="TEST_WARNING",
        message="Test alert",
        severity=SystemSeverity.WARNING,
    )
    assert sys_evt.id is not None
