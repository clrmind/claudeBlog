#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Atlas Government Recommender v0.1

역할
- 지역, 업종, 기업유형, 키워드를 입력받는다.
- SQLite 검색 인덱스에서 관련 공고를 찾는다.
- 태그 일치도 + 추천도 + 마감일을 반영해 점수를 계산한다.

사용:
python -m plugins.government.recommender \
  --region 경남 \
  --industry 수출 \
  --target 벤처기업 \
  --keyword "해외진출"
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from datetime import date, datetime
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[2]
DB_PATH = BASE_DIR / "data" / "government" / "search.db"


def parse_date(value: str) -> date | None:
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None


def normalize(value: str) -> str:
    return (value or "").strip().lower()


def contains(text: str, value: str) -> bool:
    if not value:
        return False
    return normalize(value) in normalize(text)


def calculate_score(
    row: sqlite3.Row,
    *,
    region: str,
    industry: str,
    target: str,
    technology: str,
    support_type: str,
    keyword: str,
) -> tuple[int, list[str]]:
    score = int(row["recommendation_score"] or 0)
    reasons: list[str] = []

    checks = (
        ("regions", region, 20, f"지역 일치: {region}"),
        ("industries", industry, 20, f"업종 일치: {industry}"),
        ("target_groups", target, 20, f"기업유형 일치: {target}"),
        ("technologies", technology, 15, f"기술 일치: {technology}"),
        ("support_types", support_type, 15, f"지원유형 일치: {support_type}"),
    )

    for field, value, points, reason in checks:
        if value and contains(str(row[field] or ""), value):
            score += points
            reasons.append(reason)

    if keyword:
        searchable = " ".join(
            str(row[field] or "")
            for field in (
                "title",
                "target",
                "support_summary",
                "content",
                "keywords",
            )
        )
        if contains(searchable, keyword):
            score += 15
            reasons.append(f"키워드 일치: {keyword}")

    deadline = parse_date(str(row["application_deadline"] or ""))
    if deadline:
        days_left = (deadline - date.today()).days
        if days_left < 0:
            score -= 50
            reasons.append("마감 종료")
        elif days_left <= 7:
            score += 10
            reasons.append(f"마감 임박: D-{days_left}")
        elif days_left <= 30:
            score += 5
            reasons.append(f"마감 D-{days_left}")

    return max(0, min(score, 100)), reasons


def recommend(
    *,
    region: str,
    industry: str,
    target: str,
    technology: str,
    support_type: str,
    keyword: str,
    limit: int,
) -> int:
    if not DB_PATH.exists():
        print(
            "❌ 검색 DB가 없습니다. 먼저 search_index build를 실행하세요.",
            file=sys.stderr,
        )
        return 1

    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row

    try:
        rows = connection.execute(
            """
            SELECT *
            FROM opportunities
            ORDER BY recommendation_score DESC
            """
        ).fetchall()

        scored = []

        for row in rows:
            score, reasons = calculate_score(
                row,
                region=region,
                industry=industry,
                target=target,
                technology=technology,
                support_type=support_type,
                keyword=keyword,
            )

            if score <= 0:
                continue

            # 최소 하나 이상의 프로필 일치가 있을 때 우선 추천
            if any((region, industry, target, technology, support_type, keyword)):
                if not reasons:
                    continue

            scored.append((score, reasons, row))

        scored.sort(
            key=lambda item: (
                item[0],
                int(item[2]["recommendation_score"] or 0),
            ),
            reverse=True,
        )

        results = scored[:max(1, limit)]

        if not results:
            print("ℹ️ 조건에 맞는 추천 결과가 없습니다.")
            return 0

        print(f"🎯 추천 결과: {len(results)}건")

        for index, (score, reasons, row) in enumerate(results, start=1):
            print()
            print(f"{index}. [{score}점] {row['title']}")
            print(f"   기관: {row['organization'] or '-'}")
            print(f"   마감: {row['application_deadline'] or '-'}")
            print(f"   지역: {row['regions'] or '-'}")
            print(f"   업종: {row['industries'] or '-'}")
            print(f"   대상: {row['target_groups'] or '-'}")
            print(f"   유형: {row['support_types'] or '-'}")
            print(
                "   추천 이유: "
                + (", ".join(reasons) if reasons else "기본 추천도")
            )
            print(f"   URL: {row['source_url'] or '-'}")

        return 0

    finally:
        connection.close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Atlas 기업 프로필 기반 정부지원사업 추천"
    )
    parser.add_argument("--region", default="")
    parser.add_argument("--industry", default="")
    parser.add_argument("--target", default="")
    parser.add_argument("--technology", default="")
    parser.add_argument("--support-type", default="")
    parser.add_argument("--keyword", default="")
    parser.add_argument("--limit", type=int, default=10)
    return parser


def main() -> int:
    args = build_parser().parse_args()

    return recommend(
        region=args.region,
        industry=args.industry,
        target=args.target,
        technology=args.technology,
        support_type=args.support_type,
        keyword=args.keyword,
        limit=args.limit,
    )


if __name__ == "__main__":
    raise SystemExit(main())
