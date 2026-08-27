"""
gatekeeper/cloud_storage.py

Cloud Storage integration for storing uploaded screenplay files.

Uploads go to Cloud Storage; Firestore only stores a pointer (URL) to the file.
This is the correct architecture because:
- Firestore is a database, not meant for file storage (size limits, cost)
- Cloud Storage is Google's file storage service, built for this purpose
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from google.cloud import storage

load_dotenv()

# Cloud Storage configuration
GCS_BUCKET_NAME = os.getenv("GCS_BUCKET_NAME")
if not GCS_BUCKET_NAME:
    raise ValueError(
        "GCS_BUCKET_NAME environment variable is required. "
        "Set it in .env file (e.g., GCS_BUCKET_NAME=script-clearance-scripts)"
    )


def _get_storage_client() -> storage.Client:
    """Get a Cloud Storage client using application default credentials."""
    # GOOGLE_APPLICATION_CREDENTIALS is read automatically by the client library
    # if set. If not set, the client will use default credentials from the
    # environment (gcloud auth application-default login).
    return storage.Client()


def _get_bucket(client: storage.Client) -> storage.Bucket:
    """Get the Cloud Storage bucket for this project."""
    return client.bucket(GCS_BUCKET_NAME)


def _generate_blob_name(original_filename: str, run_id: str) -> str:
    """
    Generate a Cloud Storage blob name for an uploaded file.

    Format: runs/{run_id}/{timestamp}-{original_filename}
    Example: runs/run_123/1724832000-screenplay.pdf

    This ensures:
    - Files are organized by run_id
    - Unique filenames even if same file is uploaded twice
    - Easy cleanup by run_id prefix
    """
    timestamp = int(datetime.now(timezone.utc).timestamp())
    path = Path(original_filename)
    name = path.stem
    suffix = path.suffix.lower() or ".bin"

    # Sanitize name - remove potentially dangerous characters
    safe_name = "".join(c if c.isalnum() or c in "-_." else "_" for c in name)
    safe_name = safe_name[:100]  # Length limit

    return f"runs/{run_id}/{timestamp}-{safe_name}{suffix}"


def upload_screenplay(
    file_bytes: bytes,
    original_filename: str,
    run_id: str,
) -> str:
    """
    Upload a screenplay file to Cloud Storage.

    Args:
        file_bytes: The file content as bytes
        original_filename: Original filename from upload
        run_id: The clearance run ID to organize under

    Returns:
        gs:// URL for the uploaded file (e.g., gs://bucket/runs/run_id/filename.pdf)

    Raises:
        ValueError: If GCS_BUCKET_NAME is not set
        google.api_core.exceptions.GoogleAPICallError: If upload fails
    """
    if not file_bytes:
        raise ValueError("Cannot upload empty file")

    client = _get_storage_client()
    bucket = _get_bucket(client)
    blob_name = _generate_blob_name(original_filename, run_id)

    blob = bucket.blob(blob_name)
    blob.upload_from_string(file_bytes, content_type="application/octet-stream")

    # Generate a public URL for the file
    # Files will be accessible via gs:// URL (internal) or
    # https://storage.googleapis.com/bucket-name/path (HTTP)
    return f"gs://{GCS_BUCKET_NAME}/{blob_name}"


def get_file_url(run_id: str, blob_name: Optional[str] = None) -> str:
    """
    Generate a Cloud Storage URL for a file.

    Args:
        run_id: The clearance run ID
        blob_name: Optional specific blob name; if None, returns runs/{run_id}/ prefix

    Returns:
        gs:// URL for the file or directory
    """
    if blob_name:
        return f"gs://{GCS_BUCKET_NAME}/{blob_name}"
    return f"gs://{GCS_BUCKET_NAME}/runs/{run_id}/"


def download_file(blob_name: str) -> bytes:
    """
    Download a file from Cloud Storage.

    Args:
        blob_name: Full blob path (e.g., runs/run_id/filename.pdf)

    Returns:
        File content as bytes

    Raises:
        google.cloud.exceptions.NotFound: If file doesn't exist
    """
    client = _get_storage_client()
    bucket = _get_bucket(client)
    blob = bucket.blob(blob_name)
    return blob.download_as_bytes()


def file_exists(blob_name: str) -> bool:
    """Check if a file exists in Cloud Storage."""
    client = _get_storage_client()
    bucket = _get_bucket(client)
    blob = bucket.blob(blob_name)
    return blob.exists()


def delete_file(blob_name: str) -> None:
    """Delete a file from Cloud Storage."""
    client = _get_storage_client()
    bucket = _get_bucket(client)
    blob = bucket.blob(blob_name)
    blob.delete()


def delete_run_files(run_id: str) -> int:
    """
    Delete all files associated with a clearance run.

    Args:
        run_id: The clearance run ID

    Returns:
        Number of files deleted
    """
    client = _get_storage_client()
    bucket = _get_bucket(client)

    # List all blobs with the run_id prefix
    prefix = f"runs/{run_id}/"
    blobs = list(client.list_blobs(bucket, prefix=prefix))

    deleted_count = 0
    for blob in blobs:
        try:
            blob.delete()
            deleted_count += 1
        except Exception as e:
            print(f"Failed to delete {blob.name}: {e}")

    return deleted_count
