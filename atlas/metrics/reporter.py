from __future__ import annotations
import argparse
from pathlib import Path
from .recorder import MetricsRecorder

BASE_DIR = Path(__file__).resolve().parents[2]
DEFAULT_DB_PATH = BASE_DIR / "data" / "system" / "metrics.db"

def print_summary(summary: dict) -> None:
    print(f"📊 Atlas Metrics — 최근 {summary['hours']}시간")
    print(f"- AI 호출: {summary['calls']}회")
    print(f"- 성공률: {summary['success_rate']:.1f}%")
    print(f"- 오류: {summary['errors']}회")
    print(f"- 평균 응답시간: {summary['average_latency_ms']:.1f}ms")
    print(f"- 캐시 적중: {summary['cache_hits']}회 ({summary['cache_hit_rate']:.1f}%)")
    print(f"- 예상 비용: ${summary['estimated_cost_usd']:.6f}")
    if summary["providers"]:
        print("\nProvider")
        for item in summary["providers"]:
            calls = int(item["calls"] or 0)
            success = int(item["successes"] or 0)
            rate = success / calls * 100 if calls else 0
            latency = float(item["average_latency_ms"] or 0)
            print(f"- {item['provider']}: {calls}회, 성공 {rate:.1f}%, 평균 {latency:.1f}ms, 캐시 {int(item['cache_hits'] or 0)}회")

def main() -> int:
    parser = argparse.ArgumentParser(description="Atlas AI Metrics")
    parser.add_argument("--hours", type=int, default=24)
    parser.add_argument("--db", default=str(DEFAULT_DB_PATH))
    args = parser.parse_args()
    recorder = MetricsRecorder(Path(args.db).expanduser().resolve())
    print_summary(recorder.summary(args.hours))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
