from __future__ import annotations

from atlas.verify.models import VerifyResult, VerifyStatus


def print_report(results: list[VerifyResult]) -> None:
    print("🧪 Atlas Verify")

    passed = 0

    for result in results:
        icon = "✅" if result.status == VerifyStatus.PASS else "❌"
        print(f"  {icon} {result.name}: {result.message}")

        if result.detail and result.status == VerifyStatus.FAIL:
            print(f"     └─ {result.detail}")

        if result.status == VerifyStatus.PASS:
            passed += 1

    total = len(results)
    print(f"\n{passed} / {total} PASS")

    if passed == total:
        print("🟢 VERIFIED")
    else:
        print("🔴 VERIFICATION FAILED")
