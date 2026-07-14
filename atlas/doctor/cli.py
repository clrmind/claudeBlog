from __future__ import annotations

import argparse
from pathlib import Path

from atlas.doctor.report import print_report
from atlas.doctor.runner import exit_code, run_checks


BASE_DIR = Path(__file__).resolve().parents[2]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Atlas 시스템 진단"
    )
    parser.add_argument(
        "--base-dir",
        default=str(BASE_DIR),
        help="Atlas 프로젝트 루트",
    )
    args = parser.parse_args()

    base_dir = Path(args.base_dir).expanduser().resolve()
    results = run_checks(base_dir)
    print_report(results)

    return exit_code(results)


if __name__ == "__main__":
    raise SystemExit(main())
