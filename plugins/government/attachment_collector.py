#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import hashlib
import json
import mimetypes
import re
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable
from urllib.parse import parse_qs, unquote, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

BASE_DIR = Path(__file__).resolve().parents[2]
ATTACHMENT_ROOT = BASE_DIR / "data" / "government" / "attachments"
USER_AGENT = (
    "Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Mobile Safari/537.36"
)
ALLOWED_EXTENSIONS = {
    ".pdf", ".hwp", ".hwpx", ".doc", ".docx",
    ".xls", ".xlsx", ".ppt", ".pptx", ".zip",
}

@dataclass
class AttachmentRecord:
    source_id: str
    title: str
    source_url: str
    download_url: str
    filename: str
    stored_file: str
    content_type: str
    size_bytes: int
    sha256: str
    downloaded_at: str

def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()

def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()

def safe_filename(name: str, fallback: str) -> str:
    name = unquote(name or "").strip().replace("/", "_").replace("\\", "_")
    name = re.sub(r'[<>:"|?*\x00-\x1f]', "_", name)
    name = re.sub(r"\s+", " ", name).strip(" .")
    return name[:180] or fallback

def extension_from_url_or_name(url: str, name: str) -> str:
    for value in (name, urlparse(url).path):
        suffix = Path(unquote(value)).suffix.lower()
        if suffix in ALLOWED_EXTENSIONS:
            return suffix
    return ""

def filename_from_url(url: str) -> str:
    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    for key in ("fileName", "filename", "orgFileName", "atchFileNm", "fileNm", "downFileName"):
        values = query.get(key)
        if values:
            return unquote(values[0])
    return unquote(Path(parsed.path).name)

def extract_attachment_links(html_text: str, page_url: str) -> Iterable[tuple[str, str]]:
    soup = BeautifulSoup(html_text, "html.parser")
    seen: set[str] = set()

    for anchor in soup.find_all("a"):
        label = clean_text(anchor.get_text(" ", strip=True))
        values = [
            anchor.get("href") or "",
            anchor.get("onclick") or "",
            anchor.get("data-url") or "",
            anchor.get("data-href") or "",
            anchor.get("data-file") or "",
        ]
        for raw in values:
            if not raw:
                continue
            urls = re.findall(r"https?://[^\s'\"]+|/[^\s'\"]+", str(raw))
            if not urls and str(raw).startswith(("http", "/")):
                urls = [str(raw)]
            for candidate in urls:
                candidate = candidate.rstrip(");,'\"")
                full_url = urljoin(page_url, candidate)
                guessed_name = label or filename_from_url(full_url)
                ext = extension_from_url_or_name(full_url, guessed_name)
                looks_download = any(
                    token in full_url.lower()
                    for token in ("download", "filedown", "atchfile", "selectfile", "file.do", "filedownload")
                )
                if not ext and not looks_download:
                    continue
                if full_url in seen:
                    continue
                seen.add(full_url)
                yield guessed_name, full_url

