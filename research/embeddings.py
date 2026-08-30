"""
research/embeddings.py

Text embeddings for semantic research retrieval.

Backends:
  - gemini: Google text-embedding-004 (production)
  - test: deterministic bag-of-words vectors (unit tests, no API)
"""
from __future__ import annotations

import hashlib
import logging
import math
import os
import re
import threading
from typing import Protocol

from research.rag_config import research_embedding_backend, research_embedding_model, research_embedding_dimensionality

logger = logging.getLogger("agentic_cinema.research_rag")

_WORD_RE = re.compile(r"[a-z0-9']+")
_TEST_DIM = 128


class EmbeddingProvider(Protocol):
    def embed(self, text: str) -> list[float]: ...


class GeminiEmbeddingProvider:
    def __init__(self) -> None:
        self._client = None
        self._lock = threading.Lock()

    def _get_client(self):
        if self._client is not None:
            return self._client
        with self._lock:
            if self._client is not None:
                return self._client
            from google import genai

            api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
            if not api_key:
                raise RuntimeError("GOOGLE_API_KEY or GEMINI_API_KEY required for RAG embeddings")
            self._client = genai.Client(api_key=api_key)
            return self._client

    def embed(self, text: str) -> list[float]:
        client = self._get_client()
        target_dim = research_embedding_dimensionality()
        
        # Request reduced dimensionality to fit Firestore's 2048-dim limit
        # Gemini models support output_dimensionality via Matryoshka Representation Learning
        response = client.models.embed_content(
            model=research_embedding_model(),
            contents=(text or "").strip() or " ",
            config={"output_dimensionality": target_dim},
        )
        embeddings = getattr(response, "embeddings", None) or []
        if not embeddings:
            raise RuntimeError("Embedding API returned no vectors")
        values = getattr(embeddings[0], "values", None)
        if not values:
            raise RuntimeError("Embedding API returned empty vector")
        
        vector = [float(v) for v in values]
        
        # L2 normalize when using non-default dimensionality
        # (only full 3072-dim output from Gemini is pre-normalized)
        if len(vector) != 3072:
            norm = math.sqrt(sum(v * v for v in vector))
            if norm > 0:
                vector = [v / norm for v in vector]
                logger.debug(
                    "L2 normalized embedding vector (%d dims) for Firestore compatibility",
                    len(vector),
                )
        
        return vector


class TestEmbeddingProvider:
    """Deterministic vectors for tests — overlapping words yield high similarity."""

    def embed(self, text: str) -> list[float]:
        vector = [0.0] * _TEST_DIM
        for word in _WORD_RE.findall((text or "").lower()):
            bucket = int(hashlib.md5(word.encode()).hexdigest(), 16) % _TEST_DIM
            vector[bucket] += 1.0
        norm = math.sqrt(sum(v * v for v in vector))
        if norm == 0:
            return vector
        return [v / norm for v in vector]


_provider: EmbeddingProvider | None = None
_provider_lock = threading.Lock()


def get_embedding_provider() -> EmbeddingProvider:
    global _provider
    if _provider is not None:
        return _provider
    with _provider_lock:
        if _provider is not None:
            return _provider
        backend = research_embedding_backend()
        if backend == "test":
            _provider = TestEmbeddingProvider()
        else:
            _provider = GeminiEmbeddingProvider()
        return _provider


def reset_embedding_provider_for_tests(provider: EmbeddingProvider | None = None) -> EmbeddingProvider:
    global _provider
    with _provider_lock:
        _provider = provider or TestEmbeddingProvider()
        return _provider


def embed_text(text: str) -> list[float]:
    """Generate embedding vector at configured dimensionality for Firestore."""
    embedding = get_embedding_provider().embed(text)
    
    expected_dim = research_embedding_dimensionality()
    if len(embedding) != expected_dim:
        logger.warning(
            "Embedding dimension mismatch: expected %d, got %d",
            expected_dim,
            len(embedding),
        )
    
    return embedding


def cosine_similarity(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)
