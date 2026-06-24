from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.routers.dependencies import CurrentUser, DatabaseSession
from app.schemas.user import CredentialsRequest
from app.services.auth import login_user, register_user, user_payload
from app.utils.responses import success_response


router = APIRouter(prefix="/api/user", tags=["users"])


@router.post("/register")
async def register(payload: CredentialsRequest, session: DatabaseSession) -> JSONResponse:
    user, token = await register_user(session, payload.username.strip(), payload.password)
    return success_response({"token": token, "userInfo": user_payload(user)})


@router.post("/login")
async def login(payload: CredentialsRequest, session: DatabaseSession) -> JSONResponse:
    user, token = await login_user(session, payload.username.strip(), payload.password)
    return success_response({"token": token, "userInfo": user_payload(user)})


@router.get("/info")
async def get_user_info(current_user: CurrentUser) -> JSONResponse:
    return success_response(user_payload(current_user))
