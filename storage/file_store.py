"""
storage/file_store.py

Cloud Storage integration for storing uploaded screenplays and generated PDF reports.

The Firestore run record holds pointers (gs:// URLs) to these files.
This is the correct architecture because:
- Firestore is a database, not meant for file storage (size limits, cost)
- Cloud Storage is Google's file storage service, built for this purpose
"""

from __future__ import annotations

import hashlib
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
    return storage.Client()


def _get_bucket(client: storage.Client) -> storage.Bucket:
    """Get the Cloud Storage bucket for this project."""
    return client.bucket(GCS_BUCKET_NAME)


def _generate_blob_name(run_id: str, filename: str) -> str:
    """
    Generate a Cloud Storage blob name for a file.

    Format: runs/{run_id}/{filename}
    Example: runs/run_123/screenplay.pdf
    """
    # Sanitize filename - remove potentially dangerous characters
    path = Path(filename)
    name = path.stem
    suffix = path.suffix.lower() or ".bin"

    # Sanitize name - remove potentially dangerous characters
    safe_name = "".join(c if c.isalnum() or c in "-_." else "_" for c in name)
    safe_name = safe_name[:100]  # Length limit

    return f"runs/{run_id}/{safe_name}{suffix}"


def upload_screenplay(run_id: str, file_bytes: bytes, filename: str) -> str:
    """
    Upload a screenplay file to Cloud Storage.

    Args:
        run_id: The clearance run ID to organize under
        file_bytes: The file content as bytes
        filename: Original filename from upload

    Returns:
        gs:// URL for the uploaded file (e.g., gs://bucket/runs/run_id/filename.pdf)

    Raises:
        ValueError: If file_bytes is empty
    """
    if not file_bytes:
        raise ValueError("Cannot upload empty file")

    client = _get_storage_client()
    bucket = _get_bucket(client)
    blob_name = _generate_blob_name(run_id, filename)

    blob = bucket.blob(blob_name)
    blob.upload_from_string(file_bytes, content_type="application/octet-stream")

    return f"gs://{GCS_BUCKET_NAME}/{blob_name}"


def get_screenplay_url(run_id: str) -> str:
    """
    Generate a Cloud Storage URL for a screenplay.

    Args:
        run_id: The clearance run ID

    Returns:
        gs:// URL for the screenplay file
    """
    return f"gs://{GCS_BUCKET_NAME}/runs/{run_id}/"


def upload_report(run_id: str, pdf_bytes: bytes) -> tuple[str, str]:
    """
    Upload a PDF report to Cloud Storage and compute its SHA-256 hash.

    Args:
        run_id: The clearance run ID
        pdf_bytes: The PDF content as bytes

    Returns:
        Tuple of (gs:// URL, SHA-256 hash hex string)
    """
    if not pdf_bytes:
        raise ValueError("Cannot upload empty PDF")

    client = _get_storage_client()
    bucket = _get_bucket(client)
    blob_name = f"runs/{run_id}/clearance_report.pdf"

    # Compute SHA-256 hash for tamper-evidence
    report_hash = hashlib.sha256(pdf_bytes).hexdigest()

    blob = bucket.blob(blob_name)
    blob.upload_from_string(pdf_bytes, content_type="application/pdf")

    return f"gs://{GCS_BUCKET_NAME}/{blob_name}", report_hash


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
