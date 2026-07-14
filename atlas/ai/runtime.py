from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from atlas.ai.providers.gemini import GeminiProvider
from atlas.ai.registry import ProviderRegistry
from atlas.ai.router import AIRouter
from atlas.metrics.recorder import MetricsRecorder

BASE_DIR = Path(__file__).resolve().parents[2]
CACHE_ROOT = BASE_DIR / "data" / "system" / "ai_cache"
METRICS_DB = BASE_DIR / "data" / "system" / "metrics.db"

@lru_cache(maxsize=1)
def get_router() -> AIRouter:
    registry = ProviderRegistry()
    registry.register(GeminiProvider())
    metrics = MetricsRecorder(METRICS_DB)

    return AIRouter(
        registry=registry,
        cache_root=CACHE_ROOT,
        provider_order=["gemini"],
        metrics=metrics,
    )
