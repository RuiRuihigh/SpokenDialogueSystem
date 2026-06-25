from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse, StreamingResponse

from app.routers.dependencies import CurrentUser, DatabaseSession
from app.schemas.speech_model import SpeechModelRequest
from app.services.audio_delivery import get_content_type, iter_file_range, parse_range_header, resolve_audio_path
from app.services.resource_access import get_readable_resource, list_readable_resources
from app.services.speech_model import create_speech_model_task, get_owned_speech_model_task, speech_task_payload
from app.services.transcription import create_transcription_task, get_owned_transcription_task, task_payload
from app.services.uploads import delete_owned_upload
from app.utils.responses import success_response


router = APIRouter(prefix="/api/audio/resources", tags=["audio resources"])


def resource_summary(resource) -> dict[str, object | None]:
    return {
        "id": resource.id,
        "name": resource.name,
        "text": resource.text,
        "sourceType": resource.source_type,
        "datasetName": resource.dataset_name,
        "durationMs": resource.duration_ms,
        "audioFormat": resource.audio_format,
        "createdAt": resource.created_at.isoformat(),
        "owner": {"id": resource.owner_id} if resource.owner_id is not None else None,
        "isFavorite": False,
    }


@router.get("")
async def list_audio_resources(
    session: DatabaseSession,
    current_user: CurrentUser,
    scope: str = Query("dataset"),
    dataset: str = Query("spokendialoguesum"),
    dataset_split: str | None = Query(None, alias="split", max_length=32),
    keyword: str | None = Query(None, max_length=256),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, alias="pageSize", ge=1, le=100),
) -> JSONResponse:
    resources, total, available_splits = await list_readable_resources(
        session,
        current_user,
        scope=scope,
        dataset_name=dataset,
        dataset_split=dataset_split,
        keyword=keyword,
        page=page,
        page_size=page_size,
    )
    return success_response(
        {
            "list": [resource_summary(resource) for resource in resources],
            "total": total,
            "hasMore": page * page_size < total,
            "availableSplits": available_splits,
        }
    )


@router.post("/{audio_id}/transcription")
async def request_transcription(audio_id: int, session: DatabaseSession, current_user: CurrentUser) -> JSONResponse:
    resource = await get_readable_resource(session, audio_id, current_user)
    task = await create_transcription_task(session, resource=resource, current_user=current_user)
    return success_response(task_payload(task), status_code=202)


@router.get("/transcriptions/{task_id}")
async def get_transcription(task_id: int, session: DatabaseSession, current_user: CurrentUser) -> JSONResponse:
    task = await get_owned_transcription_task(session, task_id=task_id, current_user=current_user)
    return success_response(task_payload(task))


@router.post("/{audio_id}/speech-tasks")
async def request_speech_model_task(
    audio_id: int,
    payload: SpeechModelRequest,
    session: DatabaseSession,
    current_user: CurrentUser,
) -> JSONResponse:
    resource = await get_readable_resource(session, audio_id, current_user)
    task = await create_speech_model_task(session, resource=resource, current_user=current_user, prompt=payload.prompt)
    return success_response(speech_task_payload(task), status_code=202)


@router.get("/speech-tasks/{task_id}")
async def get_speech_model_task(task_id: int, session: DatabaseSession, current_user: CurrentUser) -> JSONResponse:
    task = await get_owned_speech_model_task(session, task_id=task_id, current_user=current_user)
    return success_response(speech_task_payload(task))


@router.delete("/{audio_id}")
async def delete_audio_upload(audio_id: int, session: DatabaseSession, current_user: CurrentUser) -> JSONResponse:
    await delete_owned_upload(session, current_user, audio_id)
    return success_response(None, message="Upload deleted.")


@router.get("/{audio_id}")
async def get_audio_resource(audio_id: int, session: DatabaseSession, current_user: CurrentUser) -> JSONResponse:
    resource = await get_readable_resource(session, audio_id, current_user)
    return success_response(
        {
            "id": resource.id,
            "name": resource.name,
            "text": resource.text,
            "metainfo": resource.metainfo,
            "sourceType": resource.source_type,
            "datasetName": resource.dataset_name,
            "visibility": resource.visibility,
            "durationMs": resource.duration_ms,
            "audioFormat": resource.audio_format,
            "contentType": resource.content_type,
            "createdAt": resource.created_at.isoformat(),
            "owner": {"id": resource.owner_id} if resource.owner_id is not None else None,
            "isFavorite": False,
        },
    )


@router.get("/{audio_id}/content")
async def get_audio_content(
    audio_id: int,
    request: Request,
    session: DatabaseSession,
    current_user: CurrentUser,
) -> StreamingResponse:
    resource = await get_readable_resource(session, audio_id, current_user)
    path = resolve_audio_path(resource)
    file_size = path.stat().st_size
    requested_range = parse_range_header(request.headers.get("range"), file_size)
    if requested_range is None:
        start, end, status_code = 0, file_size - 1, 200
    else:
        start, end = requested_range
        status_code = 206
    headers = {"Accept-Ranges": "bytes", "Content-Length": str(end - start + 1)}
    if status_code == 206:
        headers["Content-Range"] = f"bytes {start}-{end}/{file_size}"
    return StreamingResponse(
        iter_file_range(path, start, end),
        status_code=status_code,
        media_type=get_content_type(resource, path),
        headers=headers,
    )
