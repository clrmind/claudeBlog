#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

BASE_DIR = Path(__file__).resolve().parents[2]
NORMALIZED_DIR = BASE_DIR / "data" / "government" / "normalized"
TAGGED_DIR = BASE_DIR / "data" / "government" / "tagged"
KNOWLEDGE_ROOT = BASE_DIR / "knowledge" / "government"
DEFAULT_MODEL = "gemini-2.5-flash"

REGIONS = {
    "전국": ["전국", "지역 제한 없음"], "서울": ["서울", "서울특별시"],
    "경기": ["경기", "경기도"], "인천": ["인천"], "부산": ["부산"],
    "대구": ["대구"], "광주": ["광주"], "대전": ["대전"],
    "울산": ["울산"], "세종": ["세종"], "강원": ["강원"],
    "충북": ["충북", "충청북도"], "충남": ["충남", "충청남도"],
    "전북": ["전북"], "전남": ["전남"], "경북": ["경북"],
    "경남": ["경남"], "제주": ["제주"],
}

TARGETS = {
    "중소기업": ["중소기업"], "소상공인": ["소상공인"],
    "창업기업": ["창업기업", "예비창업자", "스타트업"],
    "벤처기업": ["벤처기업"], "여성기업": ["여성기업"],
    "청년기업": ["청년기업", "청년 창업"], "제조기업": ["제조기업", "제조업"],
    "수출기업": ["수출기업"], "기업·단체": ["기업 및 단체", "기업·단체"],
}

INDUSTRIES = {
    "제조": ["제조", "공장", "생산"], "정보통신": ["정보통신", "ICT", "소프트웨어"],
    "AI": ["AI", "인공지능"], "데이터": ["데이터", "빅데이터"],
    "디자인": ["디자인"], "콘텐츠": ["콘텐츠", "출판", "미디어"],
    "바이오": ["바이오", "헬스케어"], "반도체": ["반도체"],
    "로봇": ["로봇"], "수출": ["수출", "해외진출"],
    "관광": ["관광"], "농식품": ["농식품", "식품", "농업"],
    "환경·에너지": ["환경", "에너지", "탄소중립", "ESG"],
}

SUPPORT_TYPES = {
    "사업화": ["사업화", "제품화", "상용화"], "R&D": ["R&D", "연구개발", "기술개발"],
    "판로": ["판로", "유통", "판매", "마케팅", "홍보"],
    "수출": ["수출", "해외진출"], "자금": ["융자", "정책자금", "대출"],
    "교육": ["교육", "훈련"], "컨설팅": ["컨설팅", "멘토링"],
    "입주·공간": ["입주", "공간", "사무실"], "행사·전시": ["행사", "전시", "박람회", "페어", "부스"],
}

TECHNOLOGIES = {
    "AI": ["AI", "인공지능"], "클라우드": ["클라우드"],
    "IoT": ["IoT", "사물인터넷"], "빅데이터": ["빅데이터"],
    "디지털전환": ["디지털 전환", "DX"], "스마트공장": ["스마트공장", "스마트팩토리"],
    "로봇": ["로봇"], "블록체인": ["블록체인"], "사이버보안": ["사이버보안", "정보보호"],
}

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def load_env() -> None:
    path = BASE_DIR / ".env"
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip("'\""))

def read_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("JSON 최상위 값은 객체여야 합니다.")
    return data

def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)

def latest_normalized() -> Path:
    files = list(NORMALIZED_DIR.glob("*.json"))
    if not files:
        raise FileNotFoundError("정규화 JSON이 없습니다.")
    return max(files, key=lambda p: p.stat().st_mtime)

def text_for(data: dict[str, Any]) -> str:
    return "\n".join(str(data.get(k) or "") for k in (
        "title", "ministry", "organization", "target",
        "support_summary", "application_method", "content",
    ))

def match(text: str, mapping: dict[str, list[str]]) -> list[str]:
    lowered = text.lower()
    return [
        label for label, words in mapping.items()
        if any(word.lower() in lowered for word in words)
    ]

def amounts(text: str) -> list[str]:
    pattern = r"(?:최대\s*)?\d+(?:,\d{3})*(?:\.\d+)?\s*(?:억원|천만원|백만원|만원|원)"
    out = []
    for value in re.findall(pattern, text):
        value = re.sub(r"\s+", " ", value).strip()
        if value not in out:
            out.append(value)
    return out[:5]

def rule_tags(data: dict[str, Any]) -> dict[str, Any]:
    text = text_for(data)
    result = {
        "regions": match(text, REGIONS),
        "target_groups": match(text, TARGETS),
        "industries": match(text, INDUSTRIES),
        "technologies": match(text, TECHNOLOGIES),
        "support_types": match(text, SUPPORT_TYPES),
        "amounts": amounts(text),
    }
    score = 50
    reasons = []
    for ok, points, reason in (
        (bool(data.get("application_deadline")), 10, "마감일이 명확함"),
        (bool(result["target_groups"]), 10, "지원대상이 명확함"),
        (bool(result["support_types"]), 10, "지원형태가 명확함"),
        (bool(data.get("support_summary")), 10, "지원내용이 구체적임"),
        (bool(data.get("application_method")), 5, "신청방법이 명시됨"),
        (bool(result["amounts"]), 5, "지원규모가 명시됨"),
    ):
        if ok:
            score += points
            reasons.append(reason)
    result["recommendation_score"] = min(score, 100)
    result["recommendation_reasons"] = reasons
    result["difficulty"] = "보통"
    result["keywords"] = sorted(set(
        result["regions"] + result["target_groups"] + result["industries"] +
        result["technologies"] + result["support_types"]
    ))[:20]
    return result

