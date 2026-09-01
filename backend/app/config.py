from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "AttendXsuite"
    environment: str = "development"
    port: int = 8060
    mongodb_uri: str = "mongodb://127.0.0.1:27017/attendxsuite"
    jwt_secret: str = "attendxsuite_local_secret"
    jwt_expire_minutes: int = 43200
    client_origins: str = "http://127.0.0.1:8061,http://localhost:8061"
    company_timezone: str = "Asia/Kolkata"

    face_engine: str = "opencv"
    hf_face_api_url: str = ""
    hf_face_api_token: str = "replace_with_secret_token"
    hf_face_model: str = "buffalo_s"
    hf_timeout_seconds: int = 20
    face_match_threshold: float = 0.48
    face_match_margin: float = 0.06
    face_scan_frame_count: int = 5
    face_scan_consensus: int = 3

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    @property
    def origins(self) -> list[str]:
        return [origin.strip() for origin in self.client_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
