import pytest
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock
from backend.config.settings import get_settings
from backend.services.storage import LocalStorageProvider, S3StorageProvider, GCSStorageProvider


@pytest.fixture
def temp_upload_dir(tmp_path):
    """Fixture providing a temporary uploads directory."""
    return tmp_path / "uploads"


@pytest.fixture
def local_storage(temp_upload_dir):
    """Fixture providing a LocalStorageProvider pointing to temporary dir."""
    settings = get_settings()
    # Force settings resolved_upload_dir to use temp_upload_dir
    with patch.object(settings, "upload_dir", temp_upload_dir):
        # Setting resolves to absolute temp path
        provider = LocalStorageProvider(settings)
        yield provider


@pytest.mark.asyncio
async def test_local_storage_lifecycle(local_storage):
    """Verify upload, download, and delete lifecycle of local storage."""
    file_bytes = b"Hello, local storage provider test!"
    destination_key = "test_doc_1.pdf"

    # 1. Upload
    path = await local_storage.upload_file(file_bytes, destination_key)
    assert Path(path).exists()
    assert Path(path).name == destination_key

    # 2. Download
    downloaded = await local_storage.download_file(destination_key)
    assert downloaded == file_bytes

    # 3. Delete
    deleted = await local_storage.delete_file(destination_key)
    assert deleted is True
    assert not Path(path).exists()

    # 4. Delete non-existent file
    deleted_again = await local_storage.delete_file(destination_key)
    assert deleted_again is False


@pytest.mark.asyncio
async def test_local_storage_download_missing(local_storage):
    """Verify that downloading a missing file raises FileNotFoundError."""
    with pytest.raises(FileNotFoundError):
        await local_storage.download_file("non_existent_key.pdf")


@pytest.mark.asyncio
async def test_local_storage_delete_exception_safety(local_storage):
    """Verify that if unlink raises an exception, delete_file returns False."""
    destination_key = "test_fail_delete.pdf"
    await local_storage.upload_file(b"test", destination_key)

    with patch("pathlib.Path.unlink", side_effect=PermissionError("Permission denied")):
        deleted = await local_storage.delete_file(destination_key)
        assert deleted is False


@pytest.mark.asyncio
async def test_s3_storage_url_exception_handling():
    """Verify that S3StorageProvider.get_download_url handles exceptions and returns None."""
    # Ensure boto3 module is mocked in sys.modules so that lazy imports don't fail
    mock_boto = MagicMock()
    mock_client = MagicMock()
    mock_client.generate_presigned_url.side_effect = Exception("S3 configuration error")
    mock_boto.client.return_value = mock_client
    
    mock_botocore = MagicMock()

    with patch.dict(sys.modules, {"boto3": mock_boto, "botocore": mock_botocore, "botocore.config": mock_botocore}):
        settings = get_settings()
        with patch.object(settings, "s3_bucket_name", "test-bucket"):
            provider = S3StorageProvider(settings)
            url = await provider.get_download_url("test_key", "test_file.pdf")
            assert url is None


@pytest.mark.asyncio
async def test_gcs_storage_url_exception_handling():
    """Verify that GCSStorageProvider.get_download_url handles exceptions and returns None."""
    settings = get_settings()
    with patch.object(settings, "gcs_bucket_name", "test-gcs-bucket"):
        with patch("firebase_admin.initialize_app"), patch("firebase_admin.get_app"):
            provider = GCSStorageProvider(settings)
            
            # Mock the bucket/blob to raise an exception during generation
            mock_blob = MagicMock()
            mock_blob.generate_signed_url.side_effect = Exception("GCS Signing error")
            
            mock_bucket = MagicMock()
            mock_bucket.blob.return_value = mock_blob
            
            # Use PropertyMock to patch the bucket property directly on the instance to avoid type check errors
            with patch.object(GCSStorageProvider, "bucket", new_callable=PropertyMock) as mock_bucket_prop:
                mock_bucket_prop.return_value = mock_bucket
                
                url = await provider.get_download_url("test_key", "test_file.pdf")
                assert url is None


