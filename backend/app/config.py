from pydantic_settings import BaseSettings, SettingsConfigDict

DEV_SECRET = "dev-only-insecure-secret-change-me-before-deploying"


class Settings(BaseSettings):
    """Read from environment variables prefixed with TRYON_, or from backend/.env."""

    model_config = SettingsConfigDict(env_prefix="TRYON_", env_file=".env", extra="ignore")

    environment: str = "development"
    database_url: str = "sqlite:///./data/app.db"
    # Local disk: always available, and the fallback whenever S3 is not reachable.
    storage_dir: str = "./data/files"
    # Folders for the two file areas, in the bucket and under storage_dir alike.
    input_prefix: str = "inputs"
    output_prefix: str = "outputs"
    # Set to store files in an S3-compatible bucket (e.g. Nebius Object Storage) first, with
    # presigned URLs that generation models outside this machine can fetch.
    s3_bucket: str | None = None
    # Leave unset for AWS S3. Nebius Object Storage: https://storage.eu-north1.nebius.cloud
    s3_endpoint_url: str | None = None
    s3_region: str | None = None
    # Leave unset to use the standard AWS credential chain (env vars, profile, instance role).
    s3_access_key_id: str | None = None
    s3_secret_access_key: str | None = None
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
    # Built frontend (frontend/dist/client). When set, create_site serves it at / and the API
    # at /api.
    frontend_dir: str | None = None

    def check(self) -> None:
        if not self.secret_key:
            raise RuntimeError("TRYON_SECRET_KEY is set but empty. Unset it or give it a value.")
        if self.environment != "development" and self.secret_key == DEV_SECRET:
            raise RuntimeError("Set TRYON_SECRET_KEY outside development.")
