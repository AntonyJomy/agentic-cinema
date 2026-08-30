"""
research/metrics.py

Per-run counters for how entity research was resolved (cache / RAG / Parallel).
"""
from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger("agentic_cinema.research_metrics")


class ResearchSource(str, Enum):
    SESSION_CACHE = "session_cache"
    PERSISTENT_CACHE = "persistent_cache"
    RAG_HIGH = "rag_high"
    RAG_MEDIUM_PARALLEL = "rag_medium_parallel"
    PARALLEL = "parallel"
    FAILED = "failed"


@dataclass
class ResearchMetrics:
    counts: dict[str, int] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def record(self, source: ResearchSource) -> None:
        key = source.value
        with self._lock:
            self.counts[key] = self.counts.get(key, 0) + 1
        logger.info("Research source: %s", key)

    def total(self) -> int:
        with self._lock:
            return sum(self.counts.values())

    def parallel_calls(self) -> int:
        with self._lock:
            return self.counts.get(ResearchSource.PARALLEL.value, 0) + self.counts.get(
                ResearchSource.RAG_MEDIUM_PARALLEL.value, 0
            )

    def summary_lines(self) -> list[str]:
        with self._lock:
            items = sorted(self.counts.items())
        if not items:
            return ["Research metrics: (none)"]
        parts = [f"{key}={count}" for key, count in items]
        parallel = self.parallel_calls()
        return [
            "Research metrics: " + ", ".join(parts),
            f"  Parallel calls (incl. RAG-augmented): {parallel}",
        ]

    def log_summary(self) -> None:
        for line in self.summary_lines():
            logger.info(line)


_global_metrics: ResearchMetrics | None = None
_global_lock = threading.Lock()


def get_research_metrics() -> ResearchMetrics:
    global _global_metrics
    if _global_metrics is not None:
        return _global_metrics
    with _global_lock:
        if _global_metrics is None:
            _global_metrics = ResearchMetrics()
        return _global_metrics


def reset_research_metrics_for_tests() -> ResearchMetrics:
    global _global_metrics
    with _global_lock:
        _global_metrics = ResearchMetrics()
        return _global_metrics
