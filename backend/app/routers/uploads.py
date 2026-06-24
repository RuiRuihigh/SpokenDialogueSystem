from fastapi import APIRouter, File, Form, UploadFile
from fastapi.responses import JSONResponse

from app.routers.dependencies import CurrentUser, DatabaseSession
from app.config.settings import get_settings
from app.services.transcription import create_transcription_task, task_payload
from app.services.uploads import save_upload
from app.utils.exceptions import AppError
from app.utils.responses import success_response


router = APIRouter(prefix="/api/audio", tags=["uploads"])


@router.post("/uploads")
async def upload_audio(
    session: DatabaseSession,
    current_user: CurrentUser,
    file: UploadFile = File(...),
    name: str | None = Form(None),
    text: str | None = Form(None),
    transcription_mode: str = Form("manual"),
    metainfo: str | None = Form(None),
) -> JSONResponse:
    if transcription_mode not in {"manual", "asr"}:
        raise AppError(400, "transcriptionMode must be manual or asr.")
    if transcription_mode == "manual" and not (text or "").strip():
        raise AppError(400, "A transcript is required when manual transcription is selected.")
    resource = await save_upload(
        session,
        current_user,
        upload=file,
        name=name,
        text=text,
        metainfo_raw=metainfo,
        max_size_mb=get_settings().openai_asr_max_file_size_mb if transcription_mode == "asr" else None,
    )
    task = None
    if transcription_mode == "asr":
        task = await create_transcription_task(session, resource=resource, current_user=current_user)
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
            "createdAt": resource.created_at.isoformat() if resource.created_at else None,
            "transcriptionTask": task_payload(task) if task is not None else None,
        }
    )
