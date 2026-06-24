from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

from app.routers.dependencies import CurrentUser, DatabaseSession
from app.schemas.favorite import FavoriteRequest
from app.services.favorites import add_favorite, clear_favorites, favorite_status, list_favorites, remove_favorite
from app.utils.responses import success_response


router = APIRouter(prefix="/api/audio/favorites", tags=["favorites"])


@router.get("/check")
async def check_favorite(session: DatabaseSession, current_user: CurrentUser, audio_id: int = Query(alias="audioId", gt=0)) -> JSONResponse:
    is_favorite = await favorite_status(session, current_user, audio_id)
    return success_response({"audioId": audio_id, "isFavorite": is_favorite})


@router.post("")
async def create_favorite(payload: FavoriteRequest, session: DatabaseSession, current_user: CurrentUser) -> JSONResponse:
    await add_favorite(session, current_user, payload.audio_id)
    return success_response({"audioId": payload.audio_id, "isFavorite": True})


@router.delete("/{audio_id}")
async def delete_favorite(audio_id: int, session: DatabaseSession, current_user: CurrentUser) -> JSONResponse:
    await remove_favorite(session, current_user, audio_id)
    return success_response({"audioId": audio_id, "isFavorite": False})


@router.get("")
async def get_favorites(
    session: DatabaseSession,
    current_user: CurrentUser,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, alias="pageSize", ge=1, le=100),
) -> JSONResponse:
    rows, total = await list_favorites(session, current_user, page, page_size)
    return success_response(
        {
            "list": [
                {
                    "favoriteId": favorite.id,
                    "favoritedAt": favorite.created_at.isoformat(),
                    "id": resource.id,
                    "name": resource.name,
                    "text": resource.text,
                    "sourceType": resource.source_type,
                    "datasetName": resource.dataset_name,
                    "durationMs": resource.duration_ms,
                    "audioFormat": resource.audio_format,
                    "createdAt": resource.created_at.isoformat(),
                    "isFavorite": True,
                }
                for favorite, resource in rows
            ],
            "total": total,
            "hasMore": page * page_size < total,
        }
    )


@router.delete("")
async def delete_all_favorites(session: DatabaseSession, current_user: CurrentUser) -> JSONResponse:
    deleted_count = await clear_favorites(session, current_user)
    return success_response({"deletedCount": deleted_count})
