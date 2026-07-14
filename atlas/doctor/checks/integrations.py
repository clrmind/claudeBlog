from __future__ import annotations

import importlib
import os
from pathlib import Path

from atlas.doctor.models import CheckResult, CheckStatus


def _read_env_value(path: Path, key: str) -> str:
    if not path.exists():
        return ""

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()

        if not line or line.startswith("#") or "=" not in line:
            continue

        name, value = line.split("=", 1)

        if name.strip() == key:
            return value.strip().strip("\"'")

    return ""


def check_gemini(base_dir: Path) -> CheckResult:
    key = os.getenv("GEMINI_API_KEY", "").strip()

    if not key:
        key = _read_env_value(
            base_dir / ".env",
            "GEMINI_API_KEY",
        )

    if not key:
        return CheckResult(
            name="Gemini",
            category="Providers",
            status=CheckStatus.WARNING,
            message="API Key 미설정",
            detail="GEMINI_API_KEY",
        )

    masked = f"{key[:4]}...{key[-4:]}" if len(key) >= 8 else "설정됨"

    return CheckResult(
        name="Gemini",
        category="Providers",
        status=CheckStatus.OK,
        message=f"API Key 설정됨 ({masked})",
    )


def check_government_plugin(_base_dir: Path) -> CheckResult:
    modules = (
        "plugins.government.collector",
        "plugins.government.normalizer",
        "plugins.government.pipeline",
    )

    try:
        for module in modules:
            importlib.import_module(module)
    except Exception as exc:
        return CheckResult(
            name="Government Plugin",
            category="Plugins",
            status=CheckStatus.ERROR,
            message="Plugin 로드 실패",
            detail=f"{type(exc).__name__}: {exc}",
        )

    return CheckResult(
        name="Government Plugin",
        category="Plugins",
        status=CheckStatus.OK,
        message="Collector, Normalizer, Pipeline 정상",
    )
