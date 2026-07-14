from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from atlas.doctor.checks import (
    check_config,
    check_gemini,
    check_government_plugin,
    check_knowledge_store,
    check_metrics_db,
    check_runtime,
    check_search_db,
)
from atlas.doctor.models import CheckResult, CheckStatus


CheckFunction = Callable[[Path], CheckResult]


DEFAULT_CHECKS: tuple[CheckFunction, ...] = (
    check_config,
    check_runtime,
    check_metrics_db,
    check_search_db,
    check_knowledge_store,
    check_gemini,
    check_government_plugin,
)


def run_checks(
    base_dir: Path,
    checks: tuple[CheckFunction, ...] = DEFAULT_CHECKS,
) -> list[CheckResult]:
    results: list[CheckResult] = []

    for check in checks:
        try:
            results.append(check(base_dir))
        except Exception as exc:
            results.append(
                CheckResult(
                    name=getattr(check, "__name__", "Unknown Check"),
                    category="Internal",
                    status=CheckStatus.ERROR,
                    message="Doctor 내부 오류",
                    detail=f"{type(exc).__name__}: {exc}",
                )
            )

    return results


def exit_code(results: list[CheckResult]) -> int:
    if any(result.status == CheckStatus.ERROR for result in results):
        return 2

    if any(result.status == CheckStatus.WARNING for result in results):
        return 1

    return 0
