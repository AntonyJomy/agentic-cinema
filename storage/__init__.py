"""
storage/

Cloud Storage and Firestore persistence for the Agentic Cinema clearance system.
"""

from storage.file_store import upload_screenplay, get_screenplay_url, upload_report, download_file, file_exists, delete_file, delete_run_files
from storage.firestore_run_store import (
    create_run,
    save_pipeline_results,
    record_decision,
    attach_report,
    get_run,
    recompute_summary,
)

__all__ = [
    "upload_screenplay",
    "get_screenplay_url",
    "upload_report",
    "download_file",
    "file_exists",
    "delete_file",
    "delete_run_files",
    "create_run",
    "save_pipeline_results",
    "record_decision",
    "attach_report",
    "get_run",
    "recompute_summary",
]
