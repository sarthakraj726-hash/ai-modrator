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


@router.get(
    "/{creator_id}/persona",
    summary="Get creator persona settings",
)
async def get_creator_persona(
    creator_id: str,
    service: CreatorServiceDep,
) -> dict:
    from app.db.repositories.creator_ai_repo import CreatorAISettingsRepository

    repo = CreatorAISettingsRepository(service.session)
    settings = await repo.get_or_create(creator_id)
    return {
        "creator_id": creator_id,
        "persona_type": settings.persona_type,
        "persona_sliders": settings.persona_sliders,
        "custom_persona_prompt": settings.custom_persona_prompt,
        "ai_enabled": settings.ai_enabled,
        "ai_reply_enabled": settings.ai_reply_enabled,
    }


@router.put(
    "/{creator_id}/persona",
    summary="Update creator persona settings",
)
async def update_creator_persona(
    creator_id: str,
    payload: dict,
    service: CreatorServiceDep,
    admin: AdminUserDep,
) -> dict:
    from app.db.repositories.creator_ai_repo import CreatorAISettingsRepository

    repo = CreatorAISettingsRepository(service.session)
    settings = await repo.update_settings(
        creator_id=creator_id,
        persona_type=payload.get("persona_type"),
        persona_sliders=payload.get("persona_sliders"),
        custom_persona_prompt=payload.get("custom_persona_prompt"),
    )
    return {
        "creator_id": creator_id,
        "persona_type": settings.persona_type,
        "persona_sliders": settings.persona_sliders,
        "custom_persona_prompt": settings.custom_persona_prompt,
    }


@router.get(
    "/{creator_id}/moderation-policy",
    summary="Get creator moderation policy settings",
)
async def get_creator_moderation_policy(
    creator_id: str,
    service: CreatorServiceDep,
) -> dict:
    from app.db.repositories.creator_ai_repo import CreatorAISettingsRepository

    repo = CreatorAISettingsRepository(service.session)
    settings = await repo.get_or_create(creator_id)
    return {
        "creator_id": creator_id,
        "moderation_strictness": settings.moderation_strictness,
        "moderation_mode": settings.moderation_mode,
        "auto_moderation_enabled": settings.auto_moderation_enabled,
        "hitl_enabled": settings.hitl_enabled,
        "custom_rules": settings.custom_rules,
    }


@router.put(
    "/{creator_id}/moderation-policy",
    summary="Update creator moderation policy settings",
)
async def update_creator_moderation_policy(
    creator_id: str,
    payload: dict,
    service: CreatorServiceDep,
    admin: AdminUserDep,
) -> dict:
    from app.db.repositories.creator_ai_repo import CreatorAISettingsRepository

    repo = CreatorAISettingsRepository(service.session)
    settings = await repo.update_settings(
        creator_id=creator_id,
        moderation_strictness=payload.get("moderation_strictness"),
        moderation_mode=payload.get("moderation_mode"),
        auto_moderation_enabled=payload.get("auto_moderation_enabled"),
        hitl_enabled=payload.get("hitl_enabled"),
        custom_rules=payload.get("custom_rules"),
    )
    return {
        "creator_id": creator_id,
        "moderation_strictness": settings.moderation_strictness,
        "moderation_mode": settings.moderation_mode,
        "auto_moderation_enabled": settings.auto_moderation_enabled,
        "hitl_enabled": settings.hitl_enabled,
        "custom_rules": settings.custom_rules,
    }
