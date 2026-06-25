from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings loaded from environment variables or an optional .env file."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "development"
    database_url: str
    redis_url: str
    dataset_root: str
    upload_root: str
    max_upload_size_mb: int = 100
    allowed_audio_types: str = "audio/wav,audio/mpeg,audio/mp4,audio/ogg"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    access_token_expire_minutes: int = 10080
    openai_api_key: str | None = None
    openai_asr_model: str = "gpt-4o-transcribe-diarize"
    openai_asr_max_file_size_mb: int = 25
    speechllm_api_base_url: str | None = None
    speechllm_api_path: str = ""
    speechllm_api_token: str | None = None
    speechllm_model_id: str = "RuiRuihigh/qwen2audioinstruct-sft-merged"
    speechllm_request_mode: str = "json_base64"
    speechllm_request_timeout_seconds: int = 600
    speechllm_max_file_size_mb: int = 100
    speechllm_max_new_tokens: int = 256


@lru_cache
def get_settings() -> Settings:
    return Settings()
