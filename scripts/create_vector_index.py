#!/usr/bin/env python3
"""
scripts/create_vector_index.py

Create Firestore vector index for entity_research_vectors collection.
Uses the Firestore Admin API to create a composite index with vector field.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

from api.settings import firestore_database, firestore_project


def create_vector_index():
    """Create composite vector index using Firestore Admin API."""
    from google.cloud import firestore_admin_v1
    from google.cloud.firestore_admin_v1.types import Index
    
    client = firestore_admin_v1.FirestoreAdminClient()
    
    project = firestore_project()
    database = firestore_database()
    
    parent = f"projects/{project}/databases/{database}/collectionGroups/entity_research_vectors"
    
    # Define the index with simpler structure
    index = Index(
        query_scope=Index.QueryScope.COLLECTION,
        fields=[
            Index.IndexField(
                field_path="entity_type",
                order=Index.IndexField.Order.ASCENDING,
            ),
            Index.IndexField(
                field_path="embedding",
                vector_config={
                    "dimension": 1536,
                    "flat": {}
                },
            ),
        ],
    )
    
    print(f"Creating vector index on {parent}")
    print(f"  - entity_type: ASCENDING")
    print(f"  - embedding: VECTOR (1536 dimensions)")
    print()
    
    try:
        operation = client.create_index(
            request={
                "parent": parent,
                "index": index,
            }
        )
        
        print("✓ Index creation started. This may take several minutes...")
        print(f"Operation name: {operation.operation.name}")
        print()
        print("To check status:")
        print(f"  gcloud firestore operations describe {operation.operation.name}")
        print()
        print("Or list all indexes:")
        print(f"  gcloud firestore indexes composite list --database={database}")
        
        return 0
        
    except Exception as e:
        error_msg = str(e).lower()
        if "already exists" in error_msg or "duplicate" in error_msg:
            print("✓ Index already exists!")
            print()
            print("To list existing indexes:")
            print(f"  gcloud firestore indexes composite list --database={database}")
            return 0
        else:
            print(f"ERROR: Failed to create index: {e}")
            import traceback
            traceback.print_exc()
            return 1


def main():
    try:
        return create_vector_index()
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
