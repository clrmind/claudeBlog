from __future__ import annotations
import hashlib
import sqlite3
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from contextlib import contextmanager

@dataclass
class AICallMetric:
    provider: str
    model: str
    task: str
    status: str
    elapsed_ms: int
    cached: bool
    prompt_hash: str
    error_type: str = ""
    error_message: str = ""
    input_tokens: int | None = None
    output_tokens: int | None = None
    estimated_cost_usd: float | None = None

class MetricsRecorder:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self._lock = threading.Lock()
        self._ensure_schema()

    def _connect(self) -> sqlite3.Connection:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript("""
            CREATE TABLE IF NOT EXISTS ai_calls (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                provider TEXT NOT NULL,
                model TEXT NOT NULL,
                task TEXT NOT NULL,
                status TEXT NOT NULL,
                elapsed_ms INTEGER NOT NULL,
                cached INTEGER NOT NULL DEFAULT 0,
                prompt_hash TEXT NOT NULL,
                error_type TEXT NOT NULL DEFAULT '',
                error_message TEXT NOT NULL DEFAULT '',
                input_tokens INTEGER,
                output_tokens INTEGER,
                estimated_cost_usd REAL
            );
            CREATE INDEX IF NOT EXISTS idx_ai_calls_created_at
                ON ai_calls(created_at);
            CREATE INDEX IF NOT EXISTS idx_ai_calls_provider
                ON ai_calls(provider);
            """)

    @staticmethod
    def prompt_hash(prompt: str) -> str:
        return hashlib.sha256(prompt.encode("utf-8")).hexdigest()

    def record_ai_call(self, metric: AICallMetric) -> None:
        with self._lock, self._connect() as conn:
            conn.execute("""
                INSERT INTO ai_calls (
                    created_at, provider, model, task, status,
                    elapsed_ms, cached, prompt_hash, error_type,
                    error_message, input_tokens, output_tokens,
                    estimated_cost_usd
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                datetime.now(timezone.utc).isoformat(),
                metric.provider, metric.model, metric.task, metric.status,
                int(metric.elapsed_ms), int(metric.cached), metric.prompt_hash,
                metric.error_type, metric.error_message[:1000],
                metric.input_tokens, metric.output_tokens,
                metric.estimated_cost_usd,
            ))

    @contextmanager
    def track(self, *, provider: str, model: str, task: str,
              prompt: str, cached: bool = False):
        started = perf_counter()
        context = {"input_tokens": None, "output_tokens": None,
                   "estimated_cost_usd": None}
        try:
            yield context
        except Exception as exc:
            self.record_ai_call(AICallMetric(
                provider=provider, model=model, task=task,
                status="error",
                elapsed_ms=round((perf_counter() - started) * 1000),
                cached=cached,
                prompt_hash=self.prompt_hash(prompt),
                error_type=type(exc).__name__,
                error_message=str(exc),
                input_tokens=context["input_tokens"],
                output_tokens=context["output_tokens"],
                estimated_cost_usd=context["estimated_cost_usd"],
            ))
            raise
        else:
            self.record_ai_call(AICallMetric(
                provider=provider, model=model, task=task,
                status="success",
                elapsed_ms=round((perf_counter() - started) * 1000),
                cached=cached,
                prompt_hash=self.prompt_hash(prompt),
                input_tokens=context["input_tokens"],
                output_tokens=context["output_tokens"],
                estimated_cost_usd=context["estimated_cost_usd"],
            ))

    def summary(self, hours: int = 24) -> dict:
        modifier = f"-{max(1, hours)} hours"
        with self._connect() as conn:
            totals = conn.execute("""
                SELECT
                    COUNT(*) AS calls,
                    SUM(CASE WHEN status='success' THEN 1 ELSE 0 END) AS successes,
                    SUM(CASE WHEN status='error' THEN 1 ELSE 0 END) AS errors,
                    SUM(CASE WHEN cached=1 THEN 1 ELSE 0 END) AS cache_hits,
                    AVG(elapsed_ms) AS average_latency_ms,
                    COALESCE(SUM(estimated_cost_usd), 0) AS estimated_cost_usd
                FROM ai_calls
                WHERE datetime(created_at) >= datetime('now', ?)
            """, (modifier,)).fetchone()

            providers = conn.execute("""
                SELECT provider, COUNT(*) AS calls,
                    SUM(CASE WHEN status='success' THEN 1 ELSE 0 END) AS successes,
                    SUM(CASE WHEN status='error' THEN 1 ELSE 0 END) AS errors,
                    AVG(elapsed_ms) AS average_latency_ms,
                    SUM(CASE WHEN cached=1 THEN 1 ELSE 0 END) AS cache_hits
                FROM ai_calls
                WHERE datetime(created_at) >= datetime('now', ?)
                GROUP BY provider
                ORDER BY calls DESC, provider ASC
            """, (modifier,)).fetchall()

        calls = int(totals["calls"] or 0)
        successes = int(totals["successes"] or 0)
        cache_hits = int(totals["cache_hits"] or 0)
        return {
            "hours": max(1, hours),
            "calls": calls,
            "successes": successes,
            "errors": int(totals["errors"] or 0),
            "success_rate": round(successes / calls * 100, 1) if calls else 0.0,
            "cache_hits": cache_hits,
            "cache_hit_rate": round(cache_hits / calls * 100, 1) if calls else 0.0,
            "average_latency_ms": round(float(totals["average_latency_ms"] or 0), 1),
            "estimated_cost_usd": round(float(totals["estimated_cost_usd"] or 0), 6),
            "providers": [dict(row) for row in providers],
        }
