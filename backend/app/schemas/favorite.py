from pydantic import BaseModel, Field


class FavoriteRequest(BaseModel):
    audio_id: int = Field(alias="audioId", gt=0)
