import tempfile
import unittest
from pathlib import Path

from atlas.ai.base import AIResponse, BaseProvider
from atlas.ai.registry import ProviderRegistry
from atlas.ai.router import AIRouter
from atlas.metrics.recorder import MetricsRecorder

class FakeProvider(BaseProvider):
    name = "fake"

    def available(self):
        return True

    def generate(
        self,
        prompt,
        *,
        model=None,
        temperature=0.2,
        metadata=None,
    ):
        return AIResponse(
            text="OK",
            provider=self.name,
            model=model or "fake-model",
        )

class RuntimeMetricsIntegrationTests(unittest.TestCase):
    def test_router_records_success_and_cache(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            registry = ProviderRegistry()
            registry.register(FakeProvider())
            metrics = MetricsRecorder(root / "metrics.db")

            router = AIRouter(
                registry=registry,
                cache_root=root / "cache",
                provider_order=["fake"],
                metrics=metrics,
            )

            first = router.generate(
                "hello",
                model="fake-model",
                task="test",
            )
            second = router.generate(
                "hello",
                model="fake-model",
                task="test",
            )

            summary = metrics.summary(24)

            self.assertFalse(first.cached)
            self.assertTrue(second.cached)
            self.assertEqual(summary["calls"], 2)
            self.assertEqual(summary["successes"], 2)
            self.assertEqual(summary["cache_hits"], 1)

if __name__ == "__main__":
    unittest.main()
