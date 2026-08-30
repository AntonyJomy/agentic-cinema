# Vector Dimensionality Migration Guide

## Problem Summary

Firestore's Vector field type has a hard limit of **2048 dimensions**. The Gemini embedding model (`gemini-embedding-001`) generates vectors at its default dimensionality of **3072**, which exceeds this limit. This caused:

- `InvalidArgument: 400 Vectors must be at most 2048 dimensions` errors on both read and write operations
- Silent failures where RAG indexing failed but entities were reported as SUCCESS
- Native vector search falling back to brute-force scans

## Solution Overview

The fix involves three key changes:

1. **Request reduced dimensionality** (1536) from Gemini API using the `output_dimensionality` parameter
2. **Add L2 normalization** for reduced-dimension embeddings (since only full 3072-dim output is pre-normalized)
3. **Improve error handling** to surface dimension errors instead of silent failures
4. **Migrate existing data** to rebuild the vector collection with correct dimensions

## Files Modified

### Core Changes

- **`research/embeddings.py`** - Request 1536 dims, add L2 normalization
- **`research/rag_config.py`** - Add `research_embedding_dimensionality()` config function
- **`research/vector_store.py`** - Add dimension validation and better error handling
- **`research/retrieval.py`** - Surface critical errors instead of silent logging
- **`orchestrator.py`** - Handle RAG indexing failures properly
- **`scripts/backfill_rag.py`** - Update index creation example to 1536 dims
- **`scripts/migrate_vector_dims.py`** - **NEW** migration script to rebuild vectors

## Migration Steps

### Step 1: Verify Configuration

Check your `.env` file has the correct setting (or add it):

```bash
# Optional - defaults to 1536 if not set
RESEARCH_EMBEDDING_DIMENSIONALITY=1536
```

The system will automatically use 1536 dimensions (valid range: 1-2048).

### Step 2: Test Migration (Dry Run)

Before making any changes, test the migration with a dry run:

```bash
python scripts/migrate_vector_dims.py --dry-run
```

This will show you:
- How many vectors will be deleted
- How many cache entries will be re-indexed
- No actual changes are made

### Step 3: Run Migration

Execute the full migration:

```bash
# Migrate all entries
python scripts/migrate_vector_dims.py

# Or migrate a subset first to test
python scripts/migrate_vector_dims.py --limit 10
```

The script will:
1. Delete all documents in `entity_research_vectors` collection (in batches of 500)
2. Load entries from `entity_research_cache` collection
3. Re-generate embeddings at 1536 dimensions
4. Re-index all cacheable research results
5. Validate dimensions before storing

### Step 4: Create/Update Firestore Vector Index

After migration, ensure the Firestore vector index exists with the correct dimensionality:

```bash
gcloud firestore indexes composite create \
  --collection-group=entity_research_vectors \
  --query-scope=COLLECTION \
  --field-config field-path=entity_type,order=ASCENDING \
  --field-config vector-config='{"dimension":"1536","flat": "{}"}',field-path=embedding
```

**Note:** Index creation can take several minutes depending on the number of documents.

### Step 5: Verify Native Vector Search Works

After migration, check the logs to ensure native vector search is working:

```bash
# Look for these log messages (success):
INFO Native vector search returned X hits for business

# NOT this (fallback):
WARNING Firestore native vector search unavailable; using brute-force scan.
```

## Migration Script Options

```bash
# Show what would be done without making changes
python scripts/migrate_vector_dims.py --dry-run

# Migrate only first N entries (useful for testing)
python scripts/migrate_vector_dims.py --limit 50

# Re-index without deleting (if collection is already empty)
python scripts/migrate_vector_dims.py --skip-clear

# Combine options
python scripts/migrate_vector_dims.py --dry-run --limit 10
```

## What Changed Under the Hood

### Before (Broken)

```python
# embeddings.py - OLD
response = client.models.embed_content(
    model=research_embedding_model(),
    contents=text,
)
# Returns 3072 dimensions (exceeds Firestore limit)

# Then truncated to 2048 in embed_text()
return embedding[:2048]  # Naive truncation, loses semantic quality
```

### After (Fixed)

