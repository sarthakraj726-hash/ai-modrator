"""Creator management API routes."""

from fastapi import APIRouter, status

from app.api.dependencies import AdminUserDep, CreatorServiceDep
from app.api.schemas.creator import CreatorCreate, CreatorResponse, CreatorUpdate

router = APIRouter(prefix="/creators", tags=["Creators"])


@router.post(
    "",
    response_model=CreatorResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new YouTube creator",
)
async def create_creator(
    payload: CreatorCreate,
    service: CreatorServiceDep,
    admin: AdminUserDep,
) -> CreatorResponse:
    creator = await service.register_creator(
        youtube_channel_id=payload.youtube_channel_id,
        channel_name=payload.channel_name,
        enabled=payload.enabled,
        actor_id=admin.user_id,
    )
    return CreatorResponse.model_validate(creator)


@router.get(
    "",
    response_model=list[CreatorResponse],
    summary="List registered creators",
)
async def list_creators(
    service: CreatorServiceDep,
    limit: int = 50,
    offset: int = 0,
) -> list[CreatorResponse]:
    creators = await service.list_creators(limit=limit, offset=offset)
    return [CreatorResponse.model_validate(c) for c in creators]


@router.get(
    "/{creator_id}",
    response_model=CreatorResponse,
    summary="Get creator details",
)
async def get_creator(
    creator_id: str,
    service: CreatorServiceDep,
) -> CreatorResponse:
    creator = await service.get_creator(creator_id)
    return CreatorResponse.model_validate(creator)


@router.patch(
    "/{creator_id}",
    response_model=CreatorResponse,
    summary="Update creator configuration",
)
async def update_creator(
    creator_id: str,
    payload: CreatorUpdate,
    service: CreatorServiceDep,
    admin: AdminUserDep,
) -> CreatorResponse:
    creator = await service.update_creator(
        creator_id=creator_id,
        channel_name=payload.channel_name,
        enabled=payload.enabled,
        actor_id=admin.user_id,
    )
    return CreatorResponse.model_validate(creator)


@router.delete(
    "/{creator_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a creator",
)
async def delete_creator(
    creator_id: str,
    service: CreatorServiceDep,
    admin: AdminUserDep,
) -> None:
    await service.delete_creator(creator_id, actor_id=admin.user_id)


@router.post(
    "/{creator_id}/websub/subscribe",
    summary="Subscribe creator channel to YouTube WebSub hub",
)
async def subscribe_creator_websub(
    creator_id: str,
    service: CreatorServiceDep,
    admin: AdminUserDep,
    callback_url: str = "https://goddess-ai.up.railway.app/webhooks/youtube/websub",
) -> dict[str, str]:
    from app.youtube.websub.manager import get_websub_manager

    creator = await service.get_creator(creator_id)
    manager = get_websub_manager()
    await manager.subscribe_channel(
        creator_id=creator.id,
        channel_id=creator.youtube_channel_id,
        callback_url=callback_url,
        db_session=service.session,
    )
    return {
        "status": "subscription_requested",
        "creator_id": creator.id,
        "channel_id": creator.youtube_channel_id,
        "callback_url": callback_url,
    }


@router.post(
    "/{creator_id}/websub/unsubscribe",
    summary="Unsubscribe creator channel from YouTube WebSub hub",
)
async def unsubscribe_creator_websub(
    creator_id: str,
    service: CreatorServiceDep,
    admin: AdminUserDep,
    callback_url: str = "https://goddess-ai.up.railway.app/webhooks/youtube/websub",
) -> dict[str, str]:
    from app.youtube.websub.manager import get_websub_manager

    creator = await service.get_creator(creator_id)
    manager = get_websub_manager()
    success = await manager.unsubscribe_channel(
        channel_id=creator.youtube_channel_id,
        callback_url=callback_url,
        db_session=service.session,
    )
    return {
        "status": "unsubscribed" if success else "failed",
        "creator_id": creator.id,
        "channel_id": creator.youtube_channel_id,
    }
