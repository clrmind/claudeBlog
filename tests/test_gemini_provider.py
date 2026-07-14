#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import unittest
from unittest import mock

from atlas.ai.providers.gemini import GeminiProvider


class GeminiProviderTests(unittest.TestCase):
    def test_unavailable_without_key(self):
        provider = GeminiProvider(api_key="")
        self.assertFalse(provider.available())

    @mock.patch("atlas.ai.providers.gemini.requests.post")
    def test_generate_success(self, mocked_post):
        response = mock.Mock()
        response.status_code = 200
        response.json.return_value = {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {
                                "text": "테스트 응답",
                            }
                        ]
                    }
                }
            ]
        }
        response.raise_for_status.return_value = None
        mocked_post.return_value = response

        provider = GeminiProvider(api_key="test-key")
        result = provider.generate("안녕하세요")

        self.assertEqual(result.text, "테스트 응답")
        self.assertEqual(result.provider, "gemini")

    @mock.patch("atlas.ai.providers.gemini.requests.post")
    def test_generate_429(self, mocked_post):
        response = mock.Mock()
        response.status_code = 429
        mocked_post.return_value = response

        provider = GeminiProvider(api_key="test-key")

        with self.assertRaises(RuntimeError):
            provider.generate("테스트")


if __name__ == "__main__":
    unittest.main()
