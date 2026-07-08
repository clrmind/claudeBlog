#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AutoBlogger v2 — 50대 타깃 실시간 트렌드 자동 블로그 발행기
============================================================
스마트폰(Termux)에서 스케줄러로 실행되어:
  1. 실시간 트렌드 키워드를 수집하고 (구글 트렌드 KR + signal.bz)
  2. Gemini가 그중 '50대가 가장 클릭할 키워드'를 선별한 뒤
  3. SEO 최적화된 칼럼을 생성하고 정적 사이트를 빌드하여
  4. GitHub 저장소(main)에 자동으로 커밋/푸시합니다.

사용법:
  python autoblogger.py                # 전체 파이프라인 실행
  python autoblogger.py --keyword 갱년기  # 키워드 직접 지정
  python autoblogger.py --render-only  # 글 생성 없이 사이트만 재빌드
  python autoblogger.py --no-push      # git 푸시 생략 (테스트용)

설정:
  - config.json      : 블로그 도메인, 애드센스 ID 등 (저장소에 포함)
  - .env             : GEMINI_API_KEY=... (절대 커밋 금지, .gitignore 처리됨)
"""

import argparse
import datetime
import html
import json
import os
import random
import re
import subprocess
import sys
import time

import requests

# ==========================================
# 경로 및 상수
# ==========================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")
ENV_PATH = os.path.join(BASE_DIR, ".env")
POSTS_DIR = os.path.join(BASE_DIR, "posts")
DATA_PATH = os.path.join(POSTS_DIR, "data.json")
HISTORY_PATH = os.path.join(BASE_DIR, "data", "keyword_history.json")

UA = ("Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0 Mobile Safari/537.36")

DEFAULT_CONFIG = {
    "blog_name": "ZionLabs Trend Insights",
    "blog_description": "50대가 꼭 알아야 할 건강·연금·재테크·생활 트렌드를 매일 분석하는 프리미엄 칼럼 채널",
    "blog_domain": "https://blog.zionlabs.org",
    "contact_email": "contact@zionlabs.org",
    "model_name": "gemini-2.5-flash",
    "adsense_client": "",
    "counter_namespace": "",
    "git_branch": "main",
    "posts_per_page": 9,
    "max_posts_per_day": 3
}

# 실시간 수집이 모두 실패했을 때 사용하는 50대 상시 인기 주제 (검색량/광고단가가 높은 주제 위주)
FALLBACK_KEYWORDS = [
    "국민연금 조기수령 조건과 감액", "주택연금 가입 조건과 월 수령액", "퇴직 후 건강보험 임의계속가입",
    "갱년기 증상과 극복 방법", "혈압 낮추는 생활 습관", "당뇨 초기 증상과 관리법",
    "임플란트 건강보험 적용 기준", "치매 초기 증상 자가진단", "오십견 증상과 치료",
    "노후 자산관리 포트폴리오", "개인연금 IRP 세액공제", "중장년 재취업 지원 제도",
    "기초연금 수급 자격", "상속세 절세 방법", "전원주택 귀촌 준비",
    "무릎 관절에 좋은 운동", "눈 건강 지키는 습관", "단백질 보충 식단",
]

IMAGE_CATEGORIES = ["health", "finance", "lifestyle", "food", "travel", "technology", "society", "nature"]

IMAGE_POOL = {
    "health": [
        "https://images.unsplash.com/photo-1506126613408-eca07ce68773?w=1200&auto=format&fit=crop",
        "https://images.unsplash.com/photo-1476480862126-209bfaa8edc8?w=1200&auto=format&fit=crop",
        "https://images.unsplash.com/photo-1490645935967-10de6ba17061?w=1200&auto=format&fit=crop",
    ],
    "finance": [
        "https://images.unsplash.com/photo-1554224155-6726b3ff858f?w=1200&auto=format&fit=crop",
        "https://images.unsplash.com/photo-1579621970563-ebec7560ff3e?w=1200&auto=format&fit=crop",
        "https://images.unsplash.com/photo-1553729459-efe14ef6055d?w=1200&auto=format&fit=crop",
    ],
    "lifestyle": [
        "https://images.unsplash.com/photo-1521737604893-d14cc237f11d?w=1200&auto=format&fit=crop",
        "https://images.unsplash.com/photo-1493663284031-b7e3aefcae8e?w=1200&auto=format&fit=crop",
    ],
    "food": [
        "https://images.unsplash.com/photo-1504674900247-0877df9cc836?w=1200&auto=format&fit=crop",
        "https://images.unsplash.com/photo-1498837167922-ddd27525d352?w=1200&auto=format&fit=crop",
    ],
    "travel": [
        "https://images.unsplash.com/photo-1507525428034-b723cf961d3e?w=1200&auto=format&fit=crop",
        "https://images.unsplash.com/photo-1476514525535-07fb3b4ae5f1?w=1200&auto=format&fit=crop",
    ],
    "technology": [
        "https://images.unsplash.com/photo-1518770660439-4636190af475?w=1200&auto=format&fit=crop",
        "https://images.unsplash.com/photo-1451187580459-43490279c0fa?w=1200&auto=format&fit=crop",
        "https://images.unsplash.com/photo-1526374965328-7f61d4dc18c5?w=1200&auto=format&fit=crop",
    ],
    "society": [
        "https://images.unsplash.com/photo-1477959858617-67f85cf4f1df?w=1200&auto=format&fit=crop",
        "https://images.unsplash.com/photo-1449824913935-59a10b8d2000?w=1200&auto=format&fit=crop",
    ],
    "nature": [
        "https://images.unsplash.com/photo-1441974231531-c6227db76b6e?w=1200&auto=format&fit=crop",
        "https://images.unsplash.com/photo-1470071459604-3b5ec3a7fe05?w=1200&auto=format&fit=crop",
    ],
}

# ==========================================
# 설정 / 환경변수 로딩
# ==========================================

def load_env_file():
    """저장소 루트의 .env 파일을 읽어 환경변수로 등록한다 (이미 있는 변수는 유지)."""
    if not os.path.exists(ENV_PATH):
        return
    with open(ENV_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key, value = key.strip(), value.strip().strip("'\"")
            if key and key not in os.environ:
                os.environ[key] = value


def load_config():
    cfg = dict(DEFAULT_CONFIG)
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                cfg.update(json.load(f))
        except Exception as e:
            print(f"⚠️ config.json 파싱 실패, 기본값 사용: {e}")
    return cfg


def get_api_key():
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not key:
        print("❌ GEMINI_API_KEY가 없습니다. .env 파일에 'GEMINI_API_KEY=...' 를 추가하세요.")
        sys.exit(1)
    return key


# ==========================================
# Gemini 호출 공통
# ==========================================

def call_gemini_json(prompt, api_key, model, max_retries=3, retry_delay=5):
    """Gemini에 JSON 응답을 요청하고 파싱된 dict를 반환한다. 실패 시 None."""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"responseMimeType": "application/json", "temperature": 0.8},
    }
    headers = {"Content-Type": "application/json", "x-goog-api-key": api_key}

    for attempt in range(1, max_retries + 1):
        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=60)
            if resp.status_code != 200:
                print(f"❌ Gemini API 오류 (HTTP {resp.status_code}) — 시도 {attempt}/{max_retries}")
                time.sleep(retry_delay * attempt)
                continue
            raw = resp.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
            raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw)
            return json.loads(raw)
        except Exception as e:
            print(f"⚠️ Gemini 호출 중 오류: {e} — 시도 {attempt}/{max_retries}")
            time.sleep(retry_delay * attempt)
    return None


# ==========================================
# 1단계: 실시간 트렌드 키워드 수집
# ==========================================

def fetch_google_trends_kr():
    """구글 트렌드 대한민국 실시간 급상승 검색어 RSS."""
    try:
        r = requests.get("https://trends.google.co.kr/trending/rss?geo=KR",
                         timeout=10, headers={"User-Agent": UA})
        r.raise_for_status()
        titles = re.findall(r"<title>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</title>", r.text)
        # 첫 번째 <title>은 피드 제목이므로 제외
        return [html.unescape(t).strip() for t in titles[1:] if t.strip()]
    except Exception as e:
        print(f"⚠️ 구글 트렌드 수집 실패: {e}")
        return []


def fetch_signal_keywords():
    """signal.bz 실시간 검색어 TOP10."""
    try:
        r = requests.get("https://api.signal.bz/news/realtime",
                         timeout=10, headers={"User-Agent": UA})
        r.raise_for_status()
        data = r.json()
        return [item.get("keyword", "").strip()
                for item in data.get("top10", []) if item.get("keyword")]
    except Exception as e:
        print(f"⚠️ signal.bz 수집 실패: {e}")
        return []


def fetch_trending_keywords():
    seen, merged = set(), []
    for kw in fetch_google_trends_kr() + fetch_signal_keywords():
        norm = kw.lower()
        if norm not in seen:
            seen.add(norm)
            merged.append(kw)
    print(f"📡 실시간 트렌드 후보 {len(merged)}개 수집 완료")
    return merged


# ==========================================
# 키워드 발행 이력 (중복 방지)
# ==========================================

def load_history():
    if os.path.exists(HISTORY_PATH):
        try:
            with open(HISTORY_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []


def save_history(history):
    os.makedirs(os.path.dirname(HISTORY_PATH), exist_ok=True)
    with open(HISTORY_PATH, "w", encoding="utf-8") as f:
        json.dump(history[-100:], f, ensure_ascii=False, indent=2)


def posts_today(history):
    today = datetime.date.today().isoformat()
    return sum(1 for h in history if h.get("date") == today)


# ==========================================
# 2단계: Gemini가 50대 타깃 키워드 선별
# ==========================================

def select_keyword_for_50s(candidates, history, api_key, model):
    recent = [h["keyword"] for h in history[-30:]]
    candidates_text = "\n".join(f"- {k}" for k in candidates[:30]) if candidates else "(수집 실패 — 직접 제안 필요)"
    recent_text = "\n".join(f"- {k}" for k in recent) if recent else "(없음)"

    prompt = (
        "너는 대한민국 50대 독자를 겨냥한 정보 블로그의 편집장이다.\n"
        "아래 '실시간 트렌드 후보' 중에서 50대 독자가 가장 많이 검색하고 클릭할 만한 키워드 1개를 골라라.\n\n"
        "★선정 기준 (우선순위 순):\n"
        "1. 건강/질병/의료 (갱년기, 관절, 혈압, 당뇨, 치매, 암 등)\n"
        "2. 연금/재테크/부동산/세금 (국민연금, 주택연금, 상속, 금리 등 — 광고 단가가 높은 분야)\n"
        "3. 생활 정보/정부 지원 제도 (지원금, 건강보험, 재취업 등)\n"
        "4. 50대 인지도가 높은 유명인·방송·사회 이슈\n\n"
        "★제외 기준:\n"
        f"- 최근 발행 이력에 이미 있는 키워드/주제:\n{recent_text}\n"
        "- 10~20대 위주의 게임/아이돌 이슈, 선정적/자극적 이슈\n\n"
        f"★실시간 트렌드 후보:\n{candidates_text}\n\n"
        "후보가 모두 부적합하거나 비어 있으면, 50대에게 유용하고 검색량이 많은 상시 인기 주제를 직접 1개 제안하라.\n\n"
        "★출력 형식: 반드시 아래 JSON 구조로만 출력하라.\n"
        "{\n"
        '  "keyword": "선정한 키워드",\n'
        '  "selection_reason": "50대 관점에서 이 키워드를 고른 이유 1~2문장",\n'
        f'  "category": "{" | ".join(IMAGE_CATEGORIES)} 중 하나"\n'
        "}"
    )

    result = call_gemini_json(prompt, api_key, model)
    if result and result.get("keyword"):
        return {
            "keyword": str(result["keyword"]).strip(),
            "reason": str(result.get("selection_reason", "")).strip(),
            "category": result.get("category") if result.get("category") in IMAGE_CATEGORIES else "society",
        }

    # Gemini 실패 시: 이력에 없는 상시 인기 주제 중 랜덤 선택
    pool = [k for k in FALLBACK_KEYWORDS if k not in recent] or FALLBACK_KEYWORDS
    kw = random.choice(pool)
    print(f"⚠️ 키워드 선별 실패 → 상시 인기 주제로 대체: {kw}")
    return {"keyword": kw, "reason": "50대 상시 관심 주제(자동 대체)", "category": "lifestyle"}


# ==========================================
# 3단계: 본문 생성
# ==========================================

def generate_blog_content(keyword, context, api_key, model):
    prompt = (
        "너는 대한민국 50대 독자를 위한 프리미엄 정보 칼럼을 기고하는 전문 칼럼니스트이자 SEO 전문가다.\n"
        f"핵심 키워드: '{keyword}'\n"
        f"참고 맥락: '{context}'\n\n"
        "★독자 페르소나: 50대 남녀. 건강, 노후 준비, 자산 관리, 가족에 관심이 많고,\n"
        "  신뢰할 수 있는 구체적 정보(수치, 제도, 절차)를 원한다. 어려운 용어는 풀어서 설명해야 한다.\n\n"
        "★필수 지시사항:\n"
        "1. 말투: 전문 칼럼니스트의 객관적이고 무게감 있는 문어체('~다', '~에 주목할 필요가 있다').\n"
        "2. 분량: 본문 공백 제외 최소 2,000자 이상. 실질적으로 도움이 되는 구체적 정보 위주로 작성.\n"
        "3. 구조: <h2> 소제목 4개 이상으로 단락 구분. 마지막에는 '자주 묻는 질문' <h2> 섹션을 넣고\n"
        "   Q&A 3개를 <h3>Q. 질문</h3><p>답변</p> 형식으로 작성.\n"
        "4. 강조: 핵심 문구 2~3곳만 <strong> 태그로 마킹. 목록이 어울리는 곳은 <ul><li> 사용.\n"
        "5. 정확성: 확실하지 않은 수치나 사실은 단정하지 말고 '~로 알려져 있다', '기관 확인이 필요하다'로 표현.\n"
        "6. 제목: 검색 클릭을 부르되 낚시성이 아닌 제목. 핵심 키워드를 포함하고 60자 이내.\n\n"
        "★출력 형식: 반드시 아래 JSON 구조로만 출력하라.\n"
        "{\n"
        '  "title": "SEO 최적화된 블로그 제목 (키워드 포함, 60자 이내)",\n'
        '  "meta_description": "검색 결과에 노출될 요약문 (키워드 포함, 150자 이내)",\n'
        '  "trend_reason": "이 키워드가 현재 왜 중요한지 요약 2줄",\n'
        '  "tags": ["관련태그1", "관련태그2", "관련태그3"],\n'
        f'  "image_category": "{" | ".join(IMAGE_CATEGORIES)} 중 하나",\n'
        '  "content": "<h2>소제목</h2><p>본문... <strong>강조</strong></p>"\n'
        "}"
    )
    print(f"🤖 Gemini({model})가 '{keyword}' 칼럼을 집필 중입니다...")
    result = call_gemini_json(prompt, api_key, model)
    if not result:
        return None
    for field in ("title", "content"):
        if not result.get(field):
            print(f"❌ 응답에 '{field}' 필드가 없습니다.")
            return None
    return result


def pick_image(category):
    pool = IMAGE_POOL.get(category) or IMAGE_POOL["society"]
    return random.choice(pool)


# ==========================================
# 4단계: 정적 사이트 렌더링
# ==========================================

CSS_STYLE = """
<style>
body { font-family: 'Apple SD Gothic Neo', 'Malgun Gothic', sans-serif; line-height: 1.75; color: #333; margin: 0; padding: 0; background-color: #f9f9fb; }
.container { max-width: 900px; margin: 0 auto; padding: 4px 20px 80px 20px; box-sizing: border-box; }
header { background: #fff; border-bottom: 1px solid #edf2f7; padding: 20px; display: flex; justify-content: space-between; align-items: center; position: sticky; top: 0; z-index: 100; }
header a.logo { font-size: 22px; font-weight: 900; color: #1a1a1a; text-decoration: none; letter-spacing: -0.5px; }
.nav-links a { margin-left: 20px; color: #666; text-decoration: none; font-size: 14px; font-weight: 500; }
.nav-links a:hover { color: #00c73c; }
.main-content { display: grid; grid-template-columns: 1fr; gap: 25px; margin-top: 20px; }
.post-card { background: #fff; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 15px rgba(0,0,0,0.03); border: 1px solid #edf2f7; transition: transform 0.2s; }
.post-card:hover { transform: translateY(-3px); }
.post-card a { display: flex; text-decoration: none; color: inherit; justify-content: space-between; }
.post-card-info { padding: 25px; flex: 1; display: flex; flex-direction: column; justify-content: center; }
.post-card-info h2 { margin: 0 0 10px 0; font-size: 20px; font-weight: 700; color: #1a1a1a; line-height: 1.4; }
.post-card-info p { margin: 0 0 15px 0; color: #555; font-size: 14px; line-height: 1.6; }
.post-card-img { width: 180px; height: 180px; object-fit: cover; background-color: #f4f6f8; }
.featured-img-container { width: 100%; margin-bottom: 30px; text-align: center; }
.featured-img { width: 100%; max-height: 450px; object-fit: cover; border-radius: 12px; }
.trend-reason-box { background-color: #f1f3f9; border-left: 4px solid #4a90e2; padding: 15px 20px; border-radius: 0 8px 8px 0; font-size: 15px; color: #4a5568; margin-bottom: 30px; line-height: 1.6; }
.article-body { font-size: 17px; color: #2d3748; line-height: 1.85; letter-spacing: -0.2px; }
.article-body h2 { font-size: 23px; color: #1a1a1a; margin-top: 45px; margin-bottom: 15px; border-bottom: 2px solid #edf2f7; padding-bottom: 8px; }
.article-body h3 { font-size: 18px; color: #1a1a1a; margin-top: 30px; margin-bottom: 10px; }
.article-body p { margin-bottom: 25px; text-align: justify; }
.article-body ul { margin-bottom: 25px; padding-left: 22px; }
.article-body li { margin-bottom: 8px; }
.article-body strong { color: #00a835; background: rgba(0, 199, 60, 0.06); padding: 1px 4px; border-radius: 4px; }
.tags { margin-top: 30px; }
.tags span { display: inline-block; background: #eef2f7; color: #556; border-radius: 15px; padding: 5px 14px; font-size: 13px; margin: 0 6px 8px 0; }
.ad-slot { margin: 35px 0; text-align: center; }
.recommend-section { margin-top: 60px; border-top: 1px solid #edf2f7; padding-top: 40px; }
.recommend-section h3 { font-size: 18px; color: #1a1a1a; margin-bottom: 20px; }
.recommend-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 20px; }
.recommend-card { background: #fff; border: 1px solid #edf2f7; border-radius: 8px; overflow: hidden; text-decoration: none; color: inherit; transition: border 0.2s; }
.recommend-card:hover { border-color: #00c73c; }
.recommend-thumb { width: 100%; height: 140px; object-fit: cover; }
.recommend-title { padding: 12px; margin: 0; font-size: 14px; font-weight: 600; color: #333; line-height: 1.4; }
footer { background: #fff; border-top: 1px solid #edf2f7; padding: 40px 20px; margin-top: 100px; text-align: center; font-size: 13px; color: #777; }
.footer-info { margin-bottom: 15px; line-height: 1.6; }
.footer-links a { margin: 0 10px; color: #666; text-decoration: none; }
.footer-links a:hover { color: #00c73c; }
.search-container { margin-bottom: 10px; margin-top: 25px; width: 100%; position: relative; }
.search-input { width: 100%; padding: 14px 20px; font-size: 15px; border: 1px solid #e1e2e6; border-radius: 30px; box-sizing: border-box; outline: none; transition: border 0.2s; background-color: #fff; box-shadow: 0 2px 8px rgba(0,0,0,0.02); }
.search-input:focus { border-color: #00c73c; }
.pagination { display: flex; justify-content: center; gap: 8px; margin-top: 50px; }
.pagination a, .pagination span { padding: 8px 16px; border: 1px solid #e1e2e6; border-radius: 6px; text-decoration: none; color: #555; font-size: 14px; background: #fff; }
.pagination a:hover { border-color: #00c73c; color: #00c73c; }
.pagination .current { background-color: #2ed573; color: white; border-color: #2ed573; font-weight: bold; }
@media (max-width: 640px) {
.post-card a { flex-direction: column-reverse; }
.post-card-img { width: 100%; height: 200px; }
.recommend-grid { grid-template-columns: 1fr; }
}
</style>
"""

SEARCH_BOX_HTML = """
<div class='search-container'>
<input type='text' id='blogSearch' class='search-input' placeholder='🔍 제목 또는 본문 검색...' onkeyup='runBlogSearch()'>
</div>
<script>
function runBlogSearch() {
  var input = document.getElementById('blogSearch').value.toLowerCase();
  var cards = document.getElementsByClassName('post-card');
  var pagination = document.getElementById('mainPagination');
  if (pagination) pagination.style.display = input.length > 0 ? 'none' : 'flex';
  for (var i = 0; i < cards.length; i++) {
    var title = cards[i].querySelector('h2').innerText.toLowerCase();
    var desc = cards[i].querySelector('p').innerText.toLowerCase();
    if (title.indexOf(input) > -1 || desc.indexOf(input) > -1) { cards[i].style.display = ''; }
    else { cards[i].style.display = 'none'; }
  }
}
</script>
"""


def strip_tags(text):
    return re.sub(r"<[^>]+>", " ", text or "").strip()


def adsense_head(cfg):
    client = cfg.get("adsense_client", "").strip()
    if not client:
        return ""
    return (f'<script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js'
            f'?client={client}" crossorigin="anonymous"></script>')


def analytics_script(cfg):
    ns = cfg.get("counter_namespace", "").strip()
    if not ns:
        return ""
    return (
        "<script>\n"
        "window.addEventListener('DOMContentLoaded', function() {\n"
        "  setTimeout(function() {\n"
        "    try {\n"
        "      var p = (location.pathname === '/' || location.pathname === '/index.html')\n"
        "        ? 'main_root' : location.pathname.replace(/[^a-zA-Z0-9]/g, '_');\n"
        "      var xhr = new XMLHttpRequest();\n"
        "      xhr.timeout = 2000;\n"
        "      xhr.open('GET', 'https://api.counterapi.dev/v1/" + ns + "/' + p + '/up', true);\n"
        "      xhr.send();\n"
        "    } catch (e) { }\n"
        "  }, 500);\n"
        "});\n"
        "</script>"
    )


def page_shell(cfg, title, meta_description, canonical, body_html, extra_head=""):
    name = html.escape(cfg["blog_name"])
    header_html = (
        f"<header><a class='logo' href='/'>{name}</a>"
        "<div class='nav-links'><a href='/about.html'>About</a>"
        "<a href='/privacy.html'>개인정보처리방침</a></div></header>"
    )
    footer_html = (
        f"<footer><div class='footer-info'><strong>{name}</strong><br>"
        f"문의: {html.escape(cfg['contact_email'])}</div>"
        "<div class='footer-links'><a href='/about.html'>About</a>"
        "<a href='/privacy.html'>Privacy Policy</a>"
        "<a href='/rss.xml'>RSS</a></div></footer>"
    )
    return (
        "<!DOCTYPE html><html lang='ko'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width, initial-scale=1.0'>"
        f"<title>{html.escape(title)}</title>"
        f"<meta name='description' content='{html.escape(meta_description)}'>"
        f"<link rel='canonical' href='{canonical}'>"
        f"<link rel='alternate' type='application/rss+xml' title='{name}' href='/rss.xml'>"
        f"{adsense_head(cfg)}{extra_head}{CSS_STYLE}</head><body>"
        f"{header_html}{body_html}{footer_html}{analytics_script(cfg)}</body></html>"
    )


def og_and_jsonld(cfg, post):
    url = f"{cfg['blog_domain']}/posts/{post['filename']}.html"
    desc = post.get("meta_description") or strip_tags(post["content"])[:150]
    og = (
        f"<meta property='og:type' content='article'>"
        f"<meta property='og:title' content='{html.escape(post['title'])}'>"
        f"<meta property='og:description' content='{html.escape(desc)}'>"
        f"<meta property='og:image' content='{post['image']}'>"
        f"<meta property='og:url' content='{url}'>"
    )
    jsonld = json.dumps({
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": post["title"],
        "description": desc,
        "image": post["image"],
        "datePublished": post["date"],
        "mainEntityOfPage": url,
        "publisher": {"@type": "Organization", "name": cfg["blog_name"]},
        "author": {"@type": "Organization", "name": cfg["blog_name"]},
    }, ensure_ascii=False)
    return og + f"<script type='application/ld+json'>{jsonld}</script>"


def generate_required_pages(cfg):
    """about / privacy 페이지가 없을 때만 생성 (직접 수정한 내용은 보존)."""
    name = html.escape(cfg["blog_name"])
    if not os.path.exists(os.path.join(BASE_DIR, "about.html")):
        body = (
            "<div class='container' style='margin-top:40px;'><h1>소개</h1>"
            f"<p><strong>{name}</strong>는 50대 독자를 위해 건강, 연금, 재테크, 생활 정보 등 "
            "꼭 필요한 트렌드를 매일 분석하여 전달하는 정보 칼럼 채널입니다.</p>"
            "<p>모든 콘텐츠는 공개된 자료와 시장 동향을 바탕으로 작성되며, "
            "의료·금융 관련 결정은 반드시 전문가와 상담하시기 바랍니다.</p>"
            f"<p>제휴 및 문의: {html.escape(cfg['contact_email'])}</p></div>"
        )
        page = page_shell(cfg, f"소개 - {cfg['blog_name']}", cfg["blog_description"],
                          f"{cfg['blog_domain']}/about.html", body)
        with open(os.path.join(BASE_DIR, "about.html"), "w", encoding="utf-8") as f:
            f.write(page)

    if not os.path.exists(os.path.join(BASE_DIR, "privacy.html")):
        body = (
            "<div class='container' style='margin-top:40px;'><h1>개인정보처리방침</h1>"
            f"<p>{name}(이하 '본 사이트')는 방문자의 개인정보를 소중히 여기며 관련 법령을 준수합니다.</p>"
            "<h2>1. 수집하는 정보</h2><p>본 사이트는 회원가입 없이 운영되며, 별도의 개인정보를 직접 수집하지 않습니다. "
            "다만 서비스 개선과 광고 게재를 위해 쿠키가 사용될 수 있습니다.</p>"
            "<h2>2. 쿠키 및 광고</h2><p>본 사이트는 Google AdSense를 통해 광고를 게재합니다. "
            "Google을 포함한 제3자 광고 사업자는 쿠키(DART 쿠키 등)를 사용하여 사용자의 이전 방문 기록을 바탕으로 "
            "맞춤형 광고를 제공할 수 있습니다. 사용자는 "
            "<a href='https://adssettings.google.com'>Google 광고 설정</a>에서 맞춤 광고를 비활성화할 수 있습니다.</p>"
            "<h2>3. 문의</h2>"
            f"<p>개인정보 관련 문의: {html.escape(cfg['contact_email'])}</p></div>"
        )
        page = page_shell(cfg, f"개인정보처리방침 - {cfg['blog_name']}", "개인정보처리방침 및 쿠키 안내",
                          f"{cfg['blog_domain']}/privacy.html", body)
        with open(os.path.join(BASE_DIR, "privacy.html"), "w", encoding="utf-8") as f:
            f.write(page)


def generate_sitemap(cfg, posts_data):
    today = datetime.date.today().isoformat()
    domain = cfg["blog_domain"]
    xml = ['<?xml version="1.0" encoding="UTF-8"?>',
           '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
           f'<url><loc>{domain}/</loc><lastmod>{today}</lastmod><changefreq>daily</changefreq><priority>1.0</priority></url>',
           f'<url><loc>{domain}/about.html</loc><changefreq>monthly</changefreq><priority>0.5</priority></url>',
           f'<url><loc>{domain}/privacy.html</loc><changefreq>monthly</changefreq><priority>0.3</priority></url>']
    for p in posts_data:
        xml.append(f'<url><loc>{domain}/posts/{p["filename"]}.html</loc>'
                   f'<lastmod>{p["date"]}</lastmod><changefreq>weekly</changefreq><priority>0.8</priority></url>')
    xml.append('</urlset>')
    with open(os.path.join(BASE_DIR, "sitemap.xml"), "w", encoding="utf-8") as f:
        f.write("\n".join(xml))


def generate_rss(cfg, posts_data):
    domain = cfg["blog_domain"]
    items = []
    for p in posts_data[:20]:
        desc = p.get("meta_description") or strip_tags(p["content"])[:150]
        items.append(
            "<item>"
            f"<title>{html.escape(p['title'])}</title>"
            f"<link>{domain}/posts/{p['filename']}.html</link>"
            f"<guid>{domain}/posts/{p['filename']}.html</guid>"
            f"<pubDate>{p['date']}</pubDate>"
            f"<description>{html.escape(desc)}</description>"
            "</item>"
        )
    rss = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<rss version="2.0"><channel>'
        f"<title>{html.escape(cfg['blog_name'])}</title>"
        f"<link>{domain}/</link>"
        f"<description>{html.escape(cfg['blog_description'])}</description>"
        "<language>ko</language>"
        + "".join(items) + "</channel></rss>"
    )
    with open(os.path.join(BASE_DIR, "rss.xml"), "w", encoding="utf-8") as f:
        f.write(rss)


def generate_robots_and_ads(cfg):
    with open(os.path.join(BASE_DIR, "robots.txt"), "w", encoding="utf-8") as f:
        f.write(f"User-agent: *\nAllow: /\nSitemap: {cfg['blog_domain']}/sitemap.xml\n")
    client = cfg.get("adsense_client", "").strip()
    if client:
        pub_id = client.replace("ca-", "")
        with open(os.path.join(BASE_DIR, "ads.txt"), "w", encoding="utf-8") as f:
            f.write(f"google.com, {pub_id}, DIRECT, f08c47fec0942fa0\n")


def write_admin_dashboard(cfg, posts_data):
    ns = cfg.get("counter_namespace", "").strip()
    if not ns:
        return
    admin_style = (
        "<style>.admin-card { background: #fff; padding: 25px; border-radius: 12px; "
        "box-shadow: 0 4px 15px rgba(0,0,0,0.05); margin-bottom: 25px; }\n"
        ".stats-table { width: 100%; border-collapse: collapse; margin-top: 15px; }\n"
        ".stats-table th, .stats-table td { padding: 12px; border-bottom: 1px solid #edf2f7; text-align: left; font-size: 14px; }\n"
        ".stats-table th { background-color: #f7fafc; color: #4a5568; font-weight: 600; }\n"
        ".badge { background: #e2fbf0; color: #2ed573; padding: 4px 8px; border-radius: 4px; font-size: 12px; font-weight: bold; }</style>"
    )
    filenames_js = json.dumps([p["filename"] for p in posts_data])
    script = (
        "<script>\n"
        f"var NS = '{ns}';\n"
        f"var posts = {filenames_js};\n"
        "var tb = document.getElementById('statsTableBody');\n"
        "var seq = 0;\n"
        "function addRow(label, key) {\n"
        "  var id = 'cnt_' + (seq++);\n"
        "  var tr = document.createElement('tr');\n"
        "  tr.innerHTML = '<td>' + label + '</td><td><span class=\"badge\">Active</span></td>' +\n"
        "    '<td id=\"' + id + '\">불러오는 중...</td>';\n"
        "  tb.appendChild(tr);\n"
        "  fetch('https://api.counterapi.dev/v1/' + NS + '/' + key)\n"
        "    .then(function(r){ return r.json(); })\n"
        "    .then(function(d){ document.getElementById(id).innerText = (d.count || 0) + ' 회'; })\n"
        "    .catch(function(){ document.getElementById(id).innerText = '0 회'; });\n"
        "}\n"
        "addRow('/ (메인)', 'main_root');\n"
        "posts.forEach(function(f){ addRow('/posts/' + f + '.html', '_posts_' + f + '_html'); });\n"
        "</script>"
    )
    body = (
        "<div class='container'><div class='admin-card' style='margin-top: 30px;'>"
        "<h2>📈 페이지별 조회수 대시보드</h2>"
        "<table class='stats-table'><thead><tr><th>페이지 경로</th><th>상태</th><th>조회수(PV)</th></tr></thead>"
        "<tbody id='statsTableBody'></tbody></table></div></div>" + script
    )
    page = page_shell(cfg, f"대시보드 - {cfg['blog_name']}", "관리자 대시보드",
                      f"{cfg['blog_domain']}/admin.html", body, extra_head=admin_style)
    with open(os.path.join(BASE_DIR, "admin.html"), "w", encoding="utf-8") as f:
        f.write(page)


def render_site(cfg):
    posts_data = []
    if os.path.exists(DATA_PATH):
        with open(DATA_PATH, "r", encoding="utf-8") as f:
            posts_data = json.load(f)
    posts_data = sorted(posts_data, key=lambda x: x.get("filename", ""), reverse=True)

    generate_required_pages(cfg)
    generate_sitemap(cfg, posts_data)
    generate_rss(cfg, posts_data)
    generate_robots_and_ads(cfg)

    # ---- 메인(목록) 페이지 + 페이지네이션 ----
    per_page = int(cfg.get("posts_per_page", 9))
    total_pages = max(1, (len(posts_data) + per_page - 1) // per_page)

    for page_idx in range(total_pages):
        start, end = page_idx * per_page, (page_idx + 1) * per_page
        cards = []
        for i, p in enumerate(posts_data):
            summary = strip_tags(p["content"])[:140]
            display = "" if start <= i < end else " style='display:none;'"
            cards.append(
                f"<div class='post-card'{display}>"
                f"<a href='/posts/{p['filename']}.html'>"
                "<div class='post-card-info'>"
                f"<h2>{html.escape(p['title'])}</h2>"
                f"<p>{html.escape(summary)}...</p>"
                f"<div style='font-size:12px; color:#999;'>{p['date']}</div>"
                "</div>"
                f"<img class='post-card-img' src='{p['image']}' alt='{html.escape(p['title'])}' loading='lazy'>"
                "</a></div>"
            )

        pagination = ["<div class='pagination' id='mainPagination'>"]
        for i in range(1, total_pages + 1):
            href = "/" if i == 1 else f"/index{i}.html"
            if i == page_idx + 1:
                pagination.append(f"<span class='current'>{i}</span>")
            else:
                pagination.append(f"<a href='{href}'>{i}</a>")
        pagination.append("</div>")

        body = (
            f"<div class='container'>{SEARCH_BOX_HTML}"
            f"<div class='main-content'>{''.join(cards)}</div>"
            f"{''.join(pagination)}</div>"
        )
        fname = "index.html" if page_idx == 0 else f"index{page_idx + 1}.html"
        canonical = cfg["blog_domain"] + ("/" if page_idx == 0 else f"/{fname}")
        page = page_shell(cfg, cfg["blog_name"], cfg["blog_description"], canonical, body)
        with open(os.path.join(BASE_DIR, fname), "w", encoding="utf-8") as f:
            f.write(page)

    # ---- 개별 포스트 페이지 ----
    os.makedirs(POSTS_DIR, exist_ok=True)
    for p in posts_data:
        others = [x for x in posts_data if x["filename"] != p["filename"]][:4]
        recommend = ""
        if others:
            items = "".join(
                f"<a href='/posts/{rp['filename']}.html' class='recommend-card'>"
                f"<img class='recommend-thumb' src='{rp['image']}' alt='{html.escape(rp['title'])}' loading='lazy'>"
                f"<p class='recommend-title'>{html.escape(rp['title'])}</p></a>"
                for rp in others
            )
            recommend = ("<div class='recommend-section'><h3>📰 함께 보면 좋은 인사이트</h3>"
                         f"<div class='recommend-grid'>{items}</div></div>")

        reason_box = ""
        if p.get("trend_reason"):
            reason_box = (f"<div class='trend-reason-box'><strong>💡 분석 배경:</strong> "
                          f"{html.escape(p['trend_reason'])}</div>")

        tags_html = ""
        if p.get("tags"):
            tags_html = "<div class='tags'>" + "".join(
                f"<span>#{html.escape(str(t))}</span>" for t in p["tags"]) + "</div>"

        body = (
            "<div class='container'><div class='main-content'><article>"
            f"<h1>{html.escape(p['title'])}</h1>"
            f"<div style='color:#999;font-size:14px;margin-bottom:20px;'>{p['date']}</div>"
            f"<div class='featured-img-container'><img class='featured-img' src='{p['image']}' "
            f"alt='{html.escape(p['title'])}'></div>"
            f"{reason_box}<div class='article-body'>{p['content']}</div>"
            f"{tags_html}{recommend}</article></div></div>"
        )
        desc = p.get("meta_description") or strip_tags(p["content"])[:150]
        canonical = f"{cfg['blog_domain']}/posts/{p['filename']}.html"
        page = page_shell(cfg, p["title"], desc, canonical, body,
                          extra_head=og_and_jsonld(cfg, p))
        with open(os.path.join(POSTS_DIR, f"{p['filename']}.html"), "w", encoding="utf-8") as f:
            f.write(page)

    write_admin_dashboard(cfg, posts_data)
    print(f"🛠️ 사이트 빌드 완료 (총 {len(posts_data)}개 포스트, {total_pages}페이지)")


# ==========================================
# 5단계: GitHub 자동 배포
# ==========================================

def git_sync(cfg, commit_message, max_retries=4):
    branch = cfg.get("git_branch", "main")
    try:
        subprocess.run(["git", "add", "-A"], check=True, cwd=BASE_DIR)
        diff = subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=BASE_DIR)
        if diff.returncode == 0:
            print("ℹ️ 변경 사항이 없어 커밋을 건너뜁니다.")
            return True
        subprocess.run(["git", "commit", "-m", commit_message], check=True, cwd=BASE_DIR)
    except subprocess.CalledProcessError as e:
        print(f"❌ git 커밋 실패: {e}")
        return False

    # 원격에서 다른 변경이 있었을 수 있으므로 rebase 후 push (충돌 자동 회피)
    subprocess.run(["git", "pull", "--rebase", "origin", branch], cwd=BASE_DIR)

    delay = 2
    for attempt in range(1, max_retries + 1):
        result = subprocess.run(["git", "push", "-u", "origin", branch], cwd=BASE_DIR)
        if result.returncode == 0:
            print("🎉 GitHub 배포 완료!")
            return True
        print(f"⚠️ push 실패 — {delay}초 후 재시도 ({attempt}/{max_retries})")
        time.sleep(delay)
        delay *= 2
    print("❌ GitHub push에 최종 실패했습니다. 네트워크/인증 상태를 확인하세요.")
    return False


# ==========================================
# 메인 파이프라인
# ==========================================

def main():
    parser = argparse.ArgumentParser(description="50대 타깃 트렌드 자동 블로그 발행기")
    parser.add_argument("--keyword", help="키워드 직접 지정 (트렌드 수집 생략)")
    parser.add_argument("--render-only", action="store_true", help="글 생성 없이 사이트만 재빌드")
    parser.add_argument("--no-push", action="store_true", help="git 커밋/푸시 생략")
    args = parser.parse_args()

    load_env_file()
    cfg = load_config()
    os.makedirs(POSTS_DIR, exist_ok=True)

    if args.render_only:
        render_site(cfg)
        if not args.no_push:
            git_sync(cfg, "chore: rebuild site")
        return

    api_key = get_api_key()
    history = load_history()

    # 하루 발행량 제한 (스팸성 대량 발행 방지 — 애드센스 정책 보호)
    limit = int(cfg.get("max_posts_per_day", 3))
    if posts_today(history) >= limit:
        print(f"ℹ️ 오늘 발행량({limit}개)을 이미 채웠습니다. 종료합니다.")
        return

    # 1) 키워드 결정
    if args.keyword:
        selection = {"keyword": args.keyword, "reason": "사용자 직접 지정", "category": "society"}
    else:
        print("📡 실시간 트렌드 키워드를 수집합니다...")
        candidates = fetch_trending_keywords()
        selection = select_keyword_for_50s(candidates, history, api_key, cfg["model_name"])

    keyword = selection["keyword"]
    print(f"🎯 선정 키워드: [{keyword}] — {selection['reason']}")

    # 2) 본문 생성
    blog_json = generate_blog_content(keyword, selection["reason"], api_key, cfg["model_name"])
    if not blog_json:
        print("❌ 콘텐츠 생성에 실패하여 종료합니다.")
        sys.exit(1)

    # 3) 포스트 데이터 저장
    now = datetime.datetime.now()
    blog_json["keyword"] = keyword
    blog_json["filename"] = f"post_{now.strftime('%Y%m%d_%H%M%S')}"
    blog_json["date"] = now.strftime("%Y-%m-%d")
    category = blog_json.get("image_category")
    if category not in IMAGE_CATEGORIES:
        category = selection.get("category", "society")
    blog_json["image"] = pick_image(category)

    posts_data = []
    if os.path.exists(DATA_PATH):
        with open(DATA_PATH, "r", encoding="utf-8") as f:
            posts_data = json.load(f)
    posts_data.append(blog_json)
    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(posts_data, f, ensure_ascii=False, indent=2)

    history.append({"keyword": keyword, "date": datetime.date.today().isoformat(),
                    "title": blog_json["title"]})
    save_history(history)

    # 4) 사이트 빌드
    render_site(cfg)
    print(f"🎉 발행 완료! [{keyword}] → 「{blog_json['title']}」")

    # 5) GitHub 배포
    if not args.no_push:
        git_sync(cfg, f"post: {blog_json['title']}")


if __name__ == "__main__":
    main()
