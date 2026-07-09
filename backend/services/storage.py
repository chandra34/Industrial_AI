"""Pluggable file-storage providers for uploaded documents.

The active provider is selected at startup via the ``STORAGE_PROVIDER``
environment variable (``local`` | ``s3`` | ``gcs``).  Cloud SDKs are
imported **lazily** so that local development never requires ``boto3``
or ``google-cloud-storage`` to be installed.
"""

import abc
import logging
from pathlib import Path

from backend.config.settings import Settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Abstract interface
# ---------------------------------------------------------------------------

class BaseStorageProvider(abc.ABC):
    """Abstract interface for document file storage operations."""

    @abc.abstractmethod
    async def upload_file(self, file_bytes: bytes, destination_key: str) -> str:
        """Upload raw file bytes and return a unique stored path/key."""

    @abc.abstractmethod
    async def download_file(self, file_key: str) -> bytes:
        """Retrieve raw file bytes from the store."""

    @abc.abstractmethod
    async def delete_file(self, file_key: str) -> bool:
        """Delete file from the store. Return True if deleted."""

    @abc.abstractmethod
    async def get_download_url(
        self, file_key: str, filename: str, expires_in: int = 3600
    ) -> str | None:
        """Generate a secure, temporary presigned URL for direct download.

        Returns ``None`` when presigned URLs are not supported (e.g. local).
        """


# ---------------------------------------------------------------------------
# Local filesystem (default – backward-compatible with existing behaviour)
# ---------------------------------------------------------------------------

class LocalStorageProvider(BaseStorageProvider):
    """Store files on the local filesystem under ``settings.resolved_upload_dir``."""

    def __init__(self, settings: Settings) -> None:
        self.upload_dir = settings.resolved_upload_dir
        self.upload_dir.mkdir(parents=True, exist_ok=True)

    async def upload_file(self, file_bytes: bytes, destination_key: str) -> str:
        from fastapi.concurrency import run_in_threadpool

        target_path = self.upload_dir / destination_key
        await run_in_threadpool(target_path.write_bytes, file_bytes)
        return str(target_path)

    async def download_file(self, file_key: str) -> bytes:
        from fastapi.concurrency import run_in_threadpool

        target_path = self.upload_dir / file_key
        exists = await run_in_threadpool(target_path.exists)
        if not exists:
            raise FileNotFoundError(f"File not found on local disk: {file_key}")
        return await run_in_threadpool(target_path.read_bytes)

    async def delete_file(self, file_key: str) -> bool:
        from fastapi.concurrency import run_in_threadpool

        target_path = self.upload_dir / file_key
        
        def _delete() -> bool:
            if target_path.exists():
                try:
                    target_path.unlink()
                    return True
                except Exception as exc:
                    logger.error("Failed to delete local file %s: %s", target_path, exc)
                    return False
            return False

        return await run_in_threadpool(_delete)

    async def get_download_url(
        self, file_key: str, filename: str, expires_in: int = 3600
    ) -> str | None:
        # Local files are streamed directly; no presigned URL needed.
        return None


# ---------------------------------------------------------------------------
# Amazon S3
# ---------------------------------------------------------------------------

class S3StorageProvider(BaseStorageProvider):
    """Store files in an Amazon S3 bucket.

    Requires ``pip install boto3``.  The SDK is imported lazily so that
    the application can start under ``STORAGE_PROVIDER=local`` without
    ``boto3`` being installed.
    """

    def __init__(self, settings: Settings) -> None:
        try:
            import boto3
            from botocore.config import Config
        except ImportError as exc:
            raise ImportError(
                "AWS S3 storage provider requires 'boto3'. "
                "Install it with:  pip install boto3"
            ) from exc

        session_opts: dict = {}
        if settings.aws_access_key_id and settings.aws_secret_access_key:
            session_opts["aws_access_key_id"] = settings.aws_access_key_id
            session_opts["aws_secret_access_key"] = settings.aws_secret_access_key

        self.s3_client = boto3.client(
            "s3",
            region_name=settings.aws_region,
            config=Config(
                signature_version="s3v4",
                s3={"addressing_style": "virtual"},
            ),
            **session_opts,
        )
        self.bucket = settings.s3_bucket_name
        if not self.bucket:
            raise ValueError(
                "S3_BUCKET_NAME must be set when STORAGE_PROVIDER=s3"
            )

    async def upload_file(self, file_bytes: bytes, destination_key: str) -> str:
        from fastapi.concurrency import run_in_threadpool

        await run_in_threadpool(
            self.s3_client.put_object,
            Bucket=self.bucket,
            Key=destination_key,
            Body=file_bytes,
            ContentType="application/pdf",
        )
        return f"s3://{self.bucket}/{destination_key}"

    async def download_file(self, file_key: str) -> bytes:
        from fastapi.concurrency import run_in_threadpool

        def _download() -> bytes:
            response = self.s3_client.get_object(
                Bucket=self.bucket,
                Key=file_key,
            )
            return response["Body"].read()

        return await run_in_threadpool(_download)

    async def delete_file(self, file_key: str) -> bool:
        from fastapi.concurrency import run_in_threadpool

        try:
            await run_in_threadpool(
                self.s3_client.delete_object,
                Bucket=self.bucket,
                Key=file_key,
            )
            return True
        except Exception as exc:
            logger.error("Failed to delete %s from S3: %s", file_key, exc)
            return False

    async def get_download_url(
        self, file_key: str, filename: str, expires_in: int = 3600
    ) -> str | None:
        from fastapi.concurrency import run_in_threadpool

        try:
            return await run_in_threadpool(
                self.s3_client.generate_presigned_url,
                ClientMethod="get_object",
                Params={
                    "Bucket": self.bucket,
                    "Key": file_key,
                    "ResponseContentDisposition": f'attachment; filename="{filename}"',
                },
                ExpiresIn=expires_in,
            )
        except Exception as exc:
            logger.warning("Failed to generate presigned download URL for %s from S3: %s", file_key, exc)
            return None


