#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Atlas Government Collector v0.1

역할:
- 정부지원사업 상세 페이지 URL을 입력받는다.
- 원본 HTML을 다운로드한다.
- 원본을 data/government/raw/ 폴더에 보존한다.
- 메타데이터 JSON을 함께 생성한다.

주의:
- 아직 특정 사이트 전용 파서는 포함하지 않는다.
- 기존 autoblogger.py는 수정하지 않는다.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from urllib.parse import urlparse

import requests


BASE_DIR = Path(__file__).resolve().parents[2]
RAW_DIR = BASE_DIR / "data" / "government" / "raw"

USER_AGENT = (
    "Mozilla/5.0 (Linux; Android 13) "
    "AppleWebKit/537.36 "
    "(KHTML, like Gecko) "
    "Chrome/120.0 Mobile Safari/537.36"
)


@dataclass
class CollectedDocument:
    source: str
    source_url: str
    source_id: str
    fetched_at: str
    content_hash: str
    http_status: int
    content_type: str
    html_file: str


def detect_source(url: str) -> str:
    """URL의 도메인을 기준으로 출처 이름을 정한다."""
    hostname = (urlparse(url).hostname or "").lower()

    source_map = {
        "bizinfo.go.kr": "bizinfo",
        "k-startup.go.kr": "kstartup",
        "mss.go.kr": "mss",
        "tipa.or.kr": "tipa",
        "nipa.kr": "nipa",
    }

    for domain, source in source_map.items():
        if hostname == domain or hostname.endswith("." + domain):
            return source

    return re.sub(r"[^a-z0-9]+", "_", hostname).strip("_") or "unknown"


def make_source_id(url: str) -> str:
    """URL을 이용해 안정적인 고유 ID를 생성한다."""
    return hashlib.sha256(url.encode("utf-8")).hexdigest()[:20]


def calculate_hash(content: bytes) -> str:
    """원본 데이터의 SHA-256 해시를 계산한다."""
    return hashlib.sha256(content).hexdigest()


def fetch_url(url: str, timeout: int = 30) -> requests.Response:
    """페이지를 다운로드한다."""
    response = requests.get(
        url,
        headers={"User-Agent": USER_AGENT},
        timeout=timeout,
        allow_redirects=True,
    )
    response.raise_for_status()
    return response


def save_document(url: str, response: requests.Response) -> CollectedDocument:
    """HTML 원본과 수집 메타데이터를 저장한다."""
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    source = detect_source(url)
    source_id = make_source_id(url)
    fetched_at = dt.datetime.now(dt.timezone.utc).isoformat()
    content_hash = calculate_hash(response.content)

    html_filename = f"{source}_{source_id}.html"
    json_filename = f"{source}_{source_id}.json"

    html_path = RAW_DIR / html_filename
    json_path = RAW_DIR / json_filename

    html_path.write_bytes(response.content)

    document = CollectedDocument(
        source=source,
        source_url=url,
        source_id=source_id,
        fetched_at=fetched_at,
        content_hash=content_hash,
        http_status=response.status_code,
        content_type=response.headers.get("Content-Type", ""),
        html_file=str(html_path.relative_to(BASE_DIR)),
    )

    json_path.write_text(
        json.dumps(asdict(document), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    return document


def collect(url: str) -> CollectedDocument:
    print(f"📡 수집 시작: {url}")

    response = fetch_url(url)
    document = save_document(url, response)

    print(f"✅ 수집 완료: {document.source}")
    print(f"📄 원본 파일: {document.html_file}")
    print(f"🔐 SHA-256: {document.content_hash}")

    return document


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Atlas 정부지원사업 원본 수집기"
    )
    parser.add_argument(
        "url",
        help="수집할 정부지원사업 상세 페이지 URL",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    try:
        collect(args.url)
        return 0
    except requests.Timeout:
        print("❌ 요청 시간이 초과되었습니다.", file=sys.stderr)
    except requests.HTTPError as exc:
        print(f"❌ HTTP 오류: {exc}", file=sys.stderr)
    except requests.RequestException as exc:
        print(f"❌ 네트워크 오류: {exc}", file=sys.stderr)
    except OSError as exc:
        print(f"❌ 파일 저장 오류: {exc}", file=sys.stderr)
    except Exception as exc:
        print(f"❌ 예상하지 못한 오류: {exc}", file=sys.stderr)

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