```python
# embeddings.py - NEW
response = client.models.embed_content(
    model=research_embedding_model(),
    contents=text,
    config={"output_dimensionality": 1536},  # Request reduced dims
)

# L2 normalize reduced-dimension output
if len(vector) != 3072:
    norm = math.sqrt(sum(v * v for v in vector))
    if norm > 0:
        vector = [v / norm for v in vector]
```

### Error Handling Improvements

**Before:**
```python
try:
    # ... upsert vector ...
except Exception:
    logger.warning("Failed to index research for RAG (%s)", name)
    # Silent failure - entity still reported as SUCCESS
```

**After:**
```python
try:
    # ... upsert vector ...
except ValueError as e:
    if "dimension" in str(e).lower():
        logger.error("Dimension mismatch: %s", e)
        raise RuntimeError(f"RAG indexing failed: {e}")  # Surface error
```

## Troubleshooting

### Error: "Embedding dimension mismatch: expected 1536, got 3072"

**Cause:** The `output_dimensionality` parameter is not being passed correctly.

**Fix:** Ensure you're running the latest code and the config function is being called.

### Error: "InvalidArgument: 400 Vectors must be at most 2048 dimensions"

**Cause:** Old vectors with 3072 dimensions still exist in Firestore.

**Fix:** Run the migration script to clear and rebuild:
```bash
python scripts/migrate_vector_dims.py
```

### Warning: "Native vector search unavailable; using brute-force scan"

**Cause:** Firestore vector index doesn't exist or has wrong dimensionality.

**Fix:** Create/update the index with the command in Step 4.

### Migration fails with "Failed to re-index X: dimension mismatch"

**Cause:** Configuration issue or API not respecting `output_dimensionality`.

**Fix:**
1. Check `.env` has `RESEARCH_EMBEDDING_DIMENSIONALITY=1536`
2. Verify Gemini API supports the parameter (it should for `gemini-embedding-001`)
3. Check API key is valid and has quota

## Benefits of This Fix

✅ **No more dimension limit errors** - 1536 dims is well under the 2048 limit
✅ **Better semantic quality** - Matryoshka embeddings (1536 dims) preserve more meaning than naive truncation
✅ **Visible failures** - Dimension errors are now surfaced clearly in logs
✅ **Consistent data** - All vectors in the collection have the same dimensionality
✅ **Native vector search works** - No more fallback to brute-force scans

## Configuration Reference

### Environment Variables

```bash
# Target embedding dimensionality (default: 1536, max: 2048)
RESEARCH_EMBEDDING_DIMENSIONALITY=1536

# Embedding model (default: gemini-embedding-001)
RESEARCH_EMBEDDING_MODEL=gemini-embedding-001

# Embedding backend (default: gemini, test: test)
RESEARCH_EMBEDDING_BACKEND=gemini

# Enable/disable RAG (default: true)
RESEARCH_RAG_ENABLED=true

# Enable/disable native vector search (default: true)
RESEARCH_RAG_FIRESTORE_NATIVE=true
```

## Technical Details

### Why 1536 Dimensions?

- **Firestore limit:** Maximum 2048 dimensions for native vector search
- **Safety margin:** 1536 provides headroom below the limit
- **Common standard:** 1536 is used by OpenAI's text-embedding-3-large
- **Matryoshka support:** Gemini models support semantic-preserving truncation
- **Performance:** Smaller vectors = faster search and lower storage costs

### L2 Normalization

Gemini's full 3072-dim embeddings are pre-normalized. When using `output_dimensionality`, the truncated vectors need explicit normalization:

```python
norm = math.sqrt(sum(v * v for v in vector))
if norm > 0:
    vector = [v / norm for v in vector]
```

This ensures:
- Cosine similarity calculations work correctly
- Vector magnitudes are consistent
- Semantic relationships are preserved

## Support

If you encounter issues during migration:

1. Check logs for specific error messages
2. Run with `--dry-run` first to validate
3. Test with `--limit 10` on a small subset
4. Verify Firestore index is created and active
5. Check that API keys and credentials are valid

For questions about the fix, see the code changes in:
- `research/embeddings.py`
- `research/vector_store.py`
- `research/retrieval.py`
