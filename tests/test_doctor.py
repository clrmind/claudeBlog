import tempfile
import unittest
from pathlib import Path

from atlas.doctor.models import CheckResult, CheckStatus
from atlas.doctor.runner import exit_code, run_checks


class DoctorTests(unittest.TestCase):
    def test_exit_code_healthy(self):
        results = [
            CheckResult("A", "Core", CheckStatus.OK, "ok"),
        ]
        self.assertEqual(exit_code(results), 0)

    def test_exit_code_warning(self):
        results = [
            CheckResult("A", "Core", CheckStatus.WARNING, "warning"),
        ]
        self.assertEqual(exit_code(results), 1)

    def test_exit_code_error(self):
        results = [
            CheckResult("A", "Core", CheckStatus.ERROR, "error"),
        ]
        self.assertEqual(exit_code(results), 2)

    def test_run_checks_converts_exception_to_error(self):
        def broken_check(_base_dir):
            raise RuntimeError("boom")

        with tempfile.TemporaryDirectory() as temp_dir:
            results = run_checks(
                Path(temp_dir),
                checks=(broken_check,),
            )

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].status, CheckStatus.ERROR)
        self.assertIn("boom", results[0].detail)


if __name__ == "__main__":
    unittest.main()
