from __future__ import annotations

import importlib
import json
from pathlib import Path

from atlas.verify.models import VerifyResult, VerifyStatus


def verify_config(base_dir: Path) -> VerifyResult:
    config = base_dir / "config.json"

    if not config.exists():
        return VerifyResult(
            name="Config",
            status=VerifyStatus.FAIL,
            message="config.json 없음",
            detail=str(config),
        )

    try:
        json.loads(config.read_text(encoding="utf-8"))
    except Exception as exc:
        return VerifyResult(
            name="Config",
            status=VerifyStatus.FAIL,
            message="config.json 파싱 실패",
            detail=f"{type(exc).__name__}: {exc}",
        )

    return VerifyResult(
        name="Config",
        status=VerifyStatus.PASS,
        message="설정 파일 정상",
    )


def verify_government_plugin(_base_dir: Path) -> VerifyResult:
    modules = (
        "plugins.government.collector",
        "plugins.government.normalizer",
        "plugins.government.knowledge_store",
        "plugins.government.ai_tagger",
        "plugins.government.search_index",
        "plugins.government.recommender",
        "plugins.government.pipeline",
    )

    try:
        for module in modules:
            importlib.import_module(module)
    except Exception as exc:
        return VerifyResult(
            name="Government Plugin",
            status=VerifyStatus.FAIL,
            message="모듈 로드 실패",
            detail=f"{type(exc).__name__}: {exc}",
        )

    return VerifyResult(
        name="Government Plugin",
        status=VerifyStatus.PASS,
        message="핵심 모듈 로드 정상",
    )
