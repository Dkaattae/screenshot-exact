from pydantic_settings import BaseSettings, SettingsConfigDict

DEV_SECRET = "dev-only-change-me"


class Settings(BaseSettings):
    """Read from environment variables prefixed with TRYON_, or from backend/.env."""

    model_config = SettingsConfigDict(env_prefix="TRYON_", env_file=".env", extra="ignore")

    environment: str = "development"
    database_url: str = "sqlite:///./data/app.db"
    storage_dir: str = "./data/files"
    # Signs access tokens and file URLs. Must be set outside development.
    secret_key: str = DEV_SECRET
    access_token_minutes: int = 60 * 24 * 7
    file_url_ttl_seconds: int = 60 * 60
    # Used to build absolute image URLs.
    public_base_url: str = "http://localhost:8000"
    # JSON list, e.g. TRYON_CORS_ORIGINS='["https://app.example.com"]'
    cors_origins: list[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://localhost:8080",
    ]
    max_upload_bytes: int = 15 * 1024 * 1024

    def check(self) -> None:
        if self.environment != "development" and self.secret_key == DEV_SECRET:
            raise RuntimeError("Set TRYON_SECRET_KEY outside development.")
