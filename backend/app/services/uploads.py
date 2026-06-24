import json
import logging
import re
import uuid
import wave
from pathlib import Path
from typing import Any

from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import get_settings
from app.models.audio_resource import AudioResource
from app.models.user import User
from app.utils.exceptions import AppError


CHUNK_SIZE = 64 * 1024
logger = logging.getLogger(__name__)
EXTENSIONS_BY_CONTENT_TYPE = {
    "audio/wav": {".wav"},
    "audio/mpeg": {".mp3"},
    "audio/mp4": {".m4a", ".mp4"},
    "audio/ogg": {".ogg"},
}


async def save_upload(
    session: AsyncSession,
    user: User,
    *,
    upload: UploadFile,
    name: str | None,
    text: str | None,
    metainfo_raw: str | None,
    max_size_mb: int | None = None,
) -> AudioResource:
    if not upload.filename:
        raise AppError(400, "必须提供音频文件")

    content_type = (upload.content_type or "").lower()
    allowed_types = {item.strip().lower() for item in get_settings().allowed_audio_types.split(",") if item.strip()}
    suffix = Path(upload.filename).suffix.lower()
    if content_type not in allowed_types:
        raise AppError(415, "不支持的音频 MIME 类型")
    if suffix not in EXTENSIONS_BY_CONTENT_TYPE.get(content_type, set()):
        raise AppError(415, "文件扩展名与音频 MIME 类型不匹配")
    metainfo = _parse_metainfo(metainfo_raw)

    root = Path(get_settings().upload_root).resolve()
    owner_directory = root / f"user_{user.id}"
    owner_directory.mkdir(parents=True, exist_ok=True)
    storage_key = f"user_{user.id}/{uuid.uuid4().hex}{suffix}"
    destination = (root / storage_key).resolve()
    if root not in destination.parents:
        raise AppError(400, "非法上传路径")

    max_size_bytes = (max_size_mb or get_settings().max_upload_size_mb) * 1024 * 1024
    size = 0
    header = b""
    try:
        with destination.open("xb") as target:
            while chunk := await upload.read(CHUNK_SIZE):
                size += len(chunk)
                if size > max_size_bytes:
                    raise AppError(413, "The audio file exceeds the allowed size for this upload mode.")
                if len(header) < 12:
                    header += chunk[: 12 - len(header)]
                target.write(chunk)
        if content_type == "audio/wav" and (len(header) < 12 or header[:4] != b"RIFF" or header[8:12] != b"WAVE"):
            raise AppError(415, "WAV 文件头无效")
        resource = AudioResource(
            name=_display_name(name, upload.filename),
            text=(text or "").strip(),
            metainfo=metainfo,
            source_type="upload",
            visibility="private",
            owner_id=user.id,
            dataset_name=None,
            dataset_split="private",
            storage_key=storage_key,
            content_type=content_type,
            audio_format=suffix.removeprefix("."),
            file_size_bytes=size,
            duration_ms=_wav_duration_ms(destination) if content_type == "audio/wav" else None,
        )
        session.add(resource)
        await session.flush()
        await session.commit()
        await session.refresh(resource)
        return resource
    except Exception:
        destination.unlink(missing_ok=True)
        raise
    finally:
        await upload.close()


async def delete_owned_upload(session: AsyncSession, user: User, resource_id: int) -> None:
    """Delete one private upload and its storage file without exposing other users' data."""
    resource = await session.get(AudioResource, resource_id)
    if resource is None:
        raise AppError(404, "Audio resource not found.")
    if resource.source_type != "upload" or resource.visibility != "private" or resource.owner_id != user.id:
        raise AppError(403, "You can delete only your own private uploads.")

    path = _upload_path(resource.storage_key)
    await session.delete(resource)
    await session.commit()

    try:
        path.unlink(missing_ok=True)
        _remove_empty_parent_directory(path.parent)
    except OSError:
        # The database and authorization record have already been removed. Retain no client-visible storage path.
        logger.exception("Could not remove uploaded audio file after deleting resource %s", resource_id)


def _upload_path(storage_key: str) -> Path:
    root = Path(get_settings().upload_root).resolve()
    path = (root / storage_key).resolve()
    if root not in path.parents:
        raise AppError(400, "Invalid upload storage path.")
    return path


def _remove_empty_parent_directory(directory: Path) -> None:
    try:
        directory.rmdir()
    except OSError:
        # It is expected for a user directory to contain other uploads.
        pass


def _parse_metainfo(raw: str | None) -> dict[str, Any]:
    if raw is None or not raw.strip():
        return {}
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise AppError(400, "metainfo 必须是 JSON 对象") from exc
    if not isinstance(value, dict):
        raise AppError(400, "metainfo 必须是 JSON 对象")
    return value


def _display_name(requested_name: str | None, original_filename: str) -> str:
    candidate = (requested_name or Path(original_filename).name).strip()
    candidate = Path(candidate).name
    candidate = re.sub(r"[\x00-\x1f]", "", candidate)
    if not candidate:
        raise AppError(400, "音频名称无效")
    return candidate[:255]


def _wav_duration_ms(path: Path) -> int | None:
    try:
        with wave.open(str(path), "rb") as source:
            return round(source.getnframes() * 1000 / source.getframerate())
    except (OSError, wave.Error, EOFError, ZeroDivisionError):
        return None
