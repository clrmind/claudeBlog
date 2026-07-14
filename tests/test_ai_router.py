#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import tempfile
import unittest
from pathlib import Path

from atlas.ai.base import AIResponse, BaseProvider
from atlas.ai.registry import ProviderRegistry
from atlas.ai.router import AIRouter


class FakeProvider(BaseProvider):
    name = "fake"

    def __init__(self):
        self.calls = 0

    def available(self):
        return True

    def generate(self, prompt, *, model=None, temperature=0.2, metadata=None):
        self.calls += 1
        return AIResponse(
            text=f"response:{prompt}",
            provider=self.name,
            model=model or "fake-model",
        )


class FailingProvider(FakeProvider):
    name = "failing"

    def generate(self, prompt, *, model=None, temperature=0.2, metadata=None):
        self.calls += 1
        raise RuntimeError("temporary failure")


class RouterTests(unittest.TestCase):
    def test_cache_reuses_response(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            registry = ProviderRegistry()
            provider = FakeProvider()
            registry.register(provider)

            router = AIRouter(
                registry=registry,
                cache_root=Path(temp_dir),
                provider_order=["fake"],
            )

            first = router.generate("hello", model="fake-model")
            second = router.generate("hello", model="fake-model")

            self.assertEqual(first.text, second.text)
            self.assertEqual(provider.calls, 1)
            self.assertTrue(second.cached)

    def test_fallback_provider(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            registry = ProviderRegistry()
            failing = FailingProvider()
            working = FakeProvider()
            registry.register(failing)
            registry.register(working)

            router = AIRouter(
                registry=registry,
                cache_root=Path(temp_dir),
                provider_order=["failing", "fake"],
            )

            result = router.generate("hello")

            self.assertEqual(result.provider, "fake")
            self.assertEqual(failing.calls, 1)
            self.assertEqual(working.calls, 1)


if __name__ == "__main__":
    unittest.main()
