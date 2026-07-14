#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

from pathlib import Path
from typing import Iterable

from .base import AIResponse
from .breaker import CircuitBreaker
from .cache import AICache
from .registry import ProviderRegistry
from atlas.metrics.recorder import MetricsRecorder


class AIRouter:
    def __init__(
        self,
        *,
        registry: ProviderRegistry,
        cache_root: Path,
        provider_order: Iterable[str],
        metrics: MetricsRecorder | None = None,
    ) -> None:
        self.registry = registry
        self.cache = AICache(cache_root)
        self.provider_order = list(provider_order)
        self.breakers: dict[str, CircuitBreaker] = {}
        self.metrics = metrics

    def breaker_for(self, provider_name: str) -> CircuitBreaker:
        if provider_name not in self.breakers:
            self.breakers[provider_name] = CircuitBreaker()
        return self.breakers[provider_name]

    def generate(
        self,
        prompt: str,
        *,
        model: str | None = None,
        temperature: float = 0.2,
        use_cache: bool = True,
        task: str = "generate",
    ) -> AIResponse:
        last_error: Exception | None = None

        for provider_name in self.provider_order:
            provider = self.registry.get(provider_name)

            if not provider.available():
                continue

            breaker = self.breaker_for(provider_name)

            if not breaker.allow_request():
                continue

            selected_model = model or getattr(
                provider,
                "default_model",
                provider_name,
            )

            if use_cache:
                cached = self.cache.get(
                    provider=provider_name,
                    model=selected_model,
                    prompt=prompt,
                )
                if cached:
                    if self.metrics:
                        with self.metrics.track(
                            provider=provider_name,
                            model=selected_model,
                            task=task,
                            prompt=prompt,
                            cached=True,
                        ):
                            pass
                    return cached

            try:
                if self.metrics:
                    with self.metrics.track(
                        provider=provider_name,
                        model=selected_model,
                        task=task,
                        prompt=prompt,
                    ):
                        response = provider.generate(
                            prompt,
                            model=model,
                            temperature=temperature,
                        )
                else:
                    response = provider.generate(
                        prompt,
                        model=model,
                        temperature=temperature,
                    )

                breaker.record_success()

                if use_cache:
                    self.cache.set(response, prompt)

                return response

            except Exception as exc:
                breaker.record_failure()
                last_error = exc

        if last_error:
            raise RuntimeError(
                f"사용 가능한 AI Provider가 모두 실패했습니다: {last_error}"
            ) from last_error

        raise RuntimeError("사용 가능한 AI Provider가 없습니다.")
