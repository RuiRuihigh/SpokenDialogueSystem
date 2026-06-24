"""OpenAI diarized transcription task creation and execution."""

import asyncio
import logging
from contextlib import suppress
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.database import get_session_factory
from app.config.settings import get_settings
from app.models.audio_resource import AudioResource
from app.models.transcription_task import TranscriptionTask
from app.models.user import User
from app.services.audio_delivery import resolve_audio_path
from app.utils.exceptions import AppError


logger = logging.getLogger(__name__)
_running_tasks: set[asyncio.Task[None]] = set()


def task_payload(task: TranscriptionTask) -> dict[str, Any]:
    return {
        "id": task.id,
        "audioResourceId": task.audio_resource_id,
        "provider": task.provider,
        "model": task.model_name,
        "status": task.status,
        "transcript": task.transcript,
        "segments": task.segments or [],
        "errorMessage": task.error_message,
        "createdAt": task.created_at.isoformat() if task.created_at else None,
        "startedAt": task.started_at.isoformat() if task.started_at else None,
        "completedAt": task.completed_at.isoformat() if task.completed_at else None,
    }


async def create_transcription_task(
    session: AsyncSession, *, resource: AudioResource, current_user: User
) -> TranscriptionTask:
    if resource.source_type != "upload" or resource.visibility != "private" or resource.owner_id != current_user.id:
        raise AppError(403, "Only your private uploads can be transcribed automatically.")
    if resource.file_size_bytes > get_settings().openai_asr_max_file_size_mb * 1024 * 1024:
        raise AppError(413, "Automatic transcription supports audio files up to 25 MB.")

    task = TranscriptionTask(
        audio_resource_id=resource.id,
        owner_id=current_user.id,
        provider="openai",
        model_name=get_settings().openai_asr_model,
        status="pending",
        segments=[],
    )
    session.add(task)
    await session.flush()
    await session.commit()
    await session.refresh(task)
    enqueue_transcription(task.id)
    return task


async def get_owned_transcription_task(
    session: AsyncSession, *, task_id: int, current_user: User
) -> TranscriptionTask:
    task = await session.get(TranscriptionTask, task_id)
    if task is None:
        raise AppError(404, "Transcription task not found.")
    if task.owner_id != current_user.id:
        raise AppError(403, "You cannot access this transcription task.")
    return task


def enqueue_transcription(task_id: int) -> None:
    """Run in-process for this deployment; the task row remains visible while it runs."""
    task = asyncio.create_task(run_transcription_task(task_id), name=f"transcription-{task_id}")
    _running_tasks.add(task)
    task.add_done_callback(_running_tasks.discard)


async def resume_queued_transcriptions() -> None:
    """Retry queued work after a normal backend restart."""
    async with get_session_factory()() as session:
        task_ids = list(
            (await session.scalars(
                select(TranscriptionTask.id).where(TranscriptionTask.status.in_(("pending", "processing")))
            )).all()
        )
        if task_ids:
            tasks = list(
                (await session.scalars(select(TranscriptionTask).where(TranscriptionTask.id.in_(task_ids)))).all()
            )
            for task in tasks:
                task.status = "pending"
                task.started_at = None
                task.completed_at = None
                task.error_message = None
            await session.commit()
    for task_id in task_ids:
        enqueue_transcription(task_id)


async def stop_transcription_tasks() -> None:
    for task in tuple(_running_tasks):
        task.cancel()
    if _running_tasks:
        with suppress(asyncio.CancelledError):
            await asyncio.gather(*_running_tasks, return_exceptions=True)


async def run_transcription_task(task_id: int) -> None:
    async with get_session_factory()() as session:
        task = await session.get(TranscriptionTask, task_id)
        if task is None or task.status not in {"pending", "processing"}:
            return
        resource = await session.get(AudioResource, task.audio_resource_id)
        if resource is None:
            await _mark_failed(session, task, "The uploaded audio is no longer available.")
            return
        task.status = "processing"
        task.started_at = _utcnow()
        task.error_message = None
        await session.commit()

        try:
            result = await asyncio.to_thread(_transcribe_file, resolve_audio_path(resource))
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.exception("Automatic transcription failed for task %s", task_id)
            await session.rollback()
            task = await session.get(TranscriptionTask, task_id)
            if task is not None:
                message = "Automatic transcription failed. Check the backend configuration and logs."
                if isinstance(exc, RuntimeError) and str(exc) == "OPENAI_API_KEY is not configured":
                    message = "OpenAI ASR is not configured. Add OPENAI_API_KEY, then recreate the backend container."
                await _mark_failed(session, task, message)
            return

        task = await session.get(TranscriptionTask, task_id)
        resource = await session.get(AudioResource, task.audio_resource_id) if task is not None else None
        if task is None or resource is None:
            return
        segments, transcript = result["segments"], result["transcript"]
        existing_metainfo = dict(resource.metainfo or {})
        existing_metainfo["asr"] = {
            "provider": "openai",
            "model": get_settings().openai_asr_model,
            "speakerLabels": sorted({segment["speaker"] for segment in segments}),
            "generatedAt": _utcnow().isoformat(),
        }
        resource.text = transcript
        resource.metainfo = existing_metainfo
        task.status = "completed"
        task.transcript = transcript
        task.segments = segments
        task.error_message = None
        task.completed_at = _utcnow()
        await session.commit()


async def _mark_failed(session: AsyncSession, task: TranscriptionTask, message: str) -> None:
    task.status = "failed"
    task.error_message = message
    task.completed_at = _utcnow()
    await session.commit()


def _transcribe_file(path: Path) -> dict[str, Any]:
    settings = get_settings()
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is not configured")
    try:
        from openai import OpenAI
    except ImportError as exc:  # pragma: no cover - covered by container dependency install
        raise RuntimeError("The OpenAI SDK is not installed") from exc

    client = OpenAI(api_key=settings.openai_api_key)
    with path.open("rb") as audio_file:
        response = client.audio.transcriptions.create(
            model=settings.openai_asr_model,
            file=audio_file,
            response_format="diarized_json",
            chunking_strategy="auto",
        )
    segments = _normalise_segments(_field(response, "segments", []))
    raw_text = str(_field(response, "text", "")).strip()
    transcript = "\n".join(f"{segment['speaker']}: {segment['text']}" for segment in segments if segment["text"])
    return {"segments": segments, "transcript": transcript or raw_text}


def _field(value: Any, name: str, default: Any) -> Any:
    return value.get(name, default) if isinstance(value, dict) else getattr(value, name, default)


def _normalise_segments(raw_segments: Any) -> list[dict[str, Any]]:
    speaker_names: dict[str, str] = {}
    normalised: list[dict[str, Any]] = []
    for raw_segment in raw_segments or []:
        text = str(_field(raw_segment, "text", "")).strip()
        if not text:
            continue
        raw_speaker = str(_field(raw_segment, "speaker", "unknown") or "unknown")
        speaker = speaker_names.setdefault(raw_speaker, f"Person{len(speaker_names) + 1}")
        normalised.append(
            {
                "speaker": speaker,
                "start": _number_or_none(_field(raw_segment, "start", None)),
                "end": _number_or_none(_field(raw_segment, "end", None)),
                "text": text,
            }
        )
    return normalised


def _number_or_none(value: Any) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)
