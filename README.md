# SpokenDialogueSystem

Docker-first scaffold for a protected spoken-dialogue dataset browser and future speechLLM integration.

## Included services

- `backend`: reserved FastAPI application container.
- `frontend`: reserved Vue/Vite application container.
- `db`: PostgreSQL 16 with a named persistent volume.
- `redis`: Redis 7 with a named persistent volume.

## Initial setup

1. Copy `.env.example` to `.env` and replace development secrets.
2. Put the local `spokendialoguesum` dataset under `data/spokendialoguesum/`.
3. Run `docker compose up --build`.

The backend now provides the shared infrastructure layer; the frontend remains an idle scaffold until its application is implemented.

## Backend infrastructure

The backend reads its settings from the Compose environment and exposes dependency-aware health status at `GET /health`. Responses use the documented `{ "code", "message", "data" }` envelope. The `data.dependencies` fields report `app`, `db`, and `redis` independently; a failed dependency produces HTTP `503` with `status: "degraded"`.

Run database migrations after starting the services:

```bash
docker compose exec backend alembic upgrade head
```

## Authentication and resource access

`POST /api/user/register` and `POST /api/user/login` return a persisted Bearer token. Send it as `Authorization: Bearer <token>` to call `GET /api/user/info` and protected audio-resource endpoints. Dataset resources are available to every authenticated user; `private` resources are available only to their `owner_id`.

## Optional automatic transcription

Set `OPENAI_API_KEY` in your local `.env` or deployment secret store, then rebuild/restart the backend. The upload form can then use OpenAI `gpt-4o-transcribe-diarize` to generate a transcript with normalized `Person1`, `Person2`, … labels. The API key is read only by the backend; it is never sent to the browser or stored in the database.

## Administration

Administrator status is explicit (`role=admin`) and is not granted to registrations. Bootstrap the first administrator from the trusted deployment shell:

```bash
docker compose exec backend python -m app.scripts.bootstrap_admin --username <admin-name>
```

Admin-only endpoints list users, enable or disable another user, and expose dataset resource counts. Administrators do not automatically gain access to another user's private audio.

## Persistent data

- `data/spokendialoguesum/` is mounted into `/dataset/spokendialoguesum` in the backend container read-only.
- `storage/uploads/` is mounted into `/uploads` in the backend container read-write for user uploads.
- PostgreSQL and Redis persist through Compose named volumes.

## Dataset import

The importer reads only overlap-dialogue metadata and never copies the mounted WAV files. See [DATASET_IMPORT_RULES.md](DATASET_IMPORT_RULES.md) for the resource and metadata mapping.

```bash
docker compose exec backend python -m app.scripts.import_dataset
docker compose exec backend python -m app.scripts.list_resources --page 1 --page-size 10
```

## Documentation

- `API接口规范文档.md`
- `项目后端设计说明文档.md`
- `DATASET_IMPORT_RULES.md`
