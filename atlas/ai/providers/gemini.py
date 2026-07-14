#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import os
from typing import Any

import requests

from atlas.ai.base import AIResponse, BaseProvider


class GeminiProvider(BaseProvider):
    name = "gemini"

    def __init__(
        self,
        *,
        api_key: str | None = None,
        default_model: str = "gemini-2.5-flash",
        timeout: int = 60,
    ) -> None:
        self.api_key = api_key or os.getenv("GEMINI_API_KEY", "").strip()
        self.default_model = default_model
        self.timeout = timeout

    def available(self) -> bool:
        return bool(self.api_key)

    def generate(
        self,
        prompt: str,
        *,
        model: str | None = None,
        temperature: float = 0.2,
        metadata: dict[str, Any] | None = None,
    ) -> AIResponse:
        if not self.available():
            raise RuntimeError("GEMINI_API_KEY가 없습니다.")

        selected_model = model or self.default_model
        url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{selected_model}:generateContent?key={self.api_key}"
        )

        payload = {
            "contents": [
                {
                    "parts": [
                        {
                            "text": prompt,
                        }
                    ]
                }
            ],
            "generationConfig": {
                "temperature": temperature,
            },
        }

        response = requests.post(
            url,
            json=payload,
            timeout=self.timeout,
        )

        if response.status_code == 429:
            raise RuntimeError("Gemini quota exceeded (HTTP 429)")

        if response.status_code in (500, 502, 503, 504):
            raise RuntimeError(
                f"Gemini temporary server error (HTTP {response.status_code})"
            )

        response.raise_for_status()
        data = response.json()

        try:
            text = data["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError(
                f"Gemini 응답 형식이 예상과 다릅니다: {data}"
            ) from exc

        return AIResponse(
            text=text,
            provider=self.name,
            model=selected_model,
            cached=False,
            metadata=metadata or {},
        )
