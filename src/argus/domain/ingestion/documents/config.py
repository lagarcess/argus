from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class DocumentExtractionSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="ARGUS_DOCUMENT_EXTRACTION_", extra="ignore"
    )
    enabled: bool = False
    max_bytes: int = Field(default=10 * 1024 * 1024, ge=1, le=10 * 1024 * 1024)
    max_pages: int = Field(default=8, ge=1, le=8)
