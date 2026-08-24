#!/usr/bin/env python3
"""자동블로그/오토포스트 헬스체크 — 문제가 있을 때만 ntfy로 폰 알림.

cron으로 하루 1회(밤) 실행한다. 정상이면 조용하고, 문제가 있을 때만 푸시한다.
점검 항목:
  1) 블로그 새 글 신선도  — 일정 시간 넘게 새 글이 없으면 (cron/생성/푸시 어딘가 끊김)
  2) Gemini API 접근성    — 키 만료/쿼터 소진 등 (자동블로그·오토포스트 Pro 공통 원인)

.env(같은 폴더)에서 읽는 값:
  NTFY_TOPIC=zionlabs-alert-xxxx    (필수 — 폰 ntfy 앱에서 이 토픽을 구독)
  NTFY_URL=https://ntfy.sh          (선택, 기본 ntfy.sh)
  HEALTH_STALE_HOURS=26             (선택, 이 시간 넘게 새 글 없으면 경고)
  GEMINI_API_KEY=...                (Gemini 접근 점검용)

사용:
  python monitor.py           # 점검(문제가 있으면 알림)
  python monitor.py --test    # 알림 채널이 살아있는지 테스트 푸시 1건
"""
import os
import re
import sys
import glob
import json
import datetime
import urllib.request
import urllib.error

BASE = os.path.dirname(os.path.abspath(__file__))


def load_env():
    """저장소 루트의 .env를 읽어 환경변수로 등록한다(이미 있으면 유지)."""
    path = os.path.join(BASE, ".env")
    if not os.path.exists(path):
        return
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, val = line.split("=", 1)
            os.environ.setdefault(key.strip(), val.strip())


def notify(title, message, priority=4, tags=None):
    """ntfy로 푸시 알림을 보낸다. 성공 시 True."""
    topic = os.environ.get("NTFY_TOPIC", "").strip()
    if not topic:
        print("⚠️ NTFY_TOPIC 미설정 — 알림을 보낼 수 없습니다(.env에 추가하세요).")
        return False
    base = os.environ.get("NTFY_URL", "https://ntfy.sh").rstrip("/")
    body = json.dumps({
        "topic": topic,
        "title": title,
        "message": message,
        "priority": priority,      # 1(min) ~ 5(max)
        "tags": tags or ["warning"],
    }).encode("utf-8")
    req = urllib.request.Request(base + "/", data=body,
                                 headers={"Content-Type": "application/json"})
    try:
        urllib.request.urlopen(req, timeout=15)
        print("📣 알림 전송:", title)
        return True
    except Exception as e:
        print("❌ 알림 전송 실패:", e)
        return False


def newest_post_dt():
    """posts 폴더의 파일명(post_YYYYMMDD_HHMMSS.html)에서 가장 최근 발행 시각을 구한다.
    파일 mtime은 git clone/pull로 바뀌므로 파일명 타임스탬프를 쓴다."""
    latest = None
    for f in glob.glob(os.path.join(BASE, "posts", "post_*.html")):
        m = re.search(r"post_(\d{8})_(\d{6})", os.path.basename(f))
        if not m:
            continue
        try:
            dt = datetime.datetime.strptime(m.group(1) + m.group(2), "%Y%m%d%H%M%S")
        except ValueError:
            continue
        if latest is None or dt > latest:
            latest = dt
    return latest


def check_blog_freshness():
    """최근 글이 너무 오래됐으면 문제 메시지 반환, 정상이면 None."""
    stale_h = float(os.environ.get("HEALTH_STALE_HOURS", "26"))
    latest = newest_post_dt()
    if latest is None:
        return "블로그 글을 하나도 찾지 못했습니다(posts 폴더 확인 필요)."
    age_h = (datetime.datetime.now() - latest).total_seconds() / 3600
    if age_h > stale_h:
        return (f"최근 {age_h:.0f}시간 동안 새 글이 발행되지 않았습니다 "
                f"(마지막: {latest:%Y-%m-%d %H:%M}). cron/생성/푸시 점검이 필요합니다.")
    return None


def check_gemini():
    """Gemini API 키/접근이 살아있는지 확인. 문제면 메시지, 정상이면 None."""
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not key:
        return "GEMINI_API_KEY가 설정돼 있지 않습니다."
    url = "https://generativelanguage.googleapis.com/v1beta/models"
    req = urllib.request.Request(url, headers={"x-goog-api-key": key})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.loads(r.read().decode("utf-8"))
        usable = sum(1 for m in data.get("models", [])
                     if "generateContent" in m.get("supportedGenerationMethods", []))
        if usable == 0:
            return "Gemini에 사용 가능한 생성 모델이 0개입니다(키 권한/쿼터 확인)."
        return None
    except urllib.error.HTTPError as e:
        return f"Gemini API 접근 오류(HTTP {e.code}) — 키 만료/쿼터 소진 가능."
    except Exception as e:
        return f"Gemini API 연결 실패: {e}"


def main():
    load_env()

    if "--test" in sys.argv:
        ok = notify("✅ 헬스체크 테스트",
                    "알림이 정상 작동합니다. 이 메시지가 폰에 뜨면 설정 완료입니다.",
                    priority=3, tags=["white_check_mark"])
        sys.exit(0 if ok else 1)

    problems = []
    for check in (check_blog_freshness, check_gemini):
        try:
            msg = check()
        except Exception as e:
            msg = f"{check.__name__} 점검 중 오류: {e}"
        if msg:
            problems.append(msg)

    if problems:
        notify("🚨 자동블로그/오토포스트 점검 필요",
               "\n".join("• " + p for p in problems),
               priority=5, tags=["rotating_light"])
        print("문제 발견:\n" + "\n".join(problems))
        sys.exit(1)

    print("✅ 정상 — 알림 없음")
    sys.exit(0)


if __name__ == "__main__":
    main()
