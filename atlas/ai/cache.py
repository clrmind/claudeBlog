#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .base import AIResponse


class AICache:
    def __init__(self, root: Path) -> None:
        self.root = root

    def make_key(
        self,
        *,
        provider: str,
        model: str,
        prompt: str,
    ) -> str:
        raw = json.dumps(
            {
                "provider": provider,
                "model": model,
                "prompt": prompt,
            },
            ensure_ascii=False,
            sort_keys=True,
        ).encode("utf-8")

        return hashlib.sha256(raw).hexdigest()

    def get(
        self,
        *,
        provider: str,
        model: str,
        prompt: str,
    ) -> AIResponse | None:
        key = self.make_key(
            provider=provider,
            model=model,
            prompt=prompt,
        )
        path = self.root / provider / f"{key}.json"

        if not path.exists():
            return None

        data = json.loads(path.read_text(encoding="utf-8"))

        return AIResponse(
            text=str(data["text"]),
            provider=str(data["provider"]),
            model=str(data["model"]),
            cached=True,
            metadata=data.get("metadata") or {},
        )

    def set(self, response: AIResponse, prompt: str) -> Path:
        key = self.make_key(
            provider=response.provider,
            model=response.model,
            prompt=prompt,
        )
        path = self.root / response.provider / f"{key}.json"
        path.parent.mkdir(parents=True, exist_ok=True)

        payload: dict[str, Any] = {
            "text": response.text,
            "provider": response.provider,
            "model": response.model,
            "metadata": response.metadata or {},
        }

        temp = path.with_suffix(".json.tmp")
        temp.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temp.replace(path)

        return path
