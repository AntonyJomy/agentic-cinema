\# Agentic Cinema



Multi-agent pre-release compliance certification system for films. Specialist agents assess rights, ratings, trademarks, cast likeness, and territory compliance from contract documents, an arbiter agent aggregates verdicts into a final release/block decision with a full audit trail.



\## Structure



\- `/agents` — specialist and arbiter agent logic

\- `/frontend` — UI

\- `/schemas` — verdict and data schemas shared across agents

\- `/tests` — test suite

\- `/gatekeeper` — MCP wiring and access governance



\## Firestore Setup

This project uses Firestore for entity research caching and RAG (Retrieval-Augmented Generation) with vector embeddings.

### Deploy Firestore Indexes

The project requires a composite vector index for semantic search on the `entity_research_vectors` collection. 

**Option 1: Using gcloud CLI** (recommended if you don't have Firebase CLI):

```bash
gcloud firestore indexes composite create --project=script-clearance-hackathon --database=script-clearance-db --field-config-from-file=firestore.indexes.json
```

**Option 2: Using Firebase CLI** (if installed):

```bash
firebase deploy --only firestore:indexes
```

This will create an index on:
- `entity_type` (ascending order)
- `embedding` (vector field, 1536 dimensions)

**Note:** Index creation can take several minutes. Check status with:
```bash
# Using gcloud
gcloud firestore indexes composite list --database=script-clearance-db

# Or using Firebase CLI
firebase firestore:indexes
```

The vector dimensionality (1536) is configured in `research/embeddings.py` via `research_embedding_dimensionality()` and must match the dimension specified in `firestore.indexes.json`.

\## Status

In active development for the Agentic Cinema hackathon (Devpost).

