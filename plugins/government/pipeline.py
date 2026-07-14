#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Atlas Government Pipeline v0.1

입력:
    정부지원사업 상세 URL

처리:
    1. Collector로 원본 HTML 저장
    2. Normalizer로 표준 JSON 생성
    3. AutoBlogger Atlas로 블로그 글 생성 및 사이트 빌드
    4. 선택적으로 GitHub push

사용:
    python plugins/government/pipeline.py "상세공고URL" --no-push

기본값은 안전을 위해 --no-push 동작이다.
실제 배포하려면 --push를 명시한다.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import asdict
from pathlib import Path

from plugins.government.collector import collect
from plugins.government.normalizer import normalize
from plugins.government.ai_tagger import tag_opportunity
from plugins.government.knowledge_store import store_knowledge


BASE_DIR = Path(__file__).resolve().parents[2]
BLOGGER_CANDIDATES = (
    BASE_DIR / "autoblogger_atlas_v0.2.py",
    BASE_DIR / "autoblogger_atlas_v0.1.py",
    BASE_DIR / "autoblogger.py",
)


def find_blogger() -> Path:
    for path in BLOGGER_CANDIDATES:
        if path.exists():
            return path

    names = ", ".join(path.name for path in BLOGGER_CANDIDATES)
    raise FileNotFoundError(
        f"AutoBlogger 실행 파일을 찾지 못했습니다. 다음 중 하나가 필요합니다: {names}"
    )


def metadata_path_for(source: str, source_id: str) -> Path:
    return (
        BASE_DIR
        / "data"
        / "government"
        / "raw"
        / f"{source}_{source_id}.json"
    )


def is_already_published(source: str, source_id: str) -> bool:
    """기존 posts/data.json에서 동일한 정부지원사업 발행 여부를 확인한다."""
    posts_path = BASE_DIR / "posts" / "data.json"

    if not posts_path.exists():
        return False

    try:
        posts = json.loads(posts_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False

    return any(
        post.get("source") == source
        and post.get("source_id") == source_id
        for post in posts
    )


def run_publisher(blogger_path: Path, normalized_path: Path, push: bool) -> None:
    command = [
        sys.executable,
        str(blogger_path),
        "--grant-json",
        str(normalized_path),
    ]

    if not push:
        command.append("--no-push")

    print("🚀 AutoBlogger 실행:")
    print(" ".join(command))

    subprocess.run(
        command,
        cwd=BASE_DIR,
        check=True,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="정부지원사업 URL을 블로그 글로 자동 발행하는 Atlas 파이프라인"
    )
    parser.add_argument(
        "url",
        help="기업마당 등 정부지원사업 상세 페이지 URL",
    )

    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--push",
        action="store_true",
        help="사이트 생성 후 GitHub에 실제 push",
    )
    group.add_argument(
        "--no-push",
        action="store_true",
        help="GitHub push 생략. 기본 동작",
    )

    return parser


def main() -> int:
    args = build_parser().parse_args()

    try:
        print("1/3 📡 공고 수집")
        document = collect(args.url)

        meta_path = metadata_path_for(
            document.source,
            document.source_id,
        )

        print("\n2/3 🧹 공고 표준화")
        opportunity = normalize(meta_path)

        normalized_dir = BASE_DIR / "data" / "government" / "normalized"
        normalized_dir.mkdir(parents=True, exist_ok=True)

        normalized_path = (
            normalized_dir
            / f"{opportunity.source}_{opportunity.source_id}.json"
        )

        normalized_path.write_text(
            json.dumps(
                asdict(opportunity),
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        print(f"📌 제목: {opportunity.title}")
        print(f"🏢 수행기관: {opportunity.organization}")
        print(f"📅 마감일: {opportunity.application_deadline}")
        print(f"💾 표준 JSON: {normalized_path.relative_to(BASE_DIR)}")

        knowledge_status, knowledge_path, knowledge_version = store_knowledge(
            normalized_path
        )
        if knowledge_status == "stored":
            print(
                f"📚 Knowledge 저장: "
                f"{knowledge_path.relative_to(BASE_DIR)} "
                f"(v{knowledge_version:04d})"
            )
        else:
            print(f"📚 Knowledge 변경 없음: v{knowledge_version:04d}")

        print("\n🧠 AI Tagger")
        try:
            tag_output, tag_path, tag_knowledge_path = tag_opportunity(
                normalized_path
            )
            score = tag_output.get("enrichment", {}).get(
                "recommendation_score", 0
            )
            print(f"🏷️ 태그 저장: {tag_path.relative_to(BASE_DIR)}")
            print(f"⭐ 추천도: {score}점")
        except Exception as exc:
            print(f"⚠️ AI Tagger 실패(계속 진행): {exc}")

        if is_already_published(
            opportunity.source,
            opportunity.source_id,
        ):
            print("\nℹ️ 이미 발행된 정부지원사업입니다.")
            print("⏭️ Gemini 호출과 사이트 빌드를 모두 건너뜁니다.")
            return 0

        print("\n3/3 ✍️ 블로그 생성 및 사이트 빌드")
        blogger_path = find_blogger()
        run_publisher(
            blogger_path=blogger_path,
            normalized_path=normalized_path,
            push=args.push,
        )

        print("\n✅ Atlas 정부지원사업 파이프라인 완료")
        if args.push:
            print("🌐 GitHub 배포까지 실행했습니다.")
        else:
            print("🧪 테스트 모드입니다. GitHub push는 실행하지 않았습니다.")

        return 0

    except subprocess.CalledProcessError as exc:
        print(
            f"❌ 하위 프로그램 실행 실패: 종료코드 {exc.returncode}",
            file=sys.stderr,
        )
    except FileNotFoundError as exc:
        print(f"❌ 파일 오류: {exc}", file=sys.stderr)
    except Exception as exc:
        print(f"❌ 파이프라인 오류: {exc}", file=sys.stderr)

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
