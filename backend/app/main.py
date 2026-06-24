import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from redis.exceptions import RedisError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.config.database import dispose_database, get_session_factory
from app.config.redis import close_redis, get_redis
from app.routers import admin, audio_resources, favorites, uploads, users
from app.services.transcription import resume_queued_transcriptions, stop_transcription_tasks
from app.utils.exceptions import AppError
from app.utils.responses import error_response, success_response


logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Connections are lazy so /health can diagnose unavailable dependencies.
    get_redis()
    try:
        await resume_queued_transcriptions()
    except SQLAlchemyError:
        # Keep the application bootable before a freshly deployed Alembic revision is applied.
        logger.warning("Transcription task recovery skipped until database migrations are current", exc_info=True)
    yield
    await stop_transcription_tasks()
    await close_redis()
    await dispose_database()


app = FastAPI(
    title="SpokenDialogueSystem API",
    version="0.1.0",
    description="Protected spoken-dialogue dataset service.",
    lifespan=lifespan,
)


@app.exception_handler(AppError)
async def handle_app_error(_: Request, exc: AppError) -> JSONResponse:
    return error_response(exc.status_code, exc.message, exc.data)


@app.exception_handler(StarletteHTTPException)
async def handle_http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
    if isinstance(exc.detail, str):
        return error_response(exc.status_code, exc.detail)
    return error_response(exc.status_code, "请求失败", exc.detail)


@app.exception_handler(RequestValidationError)
async def handle_validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
    return error_response(422, "请求参数校验失败", {"errors": exc.errors()})


@app.exception_handler(SQLAlchemyError)
async def handle_database_error(_: Request, exc: SQLAlchemyError) -> JSONResponse:
    logger.exception("Database operation failed", exc_info=exc)
    return error_response(500, "数据库操作失败")


@app.exception_handler(Exception)
async def handle_unexpected_error(_: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled application error", exc_info=exc)
    return error_response(500, "服务器内部错误")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Accept-Ranges", "Content-Length", "Content-Range"],
)

app.include_router(users.router)
app.include_router(audio_resources.router)
app.include_router(admin.router)
app.include_router(favorites.router)
app.include_router(uploads.router)


@app.get("/", tags=["system"])
async def root() -> JSONResponse:
    return success_response({"message": "SpokenDialogueSystem backend is running"})


@app.get("/health", tags=["system"])
async def health_check() -> JSONResponse:
    async def check_database() -> str:
        try:
            async with get_session_factory()() as session:
                await session.execute(text("SELECT 1"))
            return "ok"
        except (SQLAlchemyError, OSError, asyncio.TimeoutError):
            logger.warning("Health check: database unavailable", exc_info=True)
            return "unavailable"

    async def check_redis() -> str:
        try:
            await get_redis().ping()
            return "ok"
        except (RedisError, OSError, asyncio.TimeoutError):
            logger.warning("Health check: Redis unavailable", exc_info=True)
            return "unavailable"

    db_status, redis_status = await asyncio.gather(check_database(), check_redis())
    dependencies = {"app": "ok", "db": db_status, "redis": redis_status}
    is_healthy = all(status == "ok" for status in dependencies.values())
    return success_response(
        {"status": "ok" if is_healthy else "degraded", "dependencies": dependencies},
        status_code=200 if is_healthy else 503,
        message="success" if is_healthy else "部分依赖不可用",
    )
