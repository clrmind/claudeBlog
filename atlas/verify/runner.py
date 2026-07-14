from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from atlas.verify.checks import (
    verify_ai_runtime,
    verify_assistant,
    verify_config,
    verify_government_plugin,
    verify_knowledge,
    verify_search,
)
from atlas.verify.models import VerifyResult, VerifyStatus


VerifyFunction = Callable[[Path], VerifyResult]


DEFAULT_CHECKS: tuple[VerifyFunction, ...] = (
    verify_config,
    verify_government_plugin,
    verify_knowledge,
    verify_search,
    verify_ai_runtime,
    verify_assistant,
)


def run_verification(
    base_dir: Path,
    checks: tuple[VerifyFunction, ...] = DEFAULT_CHECKS,
) -> list[VerifyResult]:
    results: list[VerifyResult] = []

    for check in checks:
        try:
            results.append(check(base_dir))
        except Exception as exc:
            results.append(
                VerifyResult(
                    name=getattr(check, "__name__", "Unknown"),
                    status=VerifyStatus.FAIL,
                    message="Verify 내부 오류",
                    detail=f"{type(exc).__name__}: {exc}",
                )
            )

    return results


def exit_code(results: list[VerifyResult]) -> int:
    return int(
        any(result.status == VerifyStatus.FAIL for result in results)
    )
