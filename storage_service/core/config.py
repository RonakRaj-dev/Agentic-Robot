from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from ``.env``.

    Only settings that are actually read by the codebase are declared
    here.  Legacy unused settings (``media_storage_path``, ``max_pages``,
    ``pdf_base_dir``, ``minio_max_retries``, ``mongo_max_retries``,
    ``extraction_max_retries``, ``collection_*`` names) were removed —
    the codebase reads collection names from each model's
    ``Settings.collection`` attribute, not from central settings.

    .. versionchanged:: v7
        Removed ``presigned_get_url_expiry`` and
        ``presigned_put_url_expiry`` — presigned URLs have been
        removed entirely.  Buckets are publicly downloadable and the
        storage service exposes :meth:`IStorageService.get_public_url`
        for direct object URLs.
        Removed the ``minio_url`` property — public URLs are now built
        from ``public_storage_url``.
        Added ``public_storage_url``.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # MongoDB
    mongo_uri: str = Field(default="")
    mongo_db_name: str = "SiliconRag"

    # MinIO
    minio_endpoint: str = Field(default="")
    minio_access_key: str = Field(default="")
    minio_secret_key: str = Field(default="")
    minio_bucket: str = "ncert-rag"
    minio_bucket_pdf: str = "pdfs"
    minio_bucket_images: str = "page-images"
    minio_secure: bool = False

    # Public object URL base.
    # The MinIO buckets ``pdfs`` and ``page-images`` (and the default
    # ``ncert-rag`` bucket) are configured as publicly downloadable.
    # All object access URLs are constructed dynamically by joining
    # ``public_storage_url`` + ``bucket`` + ``object_key`` — see
    # :meth:`IStorageService.get_public_url`.  This must be the URL the
    # *end user* can reach (e.g. the public-facing MinIO endpoint, a CDN,
    # or a reverse proxy in front of MinIO).
    public_storage_url: str = Field(
        default="http://localhost:9000",
        description=(
            "Public base URL for object storage. All object URLs are "
            "constructed as ``{public_storage_url}/{bucket}/{object_key}``. "
            "Examples: ``http://localhost:9000``, "
            "``https://storage.example.com``."
        ),
    )

    # Processing
    max_pdf_size_mb: int = 500
    log_level: str = "INFO"

    @property
    def max_pdf_size_bytes(self) -> int:
        return self.max_pdf_size_mb * 1024 * 1024


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Returns a cached Settings singleton."""
    return Settings()
