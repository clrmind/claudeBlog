from __future__ import annotations

import os
from pathlib import Path

from atlas.ai.providers.gemini import GeminiProvider
from atlas.verify.models import VerifyResult, VerifyStatus


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


def verify_ai_runtime(base_dir: Path) -> VerifyResult:
    key = os.getenv("GEMINI_API_KEY", "").strip()

    if not key:
        key = _read_env_value(
            base_dir / ".env",
            "GEMINI_API_KEY",
        )

    provider = GeminiProvider(api_key=key)

    if not provider.available():
        return VerifyResult(
            name="AI Runtime",
            status=VerifyStatus.FAIL,
            message="사용 가능한 Provider 없음",
            detail="GEMINI_API_KEY",
        )

    return VerifyResult(
        name="AI Runtime",
        status=VerifyStatus.PASS,
        message="Gemini Provider 사용 가능",
    )
