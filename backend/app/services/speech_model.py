"""Remote SpeechLLM task creation and execution."""

import asyncio
import base64
import logging
from contextlib import suppress
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.database import get_session_factory
from app.config.settings import get_settings
from app.models.audio_resource import AudioResource
from app.models.speech_model_task import SpeechModelTask
from app.models.user import User
from app.services.audio_delivery import get_content_type, resolve_audio_path
from app.utils.exceptions import AppError


logger = logging.getLogger(__name__)
_running_tasks: set[asyncio.Task[None]] = set()


class EndpointResponseError(RuntimeError):
    def __init__(self, message: str, raw_response: Any | None = None):
        super().__init__(message)
        self.raw_response = raw_response


def speech_task_payload(task: SpeechModelTask) -> dict[str, Any]:
    return {
        "id": task.id,
        "audioResourceId": task.audio_resource_id,
        "provider": task.provider,
        "model": task.model_name,
        "prompt": task.prompt,
        "status": task.status,
        "answer": task.answer,
        "errorMessage": task.error_message,
        "createdAt": task.created_at.isoformat() if task.created_at else None,
        "startedAt": task.started_at.isoformat() if task.started_at else None,
        "completedAt": task.completed_at.isoformat() if task.completed_at else None,
    }


async def create_speech_model_task(
    session: AsyncSession, *, resource: AudioResource, current_user: User, prompt: str
) -> SpeechModelTask:
    cleaned_prompt = prompt.strip()
    if not cleaned_prompt:
        raise AppError(400, "Prompt is required.")
    if len(cleaned_prompt) > 4000:
        raise AppError(400, "Prompt must be 4000 characters or fewer.")

    settings = get_settings()
    if not settings.speechllm_api_base_url:
        raise AppError(503, "SpeechLLM endpoint is not configured.")
    if resource.file_size_bytes > settings.speechllm_max_file_size_mb * 1024 * 1024:
        raise AppError(413, f"SpeechLLM supports audio files up to {settings.speechllm_max_file_size_mb} MB.")

    task = SpeechModelTask(
        audio_resource_id=resource.id,
        owner_id=current_user.id,
        provider="huggingface",
        model_name=settings.speechllm_model_id,
        prompt=cleaned_prompt,
        status="pending",
        raw_response={},
    )
    session.add(task)
    await session.flush()
    await session.commit()
    await session.refresh(task)
    enqueue_speech_model_task(task.id)
    return task


async def get_owned_speech_model_task(
    session: AsyncSession, *, task_id: int, current_user: User
) -> SpeechModelTask:
    task = await session.get(SpeechModelTask, task_id)
    if task is None:
        raise AppError(404, "SpeechLLM task not found.")
    if task.owner_id != current_user.id:
        raise AppError(403, "You cannot access this SpeechLLM task.")
    return task


def enqueue_speech_model_task(task_id: int) -> None:
    task = asyncio.create_task(run_speech_model_task(task_id), name=f"speech-model-{task_id}")
    _running_tasks.add(task)
    task.add_done_callback(_running_tasks.discard)


async def resume_queued_speech_model_tasks() -> None:
    async with get_session_factory()() as session:
        task_ids = list(
            (await session.scalars(
                select(SpeechModelTask.id).where(SpeechModelTask.status.in_(("pending", "processing")))
            )).all()
        )
        if task_ids:
            tasks = list(
                (await session.scalars(select(SpeechModelTask).where(SpeechModelTask.id.in_(task_ids)))).all()
            )
            for task in tasks:
                task.status = "pending"
                task.started_at = None
                task.completed_at = None
                task.error_message = None
            await session.commit()
    for task_id in task_ids:
        enqueue_speech_model_task(task_id)


async def stop_speech_model_tasks() -> None:
    for task in tuple(_running_tasks):
        task.cancel()
    if _running_tasks:
        with suppress(asyncio.CancelledError):
            await asyncio.gather(*_running_tasks, return_exceptions=True)


async def run_speech_model_task(task_id: int) -> None:
    async with get_session_factory()() as session:
        task = await session.get(SpeechModelTask, task_id)
        if task is None or task.status not in {"pending", "processing"}:
            return
        resource = await session.get(AudioResource, task.audio_resource_id)
        if resource is None:
            await _mark_failed(session, task, "The audio resource is no longer available.")
            return
        task.status = "processing"
        task.started_at = _utcnow()
        task.error_message = None
        await session.commit()

        try:
            path = resolve_audio_path(resource)
            result = await _call_remote_endpoint(path=path, resource=resource, prompt=task.prompt)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.exception("SpeechLLM inference failed for task %s", task_id)
            await session.rollback()
            task = await session.get(SpeechModelTask, task_id)
            if task is not None:
                if isinstance(exc, EndpointResponseError) and exc.raw_response is not None:
                    task.raw_response = _jsonable_response(exc.raw_response)
                await _mark_failed(session, task, _friendly_error(exc))
            return

        task = await session.get(SpeechModelTask, task_id)
        if task is None:
            return
        task.status = "completed"
        task.answer = result["answer"]
        task.raw_response = result["raw_response"]
        task.error_message = None
        task.completed_at = _utcnow()
        await session.commit()


