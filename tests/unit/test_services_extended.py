"""Unit tests for services business logic."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import EntityAlreadyExistsError, EntityNotFoundError
from app.db.models.stream_session import StreamStatus
from app.services.creator_service import CreatorService
from app.services.health_service import HealthService
from app.services.stream_service import StreamService


@pytest.mark.asyncio
async def test_creator_service_duplicate_error(db_session: AsyncSession):
    service = CreatorService(db_session)
    await service.register_creator("UC_DUP", "Original")

    with pytest.raises(EntityAlreadyExistsError):
        await service.register_creator("UC_DUP", "Duplicate")


@pytest.mark.asyncio
async def test_creator_service_not_found(db_session: AsyncSession):
    service = CreatorService(db_session)
    with pytest.raises(EntityNotFoundError):
        await service.get_creator("non-existent-id")


@pytest.mark.asyncio
async def test_stream_service_restart_and_list(db_session: AsyncSession):
    c_service = CreatorService(db_session)
    creator = await c_service.register_creator("UC_STREAM_SRV", "Streamer")

    s_service = StreamService(db_session)
    stream = await s_service.connect_stream(creator.id, "vid_srv_1", "chat_srv_1")

    # Restart
    restarted = await s_service.restart_stream(stream.id)
    assert restarted.id == stream.id

    # List by creator
    streams = await s_service.list_by_creator(creator.id)
    assert len(streams) == 1

    # Disconnect
    disc = await s_service.disconnect_stream(stream.id)
    assert disc.status == "ENDED"


@pytest.mark.asyncio
async def test_creator_service_update_and_delete(db_session: AsyncSession):
    service = CreatorService(db_session)
    creator = await service.register_creator("UC_UPDATE_DEL", "Original Title", enabled=True)

    # Update title
    updated = await service.update_creator(creator.id, channel_name="New Title", enabled=False)
    assert updated.channel_name == "New Title"
    assert updated.enabled is False

    # List enabled (should not include this disabled one)
    enabled_creators = await service.creator_repo.list_enabled()
    assert not any(c.id == creator.id for c in enabled_creators)

    # Delete
    await service.delete_creator(creator.id)
    with pytest.raises(EntityNotFoundError):
        await service.get_creator(creator.id)


@pytest.mark.asyncio
async def test_stream_repository_methods(db_session: AsyncSession):
    c_service = CreatorService(db_session)
    creator = await c_service.register_creator("UC_STREAM_REPO", "Streamer")

    s_service = StreamService(db_session)
    stream = await s_service.connect_stream(creator.id, "vid_repo_find", "chat_repo_find")

    # get_by_video_id
    found = await s_service.stream_repo.get_by_video_id("vid_repo_find")
    assert found is not None
    assert found.id == stream.id

    # update_status
    updated = await s_service.stream_repo.update_status(stream.id, status=StreamStatus.RECONNECTING)
    assert updated.status == StreamStatus.RECONNECTING.value

    # non-existent update_status returns None
    none_res = await s_service.stream_repo.update_status("non-existent-session-id", status=StreamStatus.ERROR)
    assert none_res is None


@pytest.mark.asyncio
async def test_health_service_deep_diagnostics(db_session: AsyncSession):
    health = HealthService(session=db_session)
    system_health = await health.get_system_health()
    assert system_health["app_name"] == "goddess-ai-modrator"
    assert "dependencies" in system_health
    assert "youtube" in system_health
    assert system_health["youtube"]["quota_daily_limit"] == 4000
