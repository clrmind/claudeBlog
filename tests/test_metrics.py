import tempfile
import unittest
from pathlib import Path
from atlas.metrics.recorder import AICallMetric, MetricsRecorder

class MetricsRecorderTests(unittest.TestCase):
    def test_record_and_summary(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            recorder = MetricsRecorder(Path(temp_dir) / "metrics.db")
            recorder.record_ai_call(AICallMetric(
                provider="gemini", model="test", task="blog",
                status="success", elapsed_ms=120, cached=False,
                prompt_hash="abc", estimated_cost_usd=0.001,
            ))
            recorder.record_ai_call(AICallMetric(
                provider="gemini", model="test", task="blog",
                status="success", elapsed_ms=0, cached=True,
                prompt_hash="abc",
            ))
            summary = recorder.summary(24)
            self.assertEqual(summary["calls"], 2)
            self.assertEqual(summary["successes"], 2)
            self.assertEqual(summary["cache_hits"], 1)
            self.assertEqual(summary["cache_hit_rate"], 50.0)

    def test_track_records_error(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            recorder = MetricsRecorder(Path(temp_dir) / "metrics.db")
            with self.assertRaises(RuntimeError):
                with recorder.track(
                    provider="gemini", model="test",
                    task="test", prompt="hello",
                ):
                    raise RuntimeError("boom")
            summary = recorder.summary(24)
            self.assertEqual(summary["calls"], 1)
            self.assertEqual(summary["errors"], 1)

if __name__ == "__main__":
    unittest.main()