def gemini_tags(data: dict[str, Any], base: dict[str, Any], api_key: str, model: str) -> dict[str, Any]:
    prompt = (
        "대한민국 정부지원사업을 분류하라. 반드시 JSON 객체만 반환한다. "
        "스키마: regions,target_groups,industries,technologies,support_types,"
        "keywords,difficulty,recommendation_score,recommendation_reasons. "
        "원문에 없는 사실은 만들지 말고 배열은 각 8개 이하로 한다.\n공고:\n"
        + json.dumps(data, ensure_ascii=False)
        + "\n규칙기반 초안:\n"
        + json.dumps(base, ensure_ascii=False)
    )
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.1, "responseMimeType": "application/json"},
    }
    response = requests.post(url, json=payload, timeout=60)
    response.raise_for_status()
    text = response.json()["candidates"][0]["content"]["parts"][0]["text"]
    result = json.loads(text)
    if not isinstance(result, dict):
        raise ValueError("Gemini 결과가 객체가 아닙니다.")
    return result

def merge(base: dict[str, Any], ai: dict[str, Any]) -> dict[str, Any]:
    result = dict(base)
    for field in ("regions", "target_groups", "industries", "technologies", "support_types", "keywords", "recommendation_reasons"):
        values = []
        for source in (base.get(field), ai.get(field)):
            if isinstance(source, list):
                for item in source:
                    value = str(item).strip()
                    if value and value not in values:
                        values.append(value)
        result[field] = values[:20]
    if str(ai.get("difficulty")) in ("쉬움", "보통", "어려움"):
        result["difficulty"] = str(ai["difficulty"])
    try:
        result["recommendation_score"] = max(0, min(100, int(ai.get("recommendation_score"))))
    except Exception:
        pass
    return result

def knowledge_latest(source_id: str) -> Path | None:
    for path in KNOWLEDGE_ROOT.glob(f"*/{source_id}/latest.json"):
        return path
    return None

def tag_opportunity(path: Path, use_ai: bool = True, model: str = DEFAULT_MODEL) -> tuple[dict[str, Any], Path, Path | None]:
    data = read_json(path)
    enrichment = rule_tags(data)
    enrichment["tagger_mode"] = "rules"
    enrichment["tagger_version"] = "0.1"
    enrichment["tagged_at"] = now_iso()

    if use_ai:
        load_env()
        api_key = os.getenv("GEMINI_API_KEY", "").strip()
        if api_key:
            try:
                enrichment = merge(enrichment, gemini_tags(data, enrichment, api_key, model))
                enrichment["tagger_mode"] = "rules+gemini"
                enrichment["tagger_version"] = "0.1"
                enrichment["tagged_at"] = now_iso()
            except Exception as exc:
                print(f"⚠️ Gemini 태깅 실패, 규칙기반 결과 사용: {exc}")

    source = str(data.get("source") or "unknown")
    source_id = str(data.get("source_id") or "unknown")
    output = {
        "source": source,
        "source_id": source_id,
        "title": str(data.get("title") or ""),
        "enrichment": enrichment,
    }
    output_path = TAGGED_DIR / f"{source}_{source_id}.json"
    write_json(output_path, output)

    latest = knowledge_latest(source_id)
    if latest:
        knowledge = read_json(latest)
        knowledge["enrichment"] = enrichment
        knowledge["enriched_at"] = now_iso()
        write_json(latest, knowledge)

    return output, output_path, latest

def main() -> int:
    parser = argparse.ArgumentParser(description="Atlas 정부지원사업 AI Tagger")
    parser.add_argument("normalized_json", nargs="?")
    parser.add_argument("--no-ai", action="store_true")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    args = parser.parse_args()
    try:
        path = Path(args.normalized_json).expanduser().resolve() if args.normalized_json else latest_normalized()
        output, output_path, latest = tag_opportunity(path, not args.no_ai, args.model)
        e = output["enrichment"]
        print("✅ AI Tagger 완료")
        print("📍 지역:", ", ".join(e["regions"]) or "없음")
        print("🎯 대상:", ", ".join(e["target_groups"]) or "없음")
        print("🏭 업종:", ", ".join(e["industries"]) or "없음")
        print("🧠 기술:", ", ".join(e["technologies"]) or "없음")
        print("💼 지원유형:", ", ".join(e["support_types"]) or "없음")
        print(f"⭐ 추천도: {e['recommendation_score']}점")
        print(f"🧩 난이도: {e['difficulty']}")
        print(f"⚙️ 모드: {e['tagger_mode']}")
        print(f"💾 태그 JSON: {output_path.relative_to(BASE_DIR)}")
        if latest:
            print(f"📚 Knowledge 반영: {latest.relative_to(BASE_DIR)}")
        return 0
    except Exception as exc:
        print(f"❌ AI Tagger 오류: {exc}", file=sys.stderr)
        return 1

if __name__ == "__main__":
    raise SystemExit(main())
