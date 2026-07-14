#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parents[2]
KNOWLEDGE_ROOT = BASE_DIR / "knowledge" / "government"

def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()

def canonical_json_bytes(data: dict[str, Any]) -> bytes:
    return json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")

def calculate_record_hash(data: dict[str, Any]) -> str:
    ignored = {"fetched_at", "stored_at", "knowledge_version", "record_hash"}
    stable = {k: v for k, v in data.items() if k not in ignored}
    return hashlib.sha256(canonical_json_bytes(stable)).hexdigest()

def extract_year(data: dict[str, Any]) -> str:
    for field in ("application_start", "application_deadline", "fetched_at"):
        value = str(data.get(field) or "")
        if len(value) >= 4 and value[:4].isdigit():
            return value[:4]
    return datetime.now().strftime("%Y")

def safe_source_id(data: dict[str, Any]) -> str:
    source_id = str(data.get("source_id") or "").strip()
    if not source_id:
        raise ValueError("source_id가 없습니다.")
    allowed = "".join(c for c in source_id if c.isalnum() or c in ("_", "-"))
    if not allowed:
        raise ValueError("유효한 source_id가 아닙니다.")
    return allowed

def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("최상위 JSON 값은 객체여야 합니다.")
    return data

def portable_path(path: Path) -> str:
    try:
        return str(path.relative_to(BASE_DIR))
    except ValueError:
        return str(path)


def write_json_atomic(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    temp_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    temp_path.replace(path)

def load_manifest(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {
            "source": "",
            "source_id": "",
            "title": "",
            "created_at": utc_now(),
            "updated_at": "",
            "latest_version": 0,
            "latest_hash": "",
            "versions": [],
        }
    return load_json(path)

def store_knowledge(normalized_path: Path) -> tuple[str, Path, int]:
    data = load_json(normalized_path)
    source = str(data.get("source") or "unknown").strip()
    source_id = safe_source_id(data)
    year = extract_year(data)
    record_hash = calculate_record_hash(data)

    item_dir = KNOWLEDGE_ROOT / year / source_id
    versions_dir = item_dir / "versions"
    manifest_path = item_dir / "manifest.json"
    latest_path = item_dir / "latest.json"

    manifest = load_manifest(manifest_path)
    if manifest.get("latest_hash") == record_hash:
        return "unchanged", latest_path, int(manifest.get("latest_version") or 0)

    next_version = int(manifest.get("latest_version") or 0) + 1
    version_path = versions_dir / f"v{next_version:04d}.json"

    stored = dict(data)
    stored["knowledge_version"] = next_version
    stored["record_hash"] = record_hash
    stored["stored_at"] = utc_now()

    write_json_atomic(version_path, stored)
    write_json_atomic(latest_path, stored)

    versions = manifest.get("versions")
    if not isinstance(versions, list):
        versions = []
    versions.append({
        "version": next_version,
        "file": portable_path(version_path),
        "record_hash": record_hash,
        "stored_at": stored["stored_at"],
        "content_hash": str(data.get("content_hash") or ""),
    })

    updated_manifest = {
        "source": source,
        "source_id": source_id,
        "title": str(data.get("title") or ""),
        "year": year,
        "created_at": manifest.get("created_at") or utc_now(),
        "updated_at": stored["stored_at"],
        "latest_version": next_version,
        "latest_hash": record_hash,
        "latest_file": portable_path(latest_path),
        "versions": versions,
    }
    write_json_atomic(manifest_path, updated_manifest)
    return "stored", latest_path, next_version

def find_latest_normalized() -> Path:
    normalized_dir = BASE_DIR / "data" / "government" / "normalized"
    files = list(normalized_dir.glob("*.json"))
    if not files:
        raise FileNotFoundError(f"정규화 JSON이 없습니다: {normalized_dir}")
    return max(files, key=lambda p: p.stat().st_mtime)

def main() -> int:
    parser = argparse.ArgumentParser(description="Atlas 정부지원사업 Knowledge Store")
    parser.add_argument("normalized_json", nargs="?")
    args = parser.parse_args()
    try:
        path = Path(args.normalized_json).expanduser().resolve() if args.normalized_json else find_latest_normalized()
        status, latest_path, version = store_knowledge(path)
        if status == "unchanged":
            print(f"ℹ️ 내용 변경 없음. 현재 v{version:04d}")
        else:
            print(f"✅ Knowledge 저장 완료: v{version:04d}")
        print(f"💾 최신본: {latest_path.relative_to(BASE_DIR)}")
        return 0
    except Exception as exc:
        print(f"❌ Knowledge Store 오류: {exc}", file=sys.stderr)
        return 1

if __name__ == "__main__":
    raise SystemExit(main())
