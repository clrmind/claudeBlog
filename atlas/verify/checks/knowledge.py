from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from atlas.verify.models import VerifyResult, VerifyStatus


def verify_knowledge(base_dir: Path) -> VerifyResult:
    knowledge_root = base_dir / "knowledge" / "government"
    latest_files = list(knowledge_root.rglob("latest.json"))

    if not latest_files:
        return VerifyResult(
            name="Knowledge",
            status=VerifyStatus.FAIL,
            message="latest.json 없음",
            detail=str(knowledge_root),
        )

    try:
        sample = json.loads(
            latest_files[0].read_text(encoding="utf-8")
        )
    except Exception as exc:
        return VerifyResult(
            name="Knowledge",
            status=VerifyStatus.FAIL,
            message="Knowledge JSON 파싱 실패",
            detail=f"{latest_files[0]}: {exc}",
        )

    required_any = ("title", "source", "source_url")

    if not any(sample.get(key) for key in required_any):
        return VerifyResult(
            name="Knowledge",
            status=VerifyStatus.FAIL,
            message="핵심 필드 없음",
            detail=str(latest_files[0]),
        )

    return VerifyResult(
        name="Knowledge",
        status=VerifyStatus.PASS,
        message=f"{len(latest_files)}개 latest 문서 확인",
    )


def verify_search(base_dir: Path) -> VerifyResult:
    db_path = base_dir / "data" / "government" / "search.db"

    if not db_path.exists():
        return VerifyResult(
            name="Search",
            status=VerifyStatus.FAIL,
            message="search.db 없음",
            detail=str(db_path),
        )

    try:
        with sqlite3.connect(db_path) as connection:
            count = connection.execute(
                "SELECT COUNT(*) FROM opportunities"
            ).fetchone()[0]
    except Exception as exc:
        return VerifyResult(
            name="Search",
            status=VerifyStatus.FAIL,
            message="검색 DB 조회 실패",
            detail=f"{type(exc).__name__}: {exc}",
        )

    if count <= 0:
        return VerifyResult(
            name="Search",
            status=VerifyStatus.FAIL,
            message="검색 인덱스가 비어 있음",
            detail=str(db_path),
        )

    return VerifyResult(
        name="Search",
        status=VerifyStatus.PASS,
        message=f"{count}개 공고 인덱스",
    )
