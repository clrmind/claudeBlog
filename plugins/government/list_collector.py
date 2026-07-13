#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

import requests
from bs4 import BeautifulSoup

BASE_DIR = Path(__file__).resolve().parents[2]
QUEUE_DIR = BASE_DIR / "data" / "government" / "queue"
DEFAULT_QUEUE_PATH = QUEUE_DIR / "bizinfo_queue.json"
POSTS_PATH = BASE_DIR / "posts" / "data.json"
DETAIL_PATH = "/sii/siia/selectSIIA200Detail.do"
USER_AGENT = (
    "Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Mobile Safari/537.36"
)

@dataclass
class QueueItem:
    source: str
    source_id: str
    title: str
    url: str
    discovered_at: str
    status: str = "pending"
    attempts: int = 0
    last_error: str = ""


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def fetch_html(url: str, timeout: int = 30) -> str:
    response = requests.get(
        url,
        headers={"User-Agent": USER_AGENT},
        timeout=timeout,
        allow_redirects=True,
    )
    response.raise_for_status()
    response.encoding = response.apparent_encoding or response.encoding
    return response.text


def extract_pblanc_id(url: str) -> str:
    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    values = query.get("pblancId") or query.get("pblancid")
    if values:
        return values[0].strip()
    match = re.search(r"PBLN_\d+", url, re.IGNORECASE)
    return match.group(0).upper() if match else ""


def canonical_detail_url(base_url: str, pblanc_id: str) -> str:
    parsed = urlparse(base_url)
    return urlunparse((
        parsed.scheme or "https",
        parsed.netloc or "www.bizinfo.go.kr",
        DETAIL_PATH,
        "",
        urlencode({"pblancId": pblanc_id}),
        "",
    ))


def iter_detail_candidates(soup: BeautifulSoup, list_url: str) -> Iterable[tuple[str, str]]:
    seen: set[str] = set()

    for anchor in soup.find_all("a"):
        title = clean_text(anchor.get_text(" ", strip=True))
        candidates = [
            anchor.get("href") or "",
            anchor.get("onclick") or "",
            str(anchor.get("data-url") or ""),
            str(anchor.get("data-href") or ""),
            str(anchor.get("data-pblanc-id") or ""),
            str(anchor.get("data-pblancid") or ""),
        ]
        for raw in candidates:
            pblanc_id = extract_pblanc_id(raw)
            if not pblanc_id or pblanc_id in seen:
                continue
            seen.add(pblanc_id)
            yield title or pblanc_id, canonical_detail_url(list_url, pblanc_id)

    for pblanc_id in re.findall(r"PBLN_\d+", str(soup), flags=re.IGNORECASE):
        pblanc_id = pblanc_id.upper()
        if pblanc_id in seen:
            continue
        seen.add(pblanc_id)
        yield pblanc_id, canonical_detail_url(list_url, pblanc_id)


def load_json_list(path: Path) -> list[dict]:
    if not path.exists():
        return []
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    return value if isinstance(value, list) else []


def published_ids() -> set[str]:
    result: set[str] = set()
    for post in load_json_list(POSTS_PATH):
        if post.get("source") != "bizinfo":
            continue
        source_id = str(post.get("source_id") or "").strip()
        source_url = str(post.get("source_url") or post.get("url") or "")
        if source_id:
            result.add(source_id)
        pblanc_id = extract_pblanc_id(source_url)
        if pblanc_id:
            result.add(pblanc_id)
    return result


def existing_queue_items(path: Path) -> list[QueueItem]:
    items: list[QueueItem] = []
    for raw in load_json_list(path):
        try:
            items.append(QueueItem(
                source=str(raw.get("source") or "bizinfo"),
                source_id=str(raw.get("source_id") or ""),
                title=str(raw.get("title") or ""),
                url=str(raw.get("url") or ""),
                discovered_at=str(raw.get("discovered_at") or ""),
                status=str(raw.get("status") or "pending"),
                attempts=int(raw.get("attempts") or 0),
                last_error=str(raw.get("last_error") or ""),
            ))
        except (TypeError, ValueError):
            continue
    return items


def collect_list(list_url: str, queue_path: Path, max_items: int) -> tuple[int, int, int]:
    print(f"📋 기업마당 목록 수집: {list_url}")
    soup = BeautifulSoup(fetch_html(list_url), "html.parser")
    candidates = list(iter_detail_candidates(soup, list_url))
    if max_items > 0:
        candidates = candidates[:max_items]

    already_published = published_ids()
    existing = existing_queue_items(queue_path)
    existing_ids = {item.source_id for item in existing if item.source_id}

    added = skipped_published = skipped_queue = 0
    discovered_at = datetime.now(timezone.utc).isoformat()

    for title, url in candidates:
        pblanc_id = extract_pblanc_id(url)
        if not pblanc_id:
            continue
        if pblanc_id in already_published:
            skipped_published += 1
            continue
        if pblanc_id in existing_ids:
            skipped_queue += 1
            continue
        existing.append(QueueItem(
            source="bizinfo",
            source_id=pblanc_id,
            title=title,
            url=url,
            discovered_at=discovered_at,
        ))
        existing_ids.add(pblanc_id)
        added += 1

    queue_path.parent.mkdir(parents=True, exist_ok=True)
    queue_path.write_text(
        json.dumps([asdict(item) for item in existing], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"🔎 상세 공고 후보: {len(candidates)}건")
    print(f"➕ Queue 신규 추가: {added}건")
    print(f"⏭️ 이미 발행되어 제외: {skipped_published}건")
    print(f"📦 기존 Queue 중복 제외: {skipped_queue}건")
    print(f"💾 Queue 저장: {queue_path.relative_to(BASE_DIR)}")
    return added, skipped_published, skipped_queue


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="기업마당 목록에서 상세 공고를 찾아 Queue에 저장")
    parser.add_argument("url", help="기업마당 지원사업 공고 목록 URL")
    parser.add_argument("--max-items", type=int, default=30, help="확인할 최대 공고 수")
    parser.add_argument("--queue", default=str(DEFAULT_QUEUE_PATH), help="Queue JSON 저장 경로")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    queue_path = Path(args.queue).expanduser()
    if not queue_path.is_absolute():
        queue_path = BASE_DIR / queue_path
    try:
        collect_list(args.url, queue_path, max(0, args.max_items))
        return 0
    except requests.Timeout:
        print("❌ 목록 페이지 요청 시간이 초과되었습니다.", file=sys.stderr)
    except requests.HTTPError as exc:
        print(f"❌ 목록 페이지 HTTP 오류: {exc}", file=sys.stderr)
    except requests.RequestException as exc:
        print(f"❌ 목록 페이지 네트워크 오류: {exc}", file=sys.stderr)
    except OSError as exc:
        print(f"❌ Queue 저장 오류: {exc}", file=sys.stderr)
    except Exception as exc:
        print(f"❌ List Collector 오류: {exc}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
