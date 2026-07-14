#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parents[2]
KNOWLEDGE_ROOT = BASE_DIR / "knowledge" / "government"
DB_PATH = BASE_DIR / "data" / "government" / "search.db"


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"JSON 객체가 아닙니다: {path}")
    return data


def flatten_list(value: Any) -> str:
    if not isinstance(value, list):
        return ""
    return " ".join(str(item).strip() for item in value if str(item).strip())


def iter_latest_records():
    for path in sorted(KNOWLEDGE_ROOT.glob("*/*/latest.json")):
        try:
            data = load_json(path)
        except Exception as exc:
            print(f"⚠️ 건너뜀: {path} — {exc}")
            continue

        enrichment = data.get("enrichment")
        if not isinstance(enrichment, dict):
            enrichment = {}

        yield {
            "source": str(data.get("source") or ""),
            "source_id": str(data.get("source_id") or ""),
            "title": str(data.get("title") or ""),
            "organization": str(data.get("organization") or ""),
            "ministry": str(data.get("ministry") or ""),
            "application_deadline": str(data.get("application_deadline") or ""),
            "target": str(data.get("target") or ""),
            "support_summary": str(data.get("support_summary") or ""),
            "content": str(data.get("content") or ""),
            "source_url": str(data.get("source_url") or ""),
            "regions": flatten_list(enrichment.get("regions")),
            "target_groups": flatten_list(enrichment.get("target_groups")),
            "industries": flatten_list(enrichment.get("industries")),
            "technologies": flatten_list(enrichment.get("technologies")),
            "support_types": flatten_list(enrichment.get("support_types")),
            "keywords": flatten_list(enrichment.get("keywords")),
            "recommendation_score": int(enrichment.get("recommendation_score") or 0),
            "knowledge_path": str(path.relative_to(BASE_DIR)),
        }


def connect_db() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def ensure_schema(connection: sqlite3.Connection) -> None:
    connection.execute("""
        CREATE TABLE IF NOT EXISTS opportunities (
            source_id TEXT PRIMARY KEY,
            source TEXT NOT NULL,
            title TEXT NOT NULL,
            organization TEXT,
            ministry TEXT,
            application_deadline TEXT,
            target TEXT,
            support_summary TEXT,
            content TEXT,
            source_url TEXT,
            regions TEXT,
            target_groups TEXT,
            industries TEXT,
            technologies TEXT,
            support_types TEXT,
            keywords TEXT,
            recommendation_score INTEGER NOT NULL DEFAULT 0,
            knowledge_path TEXT
        )
    """)
    connection.execute("""
        CREATE VIRTUAL TABLE IF NOT EXISTS opportunities_fts
        USING fts5(
            source_id UNINDEXED,
            title,
            organization,
            ministry,
            target,
            support_summary,
            content,
            regions,
            target_groups,
            industries,
            technologies,
            support_types,
            keywords,
            tokenize='unicode61'
        )
    """)


def rebuild_index() -> int:
    connection = connect_db()
    try:
        ensure_schema(connection)
        connection.execute("DELETE FROM opportunities")
        connection.execute("DELETE FROM opportunities_fts")
        count = 0
        for record in iter_latest_records():
            connection.execute("""
                INSERT OR REPLACE INTO opportunities (
                    source_id, source, title, organization, ministry,
                    application_deadline, target, support_summary, content,
                    source_url, regions, target_groups, industries,
                    technologies, support_types, keywords,
                    recommendation_score, knowledge_path
                ) VALUES (
                    :source_id, :source, :title, :organization, :ministry,
                    :application_deadline, :target, :support_summary, :content,
                    :source_url, :regions, :target_groups, :industries,
                    :technologies, :support_types, :keywords,
                    :recommendation_score, :knowledge_path
                )
            """, record)
            connection.execute("""
                INSERT INTO opportunities_fts (
                    source_id, title, organization, ministry, target,
                    support_summary, content, regions, target_groups,
                    industries, technologies, support_types, keywords
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                record["source_id"], record["title"], record["organization"],
                record["ministry"], record["target"], record["support_summary"],
                record["content"], record["regions"], record["target_groups"],
                record["industries"], record["technologies"],
                record["support_types"], record["keywords"],
            ))
            count += 1
        connection.commit()
        print(f"✅ 검색 인덱스 생성 완료: {count}건")
        print(f"💾 DB: {DB_PATH.relative_to(BASE_DIR)}")
        return 0
    finally:
        connection.close()


def normalize_query(query: str) -> str:
    terms = [term.strip() for term in query.replace(",", " ").split() if term.strip()]
    return " OR ".join(f'"{term}"' for term in terms)


def search(query: str, limit: int) -> int:
    fts_query = normalize_query(query)
    if not fts_query:
        print("❌ 검색어가 비어 있습니다.")
        return 1

    connection = connect_db()
    try:
        ensure_schema(connection)
        rows = connection.execute("""
            SELECT
                o.source_id,
                o.title,
                o.organization,
                o.application_deadline,
                o.regions,
                o.industries,
                o.support_types,
                o.recommendation_score,
                o.source_url,
                bm25(opportunities_fts) AS rank
            FROM opportunities_fts
            JOIN opportunities AS o
              ON o.source_id = opportunities_fts.source_id
            WHERE opportunities_fts MATCH ?
            ORDER BY rank ASC, o.recommendation_score DESC
            LIMIT ?
        """, (fts_query, max(1, limit))).fetchall()

        if not rows:
            print("ℹ️ 검색 결과가 없습니다.")
            return 0

        print(f"🔎 검색 결과: {len(rows)}건")
        for index, row in enumerate(rows, start=1):
            print()
            print(f"{index}. {row['title']}")
            print(f"   기관: {row['organization'] or '-'}")
            print(f"   마감: {row['application_deadline'] or '-'}")
            print(f"   지역: {row['regions'] or '-'}")
            print(f"   업종: {row['industries'] or '-'}")
            print(f"   유형: {row['support_types'] or '-'}")
            print(f"   추천도: {row['recommendation_score']}점")
            print(f"   URL: {row['source_url'] or '-'}")
        return 0
    finally:
        connection.close()


def status() -> int:
    connection = connect_db()
    try:
        ensure_schema(connection)
        count = connection.execute("SELECT COUNT(*) FROM opportunities").fetchone()[0]
        print(f"📚 검색 인덱스: {count}건")
        print(f"💾 DB: {DB_PATH.relative_to(BASE_DIR)}")
        return 0
    finally:
        connection.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Atlas 정부지원사업 로컬 검색 인덱스")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("build", help="Knowledge 최신본으로 검색 인덱스 재생성")
    search_parser = subparsers.add_parser("search", help="정부지원사업 검색")
    search_parser.add_argument("query", help="예: 서울 디자인 판로")
    search_parser.add_argument("--limit", type=int, default=10)
    subparsers.add_parser("status", help="현재 인덱스 상태 확인")
    args = parser.parse_args()

    try:
        if args.command == "build":
            return rebuild_index()
        if args.command == "search":
            return search(args.query, args.limit)
        if args.command == "status":
            return status()
    except sqlite3.OperationalError as exc:
        print(f"❌ SQLite 오류: {exc}", file=sys.stderr)
        print("ℹ️ 현재 Python의 SQLite에 FTS5가 포함되어 있는지 확인하세요.", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"❌ Search Index 오류: {exc}", file=sys.stderr)
        return 1
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