async def _call_remote_endpoint(*, path: Path, resource: AudioResource, prompt: str) -> dict[str, Any]:
    settings = get_settings()
    url = _endpoint_url(settings.speechllm_api_base_url or "", settings.speechllm_api_path)
    headers = {"Authorization": f"Bearer {settings.speechllm_api_token}"} if settings.speechllm_api_token else {}
    timeout = httpx.Timeout(settings.speechllm_request_timeout_seconds)

    async with httpx.AsyncClient(timeout=timeout) as client:
        if settings.speechllm_request_mode == "json_base64":
            payload = {
                "inputs": {
                    "audio_base64": base64.b64encode(path.read_bytes()).decode("ascii"),
                    "prompt": _prompt_with_audio_marker(prompt),
                    "max_new_tokens": settings.speechllm_max_new_tokens,
                    "filename": path.name,
                    "content_type": get_content_type(resource, path),
                    "model": settings.speechllm_model_id,
                }
            }
            response = await client.post(url, headers=headers, json=payload)
        else:
            with path.open("rb") as audio_file:
                files = {"audio": (path.name, audio_file, get_content_type(resource, path))}
                data = {"prompt": prompt, "model": settings.speechllm_model_id}
                response = await client.post(url, headers=headers, data=data, files=files)

    if response.status_code >= 400:
        detail = response.text[:500]
        raise RuntimeError(f"SpeechLLM endpoint returned HTTP {response.status_code}: {detail}")

    content_type = response.headers.get("content-type", "")
    raw_response: Any
    if "application/json" in content_type:
        raw_response = response.json()
    else:
        raw_response = {"text": response.text}
    answer = _extract_answer(raw_response)
    error_message = _extract_error(raw_response)
    if error_message:
        raise EndpointResponseError(error_message, raw_response)
    if not answer:
        raise EndpointResponseError("SpeechLLM endpoint did not return a readable answer.", raw_response)
    return {"answer": answer, "raw_response": _jsonable_response(raw_response)}


def _endpoint_url(base_url: str, path: str) -> str:
    base = base_url.rstrip("/")
    suffix = path.strip()
    if not suffix:
        return base
    return f"{base}/{suffix.lstrip('/')}"


def _prompt_with_audio_marker(prompt: str) -> str:
    if "<|im_start|>" in prompt:
        return prompt
    if "<|AUDIO|>" in prompt:
        user_content = prompt.strip()
    else:
        user_content = f"<|audio_bos|><|AUDIO|><|audio_eos|>{prompt.strip()}"
    return f"<|im_start|>user\n{user_content}\n<|im_end|>\n<|im_start|>assistant\n"


def _extract_answer(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, list):
        for item in value:
            answer = _extract_answer(item)
            if answer:
                return answer
        return ""
    if isinstance(value, dict):
        for key in ("answer", "generated_text", "text", "output", "response", "result"):
            answer = _extract_answer(value.get(key))
            if answer:
                return answer
        if isinstance(value.get("choices"), list):
            for choice in value["choices"]:
                answer = _extract_answer(choice.get("message", {}).get("content") if isinstance(choice, dict) else choice)
                if answer:
                    return answer
    return ""


def _extract_error(value: Any) -> str:
    if isinstance(value, list):
        for item in value:
            message = _extract_error(item)
            if message:
                return message
    if isinstance(value, dict):
        for key in ("error", "detail", "message"):
            raw_message = value.get(key)
            if isinstance(raw_message, str) and raw_message.strip():
                return raw_message.strip()
        if isinstance(value.get("errors"), list):
            return "; ".join(str(error) for error in value["errors"][:3])
    return ""


def _jsonable_response(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    return {"value": value}


def _friendly_error(exc: Exception) -> str:
    message = str(exc)
    if isinstance(exc, httpx.ConnectError):
        return "SpeechLLM endpoint is unreachable. Check SPEECHLLM_API_BASE_URL."
    if isinstance(exc, httpx.TimeoutException):
        return "SpeechLLM endpoint timed out. Try a shorter audio file or increase the timeout."
    if "HTTP 401" in message or "HTTP 403" in message:
        return "SpeechLLM endpoint rejected the token. Check SPEECHLLM_API_TOKEN."
    if "HTTP 404" in message:
        return "SpeechLLM endpoint path was not found. Check SPEECHLLM_API_BASE_URL and SPEECHLLM_API_PATH."
    if "did not return a readable answer" in message:
        return "SpeechLLM endpoint responded, but the response format was not recognized."
    if isinstance(exc, EndpointResponseError) and message:
        return f"SpeechLLM endpoint error: {message[:500]}"
    return "SpeechLLM inference failed. Check the backend logs and endpoint configuration."


async def _mark_failed(session: AsyncSession, task: SpeechModelTask, message: str) -> None:
    task.status = "failed"
    task.error_message = message
    task.completed_at = _utcnow()
    await session.commit()


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)
