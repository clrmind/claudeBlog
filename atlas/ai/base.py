#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class AIResponse:
    text: str
    provider: str
    model: str
    cached: bool = False
    metadata: dict[str, Any] | None = None


class BaseProvider(ABC):
    name = "base"

    @abstractmethod
    def available(self) -> bool:
        """현재 Provider를 사용할 수 있는지 반환한다."""
        raise NotImplementedError

    @abstractmethod
    def generate(
        self,
        prompt: str,
        *,
        model: str | None = None,
        temperature: float = 0.2,
        metadata: dict[str, Any] | None = None,
    ) -> AIResponse:
        """텍스트 생성 요청을 수행한다."""
        raise NotImplementedError

    def summarize(
        self,
        text: str,
        *,
        model: str | None = None,
    ) -> AIResponse:
        prompt = (
            "다음 내용을 핵심 사실 위주로 간결하게 요약하세요.\n\n"
            + text
        )
        return self.generate(prompt, model=model)

    def classify(
        self,
        text: str,
        *,
        labels: list[str],
        model: str | None = None,
    ) -> AIResponse:
        prompt = (
            "다음 텍스트를 제공된 분류 중 하나 이상으로 분류하세요. "
            "JSON 배열만 반환하세요.\n"
            f"분류: {labels}\n\n"
            f"텍스트:\n{text}"
        )
        return self.generate(prompt, model=model)