# ---------------------------------------------------------------------------
# Google Cloud Storage / Firebase Storage
# ---------------------------------------------------------------------------

class GCSStorageProvider(BaseStorageProvider):
    """Store files in a Google Cloud Storage bucket via ``firebase-admin``.

    Requires ``pip install firebase-admin google-cloud-storage``.
    Both packages are imported lazily.
    """

    def __init__(self, settings: Settings) -> None:
        try:
            import firebase_admin
            from firebase_admin import credentials
            from firebase_admin import storage as _storage  # noqa: F841
        except ImportError as exc:
            raise ImportError(
                "GCS/Firebase storage provider requires 'firebase-admin' and "
                "'google-cloud-storage'.  Install them with:  "
                "pip install firebase-admin google-cloud-storage"
            ) from exc

        # Re-use the existing Firebase app or initialize a new one with configured credentials
        try:
            self.app = firebase_admin.get_app()
        except ValueError:
            import json
            try:
                if settings.firebase_credentials_json:
                    cred_dict = json.loads(settings.firebase_credentials_json)
                    cred = credentials.Certificate(cred_dict)
                    self.app = firebase_admin.initialize_app(cred)
                    logger.info("Firebase Admin SDK initialized in GCS provider using JSON string")
                elif settings.firebase_credentials_path:
                    cred = credentials.Certificate(settings.firebase_credentials_path)
                    self.app = firebase_admin.initialize_app(cred)
                    logger.info("Firebase Admin SDK initialized in GCS provider using certificate file")
                else:
                    self.app = firebase_admin.initialize_app()
                    logger.info("Firebase Admin SDK initialized in GCS provider using default credentials")
            except Exception as init_exc:
                logger.warning("GCS provider failed to initialize Firebase Admin SDK: %s. Continuing...", init_exc)
                # Fallback to default setup attempt if something fails
                try:
                    self.app = firebase_admin.initialize_app()
                except Exception:
                    self.app = None

        self.bucket_name = settings.gcs_bucket_name
        if not self.bucket_name:
            self.bucket_name = f"{settings.project_root.name}.appspot.com"

    @property
    def bucket(self):
        """Return a handle to the GCS bucket (no RPC call)."""
        from firebase_admin import storage

        return storage.bucket(name=self.bucket_name, app=self.app)

    async def upload_file(self, file_bytes: bytes, destination_key: str) -> str:
        from fastapi.concurrency import run_in_threadpool

        def _upload() -> str:
            blob = self.bucket.blob(destination_key)
            blob.upload_from_string(file_bytes, content_type="application/pdf")
            return f"gs://{self.bucket_name}/{destination_key}"

        return await run_in_threadpool(_upload)

    async def download_file(self, file_key: str) -> bytes:
        from fastapi.concurrency import run_in_threadpool

        def _download() -> bytes:
            blob = self.bucket.blob(file_key)
            return blob.download_as_bytes()

        return await run_in_threadpool(_download)

    async def delete_file(self, file_key: str) -> bool:
        from fastapi.concurrency import run_in_threadpool

        def _delete() -> bool:
            blob = self.bucket.blob(file_key)
            if blob.exists():
                blob.delete()
                return True
            return False

        try:
            return await run_in_threadpool(_delete)
        except Exception as exc:
            logger.error("Failed to delete %s from GCS: %s", file_key, exc)
            return False

    async def get_download_url(
        self, file_key: str, filename: str, expires_in: int = 3600
    ) -> str | None:
        from datetime import timedelta

        from fastapi.concurrency import run_in_threadpool

        def _presign() -> str:
            blob = self.bucket.blob(file_key)
            return blob.generate_signed_url(
                expiration=timedelta(seconds=expires_in),
                method="GET",
                response_disposition=f'attachment; filename="{filename}"',
            )

        try:
            return await run_in_threadpool(_presign)
        except Exception as exc:
            logger.warning("Failed to generate GCS presigned download URL for %s: %s", file_key, exc)
            return None


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def create_storage_provider(settings: Settings) -> BaseStorageProvider:
    """Instantiate the storage provider selected by ``STORAGE_PROVIDER``."""
    provider = settings.storage_provider.lower().strip()
    if provider == "s3":
        return S3StorageProvider(settings)
    if provider in ("gcs", "firebase"):
        return GCSStorageProvider(settings)
    return LocalStorageProvider(settings)
