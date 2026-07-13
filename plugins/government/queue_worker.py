#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Atlas Government Queue Worker v0.1

역할
- bizinfo_queue.json에서 pending/retry 항목을 읽는다.
- 한 건씩 기존 government pipeline으로 처리한다.
- 성공 시 done, 실패 시 retry 또는 failed 상태로 기록한다.
- 중간에 종료되어도 Queue 상태를 파일에 즉시 저장한다.

사용 예시
python -m plugins.government.queue_worker --limit 3 --no-push

실제 배포
python -m plugins.government.queue_worker --limit 3 --push
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


BASE_DIR = Path(__file__).resolve().parents[2]
DEFAULT_QUEUE_PATH = (
    BASE_DIR / "data" / "government" / "queue" / "bizinfo_queue.json"
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_queue(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"Queue 파일이 없습니다: {path}")

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Queue JSON 형식이 잘못되었습니다: {exc}") from exc

    if not isinstance(data, list):
        raise ValueError("Queue JSON 최상위 값은 배열이어야 합니다.")

    normalized: list[dict[str, Any]] = []

    for item in data:
        if not isinstance(item, dict):
            continue

        normalized.append(
            {
                "source": str(item.get("source") or "bizinfo"),
                "source_id": str(item.get("source_id") or ""),
                "title": str(item.get("title") or ""),
                "url": str(item.get("url") or ""),
                "discovered_at": str(item.get("discovered_at") or ""),
                "status": str(item.get("status") or "pending"),
                "attempts": int(item.get("attempts") or 0),
                "last_error": str(item.get("last_error") or ""),
                "last_attempt_at": str(item.get("last_attempt_at") or ""),
                "completed_at": str(item.get("completed_at") or ""),
            }
        )

    return normalized


def save_queue(path: Path, queue: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    temp_path = path.with_suffix(path.suffix + ".tmp")
    temp_path.write_text(
        json.dumps(queue, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    temp_path.replace(path)


def eligible(item: dict[str, Any], max_attempts: int) -> bool:
    status = item.get("status")

    if status == "pending":
        return True

    if status == "retry" and int(item.get("attempts") or 0) < max_attempts:
        return True

    return False


def run_pipeline(url: str, push: bool) -> tuple[bool, str]:
    command = [
        sys.executable,
        "-m",
        "plugins.government.pipeline",
        url,
        "--push" if push else "--no-push",
    ]

    result = subprocess.run(
        command,
        cwd=BASE_DIR,
        text=True,
        capture_output=True,
    )

    output = "\n".join(
        part.strip()
        for part in (result.stdout, result.stderr)
        if part and part.strip()
    )

    if output:
        print(output)

    return result.returncode == 0, output[-4000:]


def process_queue(
    queue_path: Path,
    limit: int,
    max_attempts: int,
    delay_seconds: float,
    push: bool,
) -> int:
    queue = load_queue(queue_path)
    candidates = [
        (index, item)
        for index, item in enumerate(queue)
        if eligible(item, max_attempts)
    ]

    if limit > 0:
        candidates = candidates[:limit]

    if not candidates:
        print("ℹ️ 처리할 pending/retry 공고가 없습니다.")
        return 0

    print(f"📦 처리 예정: {len(candidates)}건")
    success_count = 0
    failure_count = 0

    for position, (index, item) in enumerate(candidates, start=1):
        title = item.get("title") or item.get("source_id") or "제목 없음"
        url = item.get("url") or ""

        print("\n" + "=" * 72)
        print(f"[{position}/{len(candidates)}] 🚀 처리 시작: {title}")
        print(f"URL: {url}")

        if not url:
            item["status"] = "failed"
            item["last_error"] = "URL이 없습니다."
            item["last_attempt_at"] = utc_now()
            failure_count += 1
            save_queue(queue_path, queue)
            continue

        item["status"] = "processing"
        item["attempts"] = int(item.get("attempts") or 0) + 1
        item["last_attempt_at"] = utc_now()
        item["last_error"] = ""
        save_queue(queue_path, queue)

        success, output = run_pipeline(url, push=push)

        if success:
            item["status"] = "done"
            item["completed_at"] = utc_now()
            item["last_error"] = ""
            success_count += 1
            print(f"✅ 완료: {title}")
        else:
            attempts = int(item.get("attempts") or 0)
            item["last_error"] = output or "알 수 없는 파이프라인 오류"

            if attempts >= max_attempts:
                item["status"] = "failed"
                print(
                    f"❌ 최종 실패: {title} "
                    f"({attempts}/{max_attempts}회)"
                )
            else:
                item["status"] = "retry"
                print(
                    f"⚠️ 재시도 예정: {title} "
                    f"({attempts}/{max_attempts}회)"
                )

            failure_count += 1

        save_queue(queue_path, queue)

        if delay_seconds > 0 and position < len(candidates):
            print(f"⏳ {delay_seconds:g}초 대기")
            time.sleep(delay_seconds)

    print("\n" + "=" * 72)
    print("📊 Queue Worker 결과")
    print(f"✅ 성공: {success_count}건")
    print(f"❌ 실패/재시도: {failure_count}건")
    print(f"💾 Queue: {queue_path.relative_to(BASE_DIR)}")

    return 0 if failure_count == 0 else 2


def print_status(queue_path: Path) -> int:
    queue = load_queue(queue_path)
    counts: dict[str, int] = {}

    for item in queue:
        status = str(item.get("status") or "unknown")
        counts[status] = counts.get(status, 0) + 1

    print(f"📦 전체 Queue: {len(queue)}건")

    for status in (
        "pending",
        "processing",
        "retry",
        "done",
        "failed",
        "unknown",
    ):
        if counts.get(status):
            print(f"- {status}: {counts[status]}건")

    return 0


def recover_processing(queue_path: Path) -> int:
    """
    이전 실행이 강제 종료되어 processing에 남은 항목을 retry로 복구한다.
    """
    queue = load_queue(queue_path)
    recovered = 0

    for item in queue:
        if item.get("status") == "processing":
            item["status"] = "retry"
            item["last_error"] = (
                item.get("last_error")
                or "이전 Worker 실행이 완료되지 않아 retry로 복구됨"
            )
            recovered += 1

    if recovered:
        save_queue(queue_path, queue)

    print(f"♻️ processing → retry 복구: {recovered}건")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Atlas 정부지원사업 Queue Worker"
    )
    parser.add_argument(
        "--queue",
        default=str(DEFAULT_QUEUE_PATH),
        help="Queue JSON 경로",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=1,
        help="한 번에 처리할 최대 건수. 기본 1",
    )
    parser.add_argument(
        "--max-attempts",
        type=int,
        default=3,
        help="공고당 최대 시도 횟수. 기본 3",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=5.0,
        help="공고 처리 사이 대기 초. 기본 5",
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Queue 상태만 출력",
    )
    parser.add_argument(
        "--recover",
        action="store_true",
        help="processing 상태를 retry로 복구",
    )

    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--push",
        action="store_true",
        help="각 신규 글을 GitHub에 실제 push",
    )
    group.add_argument(
        "--no-push",
        action="store_true",
        help="GitHub push 생략. 기본 동작",
    )

    return parser


def main() -> int:
    args = build_parser().parse_args()
    queue_path = Path(args.queue).expanduser()

    if not queue_path.is_absolute():
        queue_path = BASE_DIR / queue_path

    try:
        if args.status:
            return print_status(queue_path)

        if args.recover:
            return recover_processing(queue_path)

        return process_queue(
            queue_path=queue_path,
            limit=max(0, args.limit),
            max_attempts=max(1, args.max_attempts),
            delay_seconds=max(0.0, args.delay),
            push=args.push,
        )

    except FileNotFoundError as exc:
        print(f"❌ 파일 오류: {exc}", file=sys.stderr)
    except ValueError as exc:
        print(f"❌ Queue 오류: {exc}", file=sys.stderr)
    except KeyboardInterrupt:
        print("\n⚠️ 사용자 중단. 현재 상태는 Queue에 저장되어 있습니다.")
        return 130
    except Exception as exc:
        print(f"❌ Queue Worker 오류: {exc}", file=sys.stderr)

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
