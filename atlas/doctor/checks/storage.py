from __future__ import annotations

import sqlite3
from pathlib import Path

from atlas.doctor.models import CheckResult, CheckStatus


def _check_sqlite(
    path: Path,
    *,
    name: str,
    category: str,
    required_table: str | None = None,
    missing_status: CheckStatus = CheckStatus.WARNING,
) -> CheckResult:
    if not path.exists():
        return CheckResult(
            name=name,
            category=category,
            status=missing_status,
            message="파일 없음",
            detail=str(path),
        )

    try:
        with sqlite3.connect(path) as connection:
            connection.execute("SELECT 1").fetchone()

            if required_table:
                row = connection.execute(
                    """
                    SELECT name
                    FROM sqlite_master
                    WHERE type='table' AND name=?
                    """,
                    (required_table,),
                ).fetchone()

                if row is None:
                    return CheckResult(
                        name=name,
                        category=category,
                        status=CheckStatus.ERROR,
                        message=f"필수 테이블 없음: {required_table}",
                        detail=str(path),
                    )

    except Exception as exc:
        return CheckResult(
            name=name,
            category=category,
            status=CheckStatus.ERROR,
            message="SQLite 열기 실패",
            detail=f"{type(exc).__name__}: {exc}",
        )

    size = path.stat().st_size
    return CheckResult(
        name=name,
        category=category,
        status=CheckStatus.OK,
        message=f"정상 ({size:,} bytes)",
        detail=str(path),
    )


def check_metrics_db(base_dir: Path) -> CheckResult:
    return _check_sqlite(
        base_dir / "data" / "system" / "metrics.db",
        name="Metrics DB",
        category="Storage",
        required_table="ai_calls",
    )


def check_search_db(base_dir: Path) -> CheckResult:
    return _check_sqlite(
        base_dir / "data" / "government" / "search.db",
        name="Search DB",
        category="Knowledge",
        required_table="opportunities",
    )


def check_knowledge_store(base_dir: Path) -> CheckResult:
    path = base_dir / "knowledge" / "government"

    if not path.exists():
        return CheckResult(
            name="Knowledge Store",
            category="Knowledge",
            status=CheckStatus.WARNING,
            message="디렉터리 없음",
            detail=str(path),
        )

    latest_files = list(path.rglob("latest.json"))

    if not latest_files:
        return CheckResult(
            name="Knowledge Store",
            category="Knowledge",
            status=CheckStatus.WARNING,
            message="저장된 Knowledge 없음",
            detail=str(path),
        )

    return CheckResult(
        name="Knowledge Store",
        category="Knowledge",
        status=CheckStatus.OK,
        message=f"{len(latest_files)}개 latest 문서",
        detail=str(path),
    )
