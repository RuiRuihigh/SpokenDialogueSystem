import mimetypes
from collections.abc import Iterator
from pathlib import Path

from app.config.settings import get_settings
from app.models.audio_resource import AudioResource
from app.utils.exceptions import AppError


CHUNK_SIZE = 64 * 1024


def resolve_audio_path(resource: AudioResource) -> Path:
    root = Path(get_settings().dataset_root if resource.source_type == "dataset" else get_settings().upload_root)
    root = root.resolve()
    path = (root / resource.storage_key).resolve()
    if root not in path.parents or not path.is_file():
        raise AppError(404, "音频文件不存在")
    return path


def parse_range_header(range_header: str | None, file_size: int) -> tuple[int, int] | None:
    if not range_header:
        return None
    if not range_header.startswith("bytes=") or "," in range_header:
        raise AppError(416, "不支持的 Range 请求")
    start_text, separator, end_text = range_header[6:].partition("-")
    if not separator or (not start_text and not end_text):
        raise AppError(416, "不支持的 Range 请求")
    try:
        if start_text:
            start = int(start_text)
            end = int(end_text) if end_text else file_size - 1
        else:
            suffix_length = int(end_text)
            if suffix_length <= 0:
                raise ValueError
            start = max(file_size - suffix_length, 0)
            end = file_size - 1
    except ValueError as exc:
        raise AppError(416, "不支持的 Range 请求") from exc
    if start < 0 or start >= file_size or end < start:
        raise AppError(416, "请求范围不满足")
    return start, min(end, file_size - 1)


def iter_file_range(path: Path, start: int, end: int) -> Iterator[bytes]:
    remaining = end - start + 1
    with path.open("rb") as source:
        source.seek(start)
        while remaining:
            chunk = source.read(min(CHUNK_SIZE, remaining))
            if not chunk:
                break
            remaining -= len(chunk)
            yield chunk


def get_content_type(resource: AudioResource, path: Path) -> str:
    return resource.content_type or mimetypes.guess_type(path.name)[0] or "application/octet-stream"
