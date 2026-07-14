import tempfile
import unittest
from pathlib import Path

from atlas.verify.models import VerifyResult, VerifyStatus
from atlas.verify.runner import exit_code, run_verification


class VerifyTests(unittest.TestCase):
    def test_exit_code_pass(self):
        results = [
            VerifyResult("A", VerifyStatus.PASS, "ok"),
        ]
        self.assertEqual(exit_code(results), 0)

    def test_exit_code_fail(self):
        results = [
            VerifyResult("A", VerifyStatus.FAIL, "fail"),
        ]
        self.assertEqual(exit_code(results), 1)

    def test_run_verification_converts_exception(self):
        def broken(_base_dir):
            raise RuntimeError("boom")

        with tempfile.TemporaryDirectory() as temp_dir:
            results = run_verification(
                Path(temp_dir),
                checks=(broken,),
            )

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].status, VerifyStatus.FAIL)
        self.assertIn("boom", results[0].detail)


if __name__ == "__main__":
    unittest.main()
