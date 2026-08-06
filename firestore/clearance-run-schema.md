# Clearance Run — Firestore Schema (v2)

**Database:** `script-clearance-db` (project: `script-clearance-hackathon`)
**Collection:** `clearance_runs`

⚠️ Anyone connecting to Firestore must pass the database name explicitly:
```python
firestore.Client(project="script-clearance-hackathon", database="script-clearance-db")
```

## Why v2

This schema was updated to align with the finalized Pydantic entities schema (`schemas/entities.py`). The original draft used a `findings` array with a flat `risk_level`; the real agent output uses an `entities` array with a more detailed structure. This version extends the Pydantic output with two additional fields (`status` and `evidence` per entity) needed for the clearance/IAM workflow — see notes below.

## Document shape

```json
{
  "run_id": "string (uuid, matches Pydantic run_id)",
  "script_id": "string",
  "script_title": "string",
  "created_at": "timestamp",
  "updated_at": "timestamp",
  "overall_status": "pending | flagged | approved | rejected",
  "reviewed_by": "string (Firebase Auth uid) | null",
  "reviewed_at": "timestamp | null",
  "entities": [
    {
      "entity_id": "string (uuid)",
      "name": "string",
      "entity_type": "string — e.g. business | song | character",
      "risk_category": "string — e.g. business_location | music_rights",
      "context": "string",
      "location": {
        "page_number": "number",
        "scene_number": "number | null",
        "line_excerpt": "string"
      },
      "confidence": "number (0-1)",
      "requires_human_review": "boolean",
      "extraction_notes": "string | null",
      "evidence": [
        {
          "source_url": "string",
          "summary": "string",
          "retrieved_via": "parallel"
        }
      ],
      "status": "flagged | cleared | overridden"
    }
  ],
  "metadata": {
    "model_used": "string",
    "extracted_at": "string (ISO timestamp)",
    "extraction_agent_version": "string",
    "total_pages_scanned": "number"
  }
}
```

## Fields NOT in the original Pydantic schema (Firestore-only additions)

- `entities[].evidence` — empty array by default; filled in later once the Parallel-powered research agent runs. Not part of the entity-extraction step itself.
- `entities[].status` — tracks clearance state per entity (`flagged`/`cleared`/`overridden`). Distinct from `overall_status`, which is the run-level sign-off state.

## Who reads/writes what

- **Entity extraction agent** (Pydantic-based) → writes `run_id`, `script_id`, `script_title`, `entities` (without `evidence`/`status` populated yet), `metadata`
- **Research agent (Parallel)** → fills in `evidence` per entity, may update `entities[].status`
- **Approval UI / IAM gate** → writes `overall_status`, `reviewed_by`, `reviewed_at` (only if caller has `legal_reviewer` claim)
- **Everyone** → reads the whole document to display current state

## Reference implementation

See `create_schema.py` in this folder — a validation script (not part of the live agent pipeline) that creates one example document matching this schema exactly, used to confirm the structure works end-to-end in Firestore before the real extraction agent was built.