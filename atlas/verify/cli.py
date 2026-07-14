from __future__ import annotations

import argparse
from pathlib import Path

from atlas.verify.report import print_report
from atlas.verify.runner import exit_code, run_verification


BASE_DIR = Path(__file__).resolve().parents[2]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Atlas 핵심 흐름 검증"
    )
    parser.add_argument(
        "--base-dir",
        default=str(BASE_DIR),
    )
    args = parser.parse_args()

    base_dir = Path(args.base_dir).expanduser().resolve()
    results = run_verification(base_dir)
    print_report(results)

    return exit_code(results)


if __name__ == "__main__":
    raise SystemExit(main())