@pytest.mark.asyncio
async def test_s3_storage_lifecycle():
    """Verify S3StorageProvider upload, download, and delete lifecycle."""
    mock_boto = MagicMock()
    mock_client = MagicMock()
    mock_boto.client.return_value = mock_client
    mock_botocore = MagicMock()

    # Mock get_object response Body
    mock_body = MagicMock()
    mock_body.read.return_value = b"S3 file bytes content"
    mock_client.get_object.return_value = {"Body": mock_body}
    mock_client.generate_presigned_url.return_value = "https://s3-presigned-url.com"

    with patch.dict(sys.modules, {"boto3": mock_boto, "botocore": mock_botocore, "botocore.config": mock_botocore}):
        settings = get_settings()
        with patch.object(settings, "s3_bucket_name", "test-bucket"):
            provider = S3StorageProvider(settings)
            
            # 1. Upload
            path = await provider.upload_file(b"S3 file bytes content", "s3_key.pdf")
            assert path == "s3://test-bucket/s3_key.pdf"
            mock_client.put_object.assert_called_once_with(
                Bucket="test-bucket",
                Key="s3_key.pdf",
                Body=b"S3 file bytes content",
                ContentType="application/pdf",
            )
            
            # 2. Download
            downloaded = await provider.download_file("s3_key.pdf")
            assert downloaded == b"S3 file bytes content"
            mock_client.get_object.assert_called_once_with(
                Bucket="test-bucket",
                Key="s3_key.pdf",
            )
            
            # 3. Presigned URL
            url = await provider.get_download_url("s3_key.pdf", "filename.pdf")
            assert url == "https://s3-presigned-url.com"
            mock_client.generate_presigned_url.assert_called_once_with(
                ClientMethod="get_object",
                Params={
                    "Bucket": "test-bucket",
                    "Key": "s3_key.pdf",
                    "ResponseContentDisposition": 'attachment; filename="filename.pdf"',
                },
                ExpiresIn=3600,
            )

            # 4. Delete
            deleted = await provider.delete_file("s3_key.pdf")
            assert deleted is True
            mock_client.delete_object.assert_called_once_with(
                Bucket="test-bucket",
                Key="s3_key.pdf",
            )


@pytest.mark.asyncio
async def test_gcs_storage_lifecycle():
    """Verify GCSStorageProvider upload, download, and delete lifecycle."""
    settings = get_settings()
    with patch.object(settings, "gcs_bucket_name", "test-gcs-bucket"):
        with patch("firebase_admin.initialize_app"), patch("firebase_admin.get_app"):
            provider = GCSStorageProvider(settings)
            
            # Mock the bucket and blob
            mock_blob = MagicMock()
            mock_blob.download_as_bytes.return_value = b"GCS file bytes content"
            mock_blob.exists.return_value = True
            mock_blob.generate_signed_url.return_value = "https://gcs-signed-url.com"
            
            mock_bucket = MagicMock()
            mock_bucket.blob.return_value = mock_blob
            
            with patch.object(GCSStorageProvider, "bucket", new_callable=PropertyMock) as mock_bucket_prop:
                mock_bucket_prop.return_value = mock_bucket
                
                # 1. Upload
                path = await provider.upload_file(b"GCS file bytes content", "gcs_key.pdf")
                assert path == "gs://test-gcs-bucket/gcs_key.pdf"
                mock_bucket.blob.assert_called_with("gcs_key.pdf")
                mock_blob.upload_from_string.assert_called_once_with(
                    b"GCS file bytes content",
                    content_type="application/pdf",
                )
                
                # 2. Download
                downloaded = await provider.download_file("gcs_key.pdf")
                assert downloaded == b"GCS file bytes content"
                mock_blob.download_as_bytes.assert_called_once()
                
                # 3. Presigned URL
                url = await provider.get_download_url("gcs_key.pdf", "filename.pdf")
                assert url == "https://gcs-signed-url.com"
                
                # 4. Delete
                deleted = await provider.delete_file("gcs_key.pdf")
                assert deleted is True
                mock_blob.exists.assert_called_once()
                mock_blob.delete.assert_called_once()


@pytest.mark.asyncio
async def test_local_storage_path_traversal_prevention(local_storage):
    """Verify that path traversal sequences raise ValueError across upload, download, and delete."""
    malicious_keys = [
        "../test.pdf",
        "../../etc/passwd",
        "subdir/../../secret.txt",
    ]

    for key in malicious_keys:
        with pytest.raises(ValueError, match="Path traversal attempt detected"):
            await local_storage.upload_file(b"content", key)

        with pytest.raises(ValueError, match="Path traversal attempt detected"):
            await local_storage.download_file(key)

        with pytest.raises(ValueError, match="Path traversal attempt detected"):
            await local_storage.delete_file(key)

