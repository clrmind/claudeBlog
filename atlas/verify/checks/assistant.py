from __future__ import annotations

from pathlib import Path

from atlas.assistant import recommend_from_query
from atlas.verify.models import VerifyResult, VerifyStatus


def verify_assistant(_base_dir: Path) -> VerifyResult:
    try:
        parsed, results = recommend_from_query(
            "경남 수출 벤처기업 지원사업",
            limit=1,
        )
    except Exception as exc:
        return VerifyResult(
            name="Assistant",
            status=VerifyStatus.FAIL,
            message="Assistant 실행 실패",
            detail=f"{type(exc).__name__}: {exc}",
        )

    if not any(
        (
            parsed.region,
            parsed.industry,
            parsed.target,
            parsed.support_type,
            parsed.keywords,
        )
    ):
        return VerifyResult(
            name="Assistant",
            status=VerifyStatus.FAIL,
            message="Query Parser 결과 없음",
        )

    if not results:
        return VerifyResult(
            name="Assistant",
            status=VerifyStatus.FAIL,
            message="추천 결과 없음",
        )

    return VerifyResult(
        name="Assistant",
        status=VerifyStatus.PASS,
        message=f"추천 결과 {len(results)}건",
    )