def load_metadata(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("메타데이터 JSON 형식이 올바르지 않습니다.")
    return data

def decode_html(path: Path) -> str:
    raw = path.read_bytes()
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("cp949", errors="replace")

def download_file(url: str, referer: str) -> requests.Response:
    response = requests.get(
        url,
        headers={"User-Agent": USER_AGENT, "Referer": referer},
        timeout=60,
        allow_redirects=True,
    )
    response.raise_for_status()
    return response

def collect_attachments(metadata_path: Path) -> list[AttachmentRecord]:
    metadata = load_metadata(metadata_path)
    source_id = str(metadata.get("source_id") or "").strip()
    page_url = str(metadata.get("source_url") or "").strip()
    html_file = str(metadata.get("html_file") or "").strip()

    if not source_id or not page_url or not html_file:
        raise ValueError("source_id, source_url, html_file이 모두 필요합니다.")

    html_path = BASE_DIR / html_file
    if not html_path.exists():
        raise FileNotFoundError(f"HTML 파일이 없습니다: {html_path}")

    links = list(extract_attachment_links(decode_html(html_path), page_url))
    item_dir = ATTACHMENT_ROOT / source_id
    files_dir = item_dir / "files"
    manifest_path = item_dir / "manifest.json"
    files_dir.mkdir(parents=True, exist_ok=True)

    existing = []
    if manifest_path.exists():
        try:
            loaded = json.loads(manifest_path.read_text(encoding="utf-8"))
            if isinstance(loaded, list):
                existing = loaded
        except Exception:
            existing = []

    known_urls = {str(x.get("download_url") or "") for x in existing if isinstance(x, dict)}
    known_hashes = {str(x.get("sha256") or "") for x in existing if isinstance(x, dict)}
    records: list[AttachmentRecord] = []

    print(f"📎 첨부파일 후보: {len(links)}건")

    for index, (label, url) in enumerate(links, start=1):
        if url in known_urls:
            print(f"⏭️ 이미 수집된 URL: {label or url}")
            continue
        try:
            response = download_file(url, referer=page_url)
        except requests.RequestException as exc:
            print(f"⚠️ 다운로드 실패: {label or url} — {exc}")
            continue

        content = response.content
        if not content:
            continue

        digest = hashlib.sha256(content).hexdigest()
        if digest in known_hashes:
            print(f"⏭️ 동일 내용 파일: {label or url}")
            continue

        content_type = response.headers.get(
            "Content-Type", ""
        ).split(";")[0].strip()

        disposition = response.headers.get(
            "Content-Disposition", ""
        )

        header_name = ""

        filename_star = re.search(
            r"filename\\*=UTF-8''([^;]+)",
            disposition,
            flags=re.IGNORECASE,
        )

        filename_normal = re.search(
            r'filename="?([^";]+)"?',
            disposition,
            flags=re.IGNORECASE,
        )

        if filename_star:
            header_name = unquote(filename_star.group(1))
        elif filename_normal:
            header_name = unquote(filename_normal.group(1))

        proposed_name = (
            header_name
            or filename_from_url(response.url)
            or filename_from_url(url)
            or label
            or f"attachment_{index:02d}"
        )

        ext = extension_from_url_or_name(
            response.url,
            proposed_name,
        )

        if not ext:
            if content.startswith(b"%PDF"):
                ext = ".pdf"
            elif content.startswith(
                bytes.fromhex("D0CF11E0A1B11AE1")
            ):
                ext = ".hwp"
            elif content.startswith(b"PK\\x03\\x04"):
                ext = ".zip"

                try:
                    import io
                    import zipfile

                    with zipfile.ZipFile(
                        io.BytesIO(content)
                    ) as archive:
                        names = set(archive.namelist())

                    if (
                        "Contents/content.hpf" in names
                        or any(
                            name.startswith("Contents/")
                            for name in names
                        )
                    ):
                        ext = ".hwpx"

                except Exception:
                    pass

            else:
                guessed = mimetypes.guess_extension(
                    content_type
                )
                ext = (
                    guessed
                    if guessed in ALLOWED_EXTENSIONS
                    else ".bin"
                )

        if Path(proposed_name).suffix.lower() not in ALLOWED_EXTENSIONS:
            if proposed_name in ("다운로드", "바로보기"):
                proposed_name = f"attachment_{index:02d}"

            proposed_name = f"{proposed_name}{ext}"

        filename = safe_filename(proposed_name, f"attachment_{index:02d}{ext}")
        stored_path = files_dir / filename
        if stored_path.exists():
            stored_path = files_dir / f"{stored_path.stem}_{digest[:8]}{stored_path.suffix}"

        stored_path.write_bytes(content)

        record = AttachmentRecord(
            source_id=source_id,
            title=label,
            source_url=page_url,
            download_url=url,
            filename=stored_path.name,
            stored_file=str(stored_path.relative_to(BASE_DIR)),
            content_type=content_type,
            size_bytes=len(content),
            sha256=digest,
            downloaded_at=utc_now(),
        )
        records.append(record)
        existing.append(asdict(record))
        known_urls.add(url)
        known_hashes.add(digest)
        print(f"✅ 저장: {stored_path.name} ({len(content):,} bytes)")

    tmp = manifest_path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(manifest_path)
    print(f"💾 Manifest: {manifest_path.relative_to(BASE_DIR)}")
    return records

def find_latest_metadata() -> Path:
    raw_dir = BASE_DIR / "data" / "government" / "raw"
    files = list(raw_dir.glob("*.json"))
    if not files:
        raise FileNotFoundError("수집 메타데이터가 없습니다.")
    return max(files, key=lambda p: p.stat().st_mtime)

def main() -> int:
    parser = argparse.ArgumentParser(description="Atlas 정부지원사업 첨부파일 수집기")
    parser.add_argument("metadata", nargs="?", help="Collector 메타데이터 JSON. 생략하면 최신 파일")
    args = parser.parse_args()
    try:
        path = Path(args.metadata).expanduser().resolve() if args.metadata else find_latest_metadata()
        records = collect_attachments(path)
        print(f"📊 이번 실행 신규 저장: {len(records)}건")
        return 0
    except Exception as exc:
        print(f"❌ Attachment Collector 오류: {exc}", file=sys.stderr)
        return 1

if __name__ == "__main__":
    raise SystemExit(main())
