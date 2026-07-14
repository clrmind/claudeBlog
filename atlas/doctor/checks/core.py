from __future__ import annotations

import importlib
import json
from pathlib import Path

from atlas.doctor.models import CheckResult, CheckStatus


def check_config(base_dir: Path) -> CheckResult:
    config_json = base_dir / "config.json"
    env_file = base_dir / ".env"

    if not config_json.exists() and not env_file.exists():
        return CheckResult(
            name="Config",
            category="Core",
            status=CheckStatus.ERROR,
            message="설정 파일을 찾지 못했습니다.",
            detail="config.json 또는 .env 필요",
        )

    if config_json.exists():
        try:
            json.loads(config_json.read_text(encoding="utf-8"))
        except Exception as exc:
            return CheckResult(
                name="Config",
                category="Core",
                status=CheckStatus.ERROR,
                message="config.json 형식 오류",
                detail=str(exc),
            )

    found = []
    if config_json.exists():
        found.append("config.json")
    if env_file.exists():
        found.append(".env")

    return CheckResult(
        name="Config",
        category="Core",
        status=CheckStatus.OK,
        message=", ".join(found),
    )


def check_runtime(_base_dir: Path) -> CheckResult:
    modules = (
        "atlas.ai.base",
        "atlas.ai.registry",
        "atlas.ai.router",
        "atlas.ai.runtime",
    )

    try:
        for module in modules:
            importlib.import_module(module)
    except Exception as exc:
        return CheckResult(
            name="AI Runtime",
            category="Core",
            status=CheckStatus.ERROR,
            message="Runtime 로드 실패",
            detail=f"{type(exc).__name__}: {exc}",
        )

    return CheckResult(
        name="AI Runtime",
        category="Core",
        status=CheckStatus.OK,
        message="Provider Router 로드 정상",
    )
