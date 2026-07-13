#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Atlas Government Auto Runner v0.1

역할
- 기업마당 목록 페이지에서 신규 공고를 Queue에 추가
- Queue Worker를 실행해 지정 건수만 처리
- 중복 실행 방지(lock file)
- 실행 로그 저장

사용 예시
python -m plugins.government.auto_runner \
  --list-url "https://www.bizinfo.go.kr/sii/siia/selectSIIA200List.do?rows=15&cpage=1&schEndAt=N" \
  --discover 30 \
  --process 3 \
  --no-push

실제 배포
python -m plugins.government.auto_runner \
  --list-url "목록URL" \
  --discover 30 \
  --process 3 \
  --push
"""

from __future__ import annotations

import argparse
import contextlib
import fcntl
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator


BASE_DIR = Path(__file__).resolve().parents[2]
LOG_DIR = BASE_DIR / "logs"
LOCK_DIR = BASE_DIR / "data" / "government" / "locks"
LOCK_PATH = LOCK_DIR / "auto_runner.lock"
QUEUE_PATH = (
    BASE_DIR / "data" / "government" / "queue" / "bizinfo_queue.json"
)

DEFAULT_LIST_URL = (
    "https://www.bizinfo.go.kr/sii/siia/selectSIIA200View.do"
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def timestamp_for_filename() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def append_log(message: str, log_path: Path) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    line = f"[{datetime.now().isoformat(timespec='seconds')}] {message}\n"
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(line)


@contextlib.contextmanager
def single_instance_lock(path: Path) -> Iterator[None]:
    """
    같은 작업이 동시에 두 번 실행되는 것을 방지한다.
    Termux/리눅스의 fcntl 파일 잠금을 사용한다.
    """
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8") as handle:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError(
                "이미 Atlas Auto Runner가 실행 중입니다."
            ) from exc

        handle.write(
            json.dumps(
                {
                    "pid": os.getpid(),
                    "started_at": utc_now(),
                },
                ensure_ascii=False,
            )
        )
        handle.flush()

        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def run_command(
    command: list[str],
    log_path: Path,
) -> int:
    printable = " ".join(command)
    print(f"$ {printable}")
    append_log(f"COMMAND {printable}", log_path)

    process = subprocess.Popen(
        command,
        cwd=BASE_DIR,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        bufsize=1,
    )

    assert process.stdout is not None

    for line in process.stdout:
        print(line, end="")
        append_log(line.rstrip(), log_path)

    return process.wait()


def queue_counts(path: Path) -> dict[str, int]:
    if not path.exists():
        return {}

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}

    counts: dict[str, int] = {}

    if not isinstance(data, list):
        return counts

    for item in data:
        if not isinstance(item, dict):
            continue

        status = str(item.get("status") or "unknown")
        counts[status] = counts.get(status, 0) + 1

    counts["total"] = len(data)
    return counts


def print_queue_summary() -> None:
    counts = queue_counts(QUEUE_PATH)

    if not counts:
        print("📦 Queue 데이터가 없습니다.")
        return

    print("\n📊 현재 Queue 상태")
    print(f"- total: {counts.get('total', 0)}건")

    for status in ("pending", "processing", "retry", "done", "failed"):
        if counts.get(status):
            print(f"- {status}: {counts[status]}건")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Atlas 정부지원사업 자동 운영 스크립트"
    )
    parser.add_argument(
        "--list-url",
        default=DEFAULT_LIST_URL,
        help="기업마당 공고 목록 URL",
    )
    parser.add_argument(
        "--discover",
        type=int,
        default=30,
        help="목록에서 확인할 최대 공고 수. 기본 30",
    )
    parser.add_argument(
        "--process",
        type=int,
        default=1,
        help="이번 실행에서 처리할 최대 공고 수. 기본 1",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=10.0,
        help="공고 처리 간 대기 초. 기본 10",
    )
    parser.add_argument(
        "--max-attempts",
        type=int,
        default=3,
        help="공고당 최대 처리 시도 횟수. 기본 3",
    )
    parser.add_argument(
        "--collect-only",
        action="store_true",
        help="목록 수집만 실행하고 Worker는 실행하지 않음",
    )
    parser.add_argument(
        "--work-only",
        action="store_true",
        help="목록 수집 없이 기존 Queue만 처리",
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="현재 Queue 상태만 출력",
    )

    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--push",
        action="store_true",
        help="신규 글 생성 후 GitHub에 실제 push",
    )
    group.add_argument(
        "--no-push",
        action="store_true",
        help="GitHub push 생략. 기본 동작",
    )

    return parser


def main() -> int:
    args = build_parser().parse_args()

    if args.status:
        print_queue_summary()
        return 0

    log_path = LOG_DIR / f"government_{timestamp_for_filename()}.log"

    try:
        with single_instance_lock(LOCK_PATH):
            append_log("AUTO_RUNNER START", log_path)
            print(f"📝 로그: {log_path.relative_to(BASE_DIR)}")

            if not args.work_only:
                print("\n=== 1. 기업마당 목록 수집 ===")
                collect_command = [
                    sys.executable,
                    "-m",
                    "plugins.government.list_collector",
                    args.list_url,
                    "--max-items",
                    str(max(0, args.discover)),
                ]

                collect_result = run_command(
                    collect_command,
                    log_path,
                )

                if collect_result != 0:
                    print("❌ 목록 수집 실패")
                    append_log(
                        f"AUTO_RUNNER END result=collect_failed "
                        f"code={collect_result}",
                        log_path,
                    )
                    return collect_result

            if args.collect_only:
                print_queue_summary()
                append_log(
                    "AUTO_RUNNER END result=collect_only_success",
                    log_path,
                )
                return 0

            print("\n=== 2. Queue Worker 실행 ===")
            worker_command = [
                sys.executable,
                "-m",
                "plugins.government.queue_worker",
                "--limit",
                str(max(0, args.process)),
                "--delay",
                str(max(0.0, args.delay)),
                "--max-attempts",
                str(max(1, args.max_attempts)),
                "--push" if args.push else "--no-push",
            ]

            worker_result = run_command(
                worker_command,
                log_path,
            )

            print_queue_summary()

            if worker_result == 0:
                print("\n✅ Atlas 정부지원사업 자동 실행 완료")
                append_log(
                    "AUTO_RUNNER END result=success",
                    log_path,
                )
                return 0

            if worker_result == 2:
                print(
                    "\n⚠️ 일부 공고가 실패하거나 재시도 상태입니다."
                )
                append_log(
                    "AUTO_RUNNER END result=partial_failure",
                    log_path,
                )
                return 2

            print(
                f"\n❌ Queue Worker 실행 실패: {worker_result}"
            )
            append_log(
                f"AUTO_RUNNER END result=worker_failed "
                f"code={worker_result}",
                log_path,
            )
            return worker_result

    except RuntimeError as exc:
        print(f"ℹ️ {exc}")
        return 3
    except KeyboardInterrupt:
        print("\n⚠️ 사용자 중단")
        append_log(
            "AUTO_RUNNER END result=interrupted",
            log_path,
        )
        return 130
    except Exception as exc:
        print(f"❌ Auto Runner 오류: {exc}", file=sys.stderr)
        append_log(
            f"AUTO_RUNNER END result=exception error={exc}",
            log_path,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
