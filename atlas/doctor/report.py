from __future__ import annotations

from collections import defaultdict

from atlas.doctor.models import CheckResult, CheckStatus


STATUS_ICON = {
    CheckStatus.OK: "✅",
    CheckStatus.WARNING: "⚠️",
    CheckStatus.ERROR: "❌",
}


def print_report(results: list[CheckResult]) -> None:
    grouped: dict[str, list[CheckResult]] = defaultdict(list)

    for result in results:
        grouped[result.category].append(result)

    print("🩺 Atlas Doctor")

    for category, items in grouped.items():
        print(f"\n{category}")

        for result in items:
            icon = STATUS_ICON[result.status]
            print(f"  {icon} {result.name}: {result.message}")

            if result.detail and result.status != CheckStatus.OK:
                print(f"     └─ {result.detail}")

    errors = sum(
        result.status == CheckStatus.ERROR
        for result in results
    )
    warnings = sum(
        result.status == CheckStatus.WARNING
        for result in results
    )

    print("\nSummary")

    if errors:
        print(f"  🔴 ERROR — 오류 {errors}건, 경고 {warnings}건")
    elif warnings:
        print(f"  🟡 WARNING — 경고 {warnings}건")
    else:
        print("  🟢 HEALTHY")
