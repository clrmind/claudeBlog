#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Atlas Government Scheduler v0.1

역할
- 지정 간격마다 Auto Runner 실행
- 실패 시 로그 기록
- Queue 적체/실패 건수 점검
- 강제 종료 후에도 다음 실행에서 계속 동작

사용 예시
python -m plugins.government.scheduler \
  --interval-minutes 180 \
  --discover 30 \
  --process 3 \
  --delay 10 \
  --no-push

한 번만 점검
python -m plugins.government.scheduler --health-only

주의
- 스마트폰 절전 정책에 의해 Termux 프로세스가 종료될 수 있습니다.
- 운영 전 Termux 배터리 최적화 제외가 권장됩니다.
"""

from __future__ import annotations

import argparse
import json
import signal
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any


BASE_DIR = Path(__file__).resolve().parents[2]
QUEUE_PATH = (
    BASE_DIR / "data" / "government" / "queue" / "bizinfo_queue.json"
)
LOG_DIR = BASE_DIR / "logs"
HEALTH_PATH = BASE_DIR / "data" / "government" / "health.json"

RUNNING = True


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def load_queue() -> list[dict[str, Any]]:
    if not QUEUE_PATH.exists():
        return []

    try:
        data = json.loads(QUEUE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []

    return data if isinstance(data, list) else []


def queue_counts() -> dict[str, int]:
    counts = {
        "total": 0,
        "pending": 0,
        "processing": 0,
        "retry": 0,
        "done": 0,
        "failed": 0,
    }

    for item in load_queue():
        if not isinstance(item, dict):
            continue

        counts["total"] += 1
        status = str(item.get("status") or "pending")
        if status in counts:
            counts[status] += 1

    return counts


def write_health(
    status: str,
    *,
    last_exit_code: int | None = None,
    message: str = "",
) -> None:
    HEALTH_PATH.parent.mkdir(parents=True, exist_ok=True)

    payload = {
        "status": status,
        "checked_at": now_iso(),
        "last_exit_code": last_exit_code,
        "message": message,
        "queue": queue_counts(),
    }

    HEALTH_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def append_scheduler_log(message: str) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    path = LOG_DIR / "scheduler.log"

    with path.open("a", encoding="utf-8") as handle:
        handle.write(f"[{now_iso()}] {message}\n")


def run_auto_runner(args: argparse.Namespace) -> int:
    command = [
        sys.executable,
        "-m",
        "plugins.government.auto_runner",
        "--discover",
        str(args.discover),
        "--process",
        str(args.process),
        "--delay",
        str(args.delay),
        "--max-attempts",
        str(args.max_attempts),
        "--push" if args.push else "--no-push",
    ]

    if args.list_url:
        command.extend(["--list-url", args.list_url])

    print("\n" + "=" * 72)
    print(f"⏰ 실행 시각: {now_iso()}")
    print("$ " + " ".join(command))
    append_scheduler_log("RUN " + " ".join(command))

    result = subprocess.run(
        command,
        cwd=BASE_DIR,
    )

    counts = queue_counts()

    if result.returncode == 0:
        message = (
            f"정상 완료 | pending={counts['pending']} "
            f"retry={counts['retry']} failed={counts['failed']}"
        )
        print(f"✅ {message}")
        append_scheduler_log("SUCCESS " + message)
        write_health(
            "healthy",
            last_exit_code=0,
            message=message,
        )
    else:
        message = (
            f"실행 실패 code={result.returncode} | "
            f"pending={counts['pending']} "
            f"retry={counts['retry']} failed={counts['failed']}"
        )
        print(f"❌ {message}")
        append_scheduler_log("FAIL " + message)
        write_health(
            "degraded",
            last_exit_code=result.returncode,
            message=message,
        )

    return result.returncode


def print_health() -> int:
    counts = queue_counts()

    status = "healthy"
    warnings: list[str] = []

    if counts["failed"] > 0:
        status = "degraded"
        warnings.append(f"failed {counts['failed']}건")

    if counts["retry"] > 0:
        status = "degraded"
        warnings.append(f"retry {counts['retry']}건")

    if counts["processing"] > 0:
        status = "degraded"
        warnings.append(f"processing 잔류 {counts['processing']}건")

    if counts["pending"] >= 50:
        status = "degraded"
        warnings.append(f"pending 적체 {counts['pending']}건")

    message = ", ".join(warnings) if warnings else "특이사항 없음"

    print("🩺 Atlas Health")
    print(f"- 상태: {status}")
    print(f"- 전체 Queue: {counts['total']}건")
    print(f"- pending: {counts['pending']}건")
    print(f"- processing: {counts['processing']}건")
    print(f"- retry: {counts['retry']}건")
    print(f"- done: {counts['done']}건")
    print(f"- failed: {counts['failed']}건")
    print(f"- 메시지: {message}")

    write_health(status, message=message)
    return 0 if status == "healthy" else 2


def handle_signal(signum: int, _frame: object) -> None:
    global RUNNING
    RUNNING = False
    print(f"\n⚠️ 종료 신호 수신: {signum}")
    append_scheduler_log(f"STOP signal={signum}")
    write_health(
        "stopped",
        message=f"종료 신호 수신: {signum}",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Atlas 정부지원사업 Scheduler + Health Monitor"
    )

    parser.add_argument(
        "--interval-minutes",
        type=int,
        default=180,
        help="자동 실행 간격(분). 기본 180분",
    )
    parser.add_argument(
        "--discover",
        type=int,
        default=30,
        help="목록에서 확인할 공고 수. 기본 30",
    )
    parser.add_argument(
        "--process",
        type=int,
        default=3,
        help="한 번에 처리할 공고 수. 기본 3",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=10.0,
        help="공고 처리 사이 대기 초. 기본 10",
    )
    parser.add_argument(
        "--max-attempts",
        type=int,
        default=3,
        help="공고당 최대 시도 횟수. 기본 3",
    )
    parser.add_argument(
        "--list-url",
        default="",
        help="기업마당 목록 URL. 생략 시 Auto Runner 기본값 사용",
    )
    parser.add_argument(
        "--run-once",
        action="store_true",
        help="한 번만 실행하고 종료",
    )
    parser.add_argument(
        "--health-only",
        action="store_true",
        help="Queue 상태만 점검",
    )

    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--push",
        action="store_true",
        help="실제 GitHub push",
    )
    group.add_argument(
        "--no-push",
        action="store_true",
        help="GitHub push 생략. 기본 동작",
    )

    return parser


def main() -> int:
    args = build_parser().parse_args()

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    if args.health_only:
        return print_health()

    interval_seconds = max(1, args.interval_minutes) * 60

    while RUNNING:
        run_auto_runner(args)

        if args.run_once:
            return 0

        if not RUNNING:
            break

        next_run = datetime.fromtimestamp(
            time.time() + interval_seconds
        ).isoformat(timespec="minutes")

        print(
            f"\n💤 다음 실행: {next_run} "
            f"({args.interval_minutes}분 후)"
        )
        append_scheduler_log(
            f"SLEEP minutes={args.interval_minutes} next={next_run}"
        )

        slept = 0
        while RUNNING and slept < interval_seconds:
            step = min(30, interval_seconds - slept)
            time.sleep(step)
            slept += step

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
