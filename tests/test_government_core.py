#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from plugins.government.collector import detect_source, make_source_id
from plugins.government.normalizer import clean_text, extract_dates, split_business_overview
from plugins.government.knowledge_store import calculate_record_hash, store_knowledge
from plugins.government.ai_tagger import rule_tags


class CollectorTests(unittest.TestCase):
    def test_detect_source_bizinfo(self):
        self.assertEqual(detect_source("https://www.bizinfo.go.kr/example"), "bizinfo")

    def test_source_id_is_stable(self):
        url = "https://example.com/detail?id=1"
        self.assertEqual(make_source_id(url), make_source_id(url))
        self.assertEqual(len(make_source_id(url)), 20)


class NormalizerTests(unittest.TestCase):
    def test_clean_text(self):
        self.assertEqual(clean_text("  서울\n\n  디자인   지원  "), "서울\n디자인 지원")

    def test_extract_dates(self):
        start, end = extract_dates("2026.07.08 ~ 2026.07.20")
        self.assertEqual(start, "2026-07-08")
        self.assertEqual(end, "2026-07-20")

    def test_split_business_overview(self):
        overview = "사업 안내입니다. ☞ 디자인 출판물 제작 기업 및 단체 ☞ 홍보 및 판로 지원"
        target, support = split_business_overview(overview)
        self.assertIn("디자인 출판물", target)
        self.assertIn("판로 지원", support)


class KnowledgeStoreTests(unittest.TestCase):
    def sample_record(self):
        return {
            "source": "bizinfo",
            "source_id": "PBLN_TEST_001",
            "title": "테스트 지원사업",
            "organization": "테스트 기관",
            "application_start": "2026-07-01",
            "application_deadline": "2026-07-31",
            "target": "중소기업",
            "support_summary": "사업화 비용 지원",
            "content": "테스트 본문",
            "content_hash": "abc123",
            "fetched_at": "2026-07-14T00:00:00+00:00",
        }

    def test_hash_ignores_fetched_at(self):
        first = self.sample_record()
        second = dict(first)
        second["fetched_at"] = "2026-07-15T00:00:00+00:00"
        self.assertEqual(calculate_record_hash(first), calculate_record_hash(second))

    def test_store_and_skip_unchanged(self):
        record = self.sample_record()
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            normalized_path = temp_path / "normalized.json"
            normalized_path.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")
            fake_root = temp_path / "knowledge"

            with mock.patch("plugins.government.knowledge_store.KNOWLEDGE_ROOT", fake_root):
                status1, _, version1 = store_knowledge(normalized_path)
                status2, _, version2 = store_knowledge(normalized_path)

            self.assertEqual((status1, version1), ("stored", 1))
            self.assertEqual((status2, version2), ("unchanged", 1))

    def test_changed_record_creates_new_version(self):
        record = self.sample_record()
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            normalized_path = temp_path / "normalized.json"
            fake_root = temp_path / "knowledge"
            normalized_path.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")

            with mock.patch("plugins.government.knowledge_store.KNOWLEDGE_ROOT", fake_root):
                _, _, version1 = store_knowledge(normalized_path)
                changed = dict(record)
                changed["support_summary"] = "지원금 확대"
                normalized_path.write_text(json.dumps(changed, ensure_ascii=False), encoding="utf-8")
                status2, _, version2 = store_knowledge(normalized_path)

            self.assertEqual(version1, 1)
            self.assertEqual((status2, version2), ("stored", 2))


class TaggerTests(unittest.TestCase):
    def test_rule_tags(self):
        record = {
            "title": "서울 AI 중소기업 판로 지원사업",
            "ministry": "서울특별시",
            "organization": "서울산업진흥원",
            "target": "서울 소재 중소기업",
            "support_summary": "AI 기업의 홍보와 판로 지원",
            "application_method": "온라인 접수",
            "application_deadline": "2026-08-31",
            "content": "인공지능 기업 대상 사업입니다.",
        }
        tags = rule_tags(record)
        self.assertIn("서울", tags["regions"])
        self.assertIn("중소기업", tags["target_groups"])
        self.assertIn("AI", tags["industries"])
        self.assertIn("AI", tags["technologies"])
        self.assertIn("판로", tags["support_types"])
        self.assertGreaterEqual(tags["recommendation_score"], 80)


if __name__ == "__main__":
    unittest.main()
