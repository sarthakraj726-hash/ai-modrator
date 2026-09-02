"""Stream session lifecycle management API routes."""

from fastapi import APIRouter, status

from app.api.dependencies import AdminUserDep, StreamServiceDep
from app.api.schemas.stream import StreamConnectRequest, StreamSessionResponse

router = APIRouter(prefix="/streams", tags=["Streams"])


@router.post(
    "/connect",
    response_model=StreamSessionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Connect and launch an isolated stream worker session",
)
async def connect_stream(
    payload: StreamConnectRequest,
    service: StreamServiceDep,
    admin: AdminUserDep,
) -> StreamSessionResponse:
    session_record = await service.connect_stream(
        creator_id=payload.creator_id,
        youtube_video_id=payload.youtube_video_id,
        youtube_live_chat_id=payload.youtube_live_chat_id,
        actor_id=admin.user_id,
    )
    return StreamSessionResponse.model_validate(session_record)


@router.post(
    "/{session_id}/disconnect",
    response_model=StreamSessionResponse,
    summary="Stop stream worker session and finalize stream",
)
async def disconnect_stream(
    session_id: str,
    service: StreamServiceDep,
    admin: AdminUserDep,
) -> StreamSessionResponse:
    session_record = await service.disconnect_stream(session_id, actor_id=admin.user_id)
    return StreamSessionResponse.model_validate(session_record)


@router.post(
    "/{session_id}/restart",
    response_model=StreamSessionResponse,
    summary="Restart stream worker session",
)
async def restart_stream(
    session_id: str,
    service: StreamServiceDep,
    admin: AdminUserDep,
) -> StreamSessionResponse:
    session_record = await service.restart_stream(session_id, actor_id=admin.user_id)
    return StreamSessionResponse.model_validate(session_record)


@router.get(
    "/active",
    response_model=list[StreamSessionResponse],
    summary="List all currently active stream sessions",
)
async def list_active_streams(
    service: StreamServiceDep,
) -> list[StreamSessionResponse]:
    sessions = await service.list_active()
    return [StreamSessionResponse.model_validate(s) for s in sessions]


@router.get(
    "/{session_id}",
    response_model=StreamSessionResponse,
    summary="Get stream session details",
)
async def get_stream_session(
    session_id: str,
    service: StreamServiceDep,
) -> StreamSessionResponse:
    session_record = await service.get_stream(session_id)
    return StreamSessionResponse.model_validate(session_record)
