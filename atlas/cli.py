#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Atlas Unified CLI v0.1

사용 예시
python -m atlas status
python -m atlas collect --discover 30
python -m atlas run --process 3 --no-push
python -m atlas search "서울 AI"
python -m atlas recommend --region 서울 --industry AI
python -m atlas test
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[1]


def run_module(module: str, args: list[str]) -> int:
    command = [sys.executable, "-m", module, *args]
    print("$ " + " ".join(command))

    return subprocess.run(
        command,
        cwd=BASE_DIR,
    ).returncode


def command_status(_args: argparse.Namespace) -> int:
    return run_module(
        "plugins.government.auto_runner",
        ["--status"],
    )


def command_health(_args: argparse.Namespace) -> int:
    return run_module(
        "plugins.government.scheduler",
        ["--health-only"],
    )


def command_collect(args: argparse.Namespace) -> int:
    command = [
        "--discover",
        str(args.discover),
        "--collect-only",
        "--no-push",
    ]

    if args.list_url:
        command.extend(["--list-url", args.list_url])

    return run_module(
        "plugins.government.auto_runner",
        command,
    )


def command_run(args: argparse.Namespace) -> int:
    command = [
        "--discover",
        str(args.discover),
        "--process",
        str(args.process),
        "--delay",
        str(args.delay),
        "--push" if args.push else "--no-push",
    ]

    if args.list_url:
        command.extend(["--list-url", args.list_url])

    return run_module(
        "plugins.government.auto_runner",
        command,
    )


def command_search(args: argparse.Namespace) -> int:
    command = [
        "search",
        args.query,
        "--limit",
        str(args.limit),
    ]

    return run_module(
        "plugins.government.search_index",
        command,
    )


def command_index(_args: argparse.Namespace) -> int:
    return run_module(
        "plugins.government.search_index",
        ["build"],
    )


def command_recommend(args: argparse.Namespace) -> int:
    command: list[str] = [
        "--limit",
        str(args.limit),
    ]

    optional = (
        ("--region", args.region),
        ("--industry", args.industry),
        ("--target", args.target),
        ("--technology", args.technology),
        ("--support-type", args.support_type),
        ("--keyword", args.keyword),
    )

    for flag, value in optional:
        if value:
            command.extend([flag, value])

    return run_module(
        "plugins.government.recommender",
        command,
    )


def command_ask(args: argparse.Namespace) -> int:
    return run_module(
        "atlas.assistant",
        [args.query, "--limit", str(args.limit)],
    )


def command_ai_smoke(args: argparse.Namespace) -> int:
    command = [args.prompt]
    if args.no_cache:
        command.append("--no-cache")
    return run_module("atlas.ai.smoke", command)


def command_metrics(args: argparse.Namespace) -> int:
    return run_module(
        "atlas.metrics.reporter",
        ["--hours", str(args.hours)],
    )


def command_test(_args: argparse.Namespace) -> int:
    command = [
        sys.executable,
        "-m",
        "unittest",
        "discover",
        "-s",
        "tests",
        "-v",
    ]

    print("$ " + " ".join(command))

    return subprocess.run(
        command,
        cwd=BASE_DIR,
    ).returncode


def command_schedule(args: argparse.Namespace) -> int:
    command = [
        "--interval-minutes",
        str(args.interval_minutes),
        "--discover",
        str(args.discover),
        "--process",
        str(args.process),
        "--delay",
        str(args.delay),
        "--push" if args.push else "--no-push",
    ]

    if args.run_once:
        command.append("--run-once")

    if args.list_url:
        command.extend(["--list-url", args.list_url])

    return run_module(
        "plugins.government.scheduler",
        command,
    )


