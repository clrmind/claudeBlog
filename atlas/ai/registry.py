#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

from typing import Iterable

from .base import BaseProvider


class ProviderRegistry:
    def __init__(self) -> None:
        self._providers: dict[str, BaseProvider] = {}

    def register(self, provider: BaseProvider) -> None:
        name = provider.name.strip().lower()

        if not name or name == "base":
            raise ValueError("유효한 Provider 이름이 필요합니다.")

        self._providers[name] = provider

    def unregister(self, name: str) -> None:
        self._providers.pop(name.strip().lower(), None)

    def get(self, name: str) -> BaseProvider:
        key = name.strip().lower()

        if key not in self._providers:
            raise KeyError(f"등록되지 않은 Provider입니다: {name}")

        return self._providers[key]

    def available(self) -> list[BaseProvider]:
        return [
            provider
            for provider in self._providers.values()
            if provider.available()
        ]

    def names(self) -> list[str]:
        return sorted(self._providers)

    def all(self) -> Iterable[BaseProvider]:
        return self._providers.values()


registry = ProviderRegistry()
