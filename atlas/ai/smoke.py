from __future__ import annotations

import argparse
import sys

from atlas.ai.runtime import get_router

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Atlas AI Runtime 실호출 점검"
    )
    parser.add_argument(
        "prompt",
        nargs="?",
        default="한 단어로 OK라고 답하세요.",
    )
    parser.add_argument("--no-cache", action="store_true")
    args = parser.parse_args()

    try:
        response = get_router().generate(
            args.prompt,
            task="smoke",
            use_cache=not args.no_cache,
        )
        print("✅ AI Runtime 호출 성공")
        print(f"- Provider: {response.provider}")
        print(f"- Model: {response.model}")
        print(f"- Cached: {response.cached}")
        print(f"- Response: {response.text.strip()}")
        return 0
    except Exception as exc:
        print(f"❌ AI Runtime 호출 실패: {exc}", file=sys.stderr)
        return 1

if __name__ == "__main__":
    raise SystemExit(main())