def add_common_run_arguments(
    parser: argparse.ArgumentParser,
) -> None:
    parser.add_argument(
        "--discover",
        type=int,
        default=30,
        help="목록에서 확인할 최대 공고 수",
    )
    parser.add_argument(
        "--process",
        type=int,
        default=1,
        help="이번 실행에서 처리할 최대 공고 수",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=10.0,
        help="공고 처리 사이 대기 초",
    )
    parser.add_argument(
        "--list-url",
        default="",
        help="기업마당 목록 URL",
    )

    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--push",
        action="store_true",
        help="GitHub에 실제 배포",
    )
    group.add_argument(
        "--no-push",
        action="store_true",
        help="GitHub 배포 생략",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="atlas",
        description="Atlas 통합 명령줄 도구",
    )

    subparsers = parser.add_subparsers(
        dest="command",
        required=True,
    )

    status_parser = subparsers.add_parser(
        "status",
        help="Queue 상태 확인",
    )
    status_parser.set_defaults(func=command_status)

    health_parser = subparsers.add_parser(
        "health",
        help="Health Monitor 확인",
    )
    health_parser.set_defaults(func=command_health)

    collect_parser = subparsers.add_parser(
        "collect",
        help="기업마당 목록 수집만 실행",
    )
    collect_parser.add_argument(
        "--discover",
        type=int,
        default=30,
    )
    collect_parser.add_argument(
        "--list-url",
        default="",
    )
    collect_parser.set_defaults(func=command_collect)

    run_parser = subparsers.add_parser(
        "run",
        help="목록 수집과 Queue 처리 실행",
    )
    add_common_run_arguments(run_parser)
    run_parser.set_defaults(func=command_run)

    index_parser = subparsers.add_parser(
        "index",
        help="검색 인덱스 재생성",
    )
    index_parser.set_defaults(func=command_index)

    search_parser = subparsers.add_parser(
        "search",
        help="정부지원사업 검색",
    )
    search_parser.add_argument(
        "query",
        help="검색어",
    )
    search_parser.add_argument(
        "--limit",
        type=int,
        default=10,
    )
    search_parser.set_defaults(func=command_search)

    recommend_parser = subparsers.add_parser(
        "recommend",
        help="기업 프로필 기반 추천",
    )
    recommend_parser.add_argument("--region", default="")
    recommend_parser.add_argument("--industry", default="")
    recommend_parser.add_argument("--target", default="")
    recommend_parser.add_argument("--technology", default="")
    recommend_parser.add_argument("--support-type", default="")
    recommend_parser.add_argument("--keyword", default="")
    recommend_parser.add_argument("--limit", type=int, default=10)
    recommend_parser.set_defaults(func=command_recommend)

    ask_parser = subparsers.add_parser(
        "ask",
        help="자연어로 정부지원사업 추천 질문",
    )
    ask_parser.add_argument("query")
    ask_parser.add_argument("--limit", type=int, default=5)
    ask_parser.set_defaults(func=command_ask)

    ai_smoke_parser = subparsers.add_parser(
        "ai-smoke",
        help="AI Runtime 실호출 점검",
    )
    ai_smoke_parser.add_argument(
        "prompt",
        nargs="?",
        default="한 단어로 OK라고 답하세요.",
    )
    ai_smoke_parser.add_argument(
        "--no-cache",
        action="store_true",
    )
    ai_smoke_parser.set_defaults(func=command_ai_smoke)

    metrics_parser = subparsers.add_parser(
        "metrics",
        help="AI 호출 Metrics 확인",
    )
    metrics_parser.add_argument(
        "--hours",
        type=int,
        default=24,
    )
    metrics_parser.set_defaults(func=command_metrics)

    test_parser = subparsers.add_parser(
        "test",
        help="전체 자동 테스트 실행",
    )
    test_parser.set_defaults(func=command_test)

    schedule_parser = subparsers.add_parser(
        "schedule",
        help="Scheduler 실행",
    )
    add_common_run_arguments(schedule_parser)
    schedule_parser.add_argument(
        "--interval-minutes",
        type=int,
        default=180,
    )
    schedule_parser.add_argument(
        "--run-once",
        action="store_true",
    )
    schedule_parser.set_defaults(func=command_schedule)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    try:
        return int(args.func(args))
    except KeyboardInterrupt:
        print("\n⚠️ 사용자 중단")
        return 130
    except Exception as exc:
        print(f"❌ Atlas CLI 오류: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
