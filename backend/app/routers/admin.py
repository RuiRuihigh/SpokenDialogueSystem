from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

from app.routers.dependencies import CurrentAdmin, DatabaseSession
from app.schemas.admin import UpdateUserStatusRequest
from app.services.admin import dataset_statistics, list_users, set_user_active
from app.services.auth import user_payload
from app.utils.responses import success_response


router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/users")
async def get_users(
    session: DatabaseSession,
    _: CurrentAdmin,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, alias="pageSize", ge=1, le=100),
) -> JSONResponse:
    users, total = await list_users(session, page, page_size)
    return success_response(
        {
            "list": [{**user_payload(user), "isActive": user.is_active} for user in users],
            "total": total,
            "hasMore": page * page_size < total,
        }
    )


@router.patch("/users/{user_id}/status")
async def update_user_status(
    user_id: int,
    payload: UpdateUserStatusRequest,
    session: DatabaseSession,
    current_admin: CurrentAdmin,
) -> JSONResponse:
    user = await set_user_active(session, target_id=user_id, is_active=payload.is_active, actor=current_admin)
    return success_response({**user_payload(user), "isActive": user.is_active})


@router.get("/datasets/{dataset_name}/stats")
async def get_dataset_stats(dataset_name: str, session: DatabaseSession, _: CurrentAdmin) -> JSONResponse:
    return success_response(await dataset_statistics(session, dataset_name))
