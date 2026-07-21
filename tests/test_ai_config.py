"""AI provider preset resolution tests."""

from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from ai.client import normalize_base_url
from ai.config import ai_available, resolve_llm_settings


class AiConfigTests(unittest.TestCase):
    def setUp(self) -> None:
        self._env_patch = patch.dict(os.environ, {}, clear=True)
        self._env_patch.start()
        self._secret_patch = patch(
            "ai.config._secret",
            side_effect=lambda name: os.environ.get(name, "").strip(),
        )
        self._secret_patch.start()
        from ai.config import clear_ollama_probe_cache

        clear_ollama_probe_cache()
        self._ollama_patch = patch("ai.config.ollama_reachable", return_value=False)
        self._ollama_patch.start()

    def tearDown(self) -> None:
        self._ollama_patch.stop()
        self._secret_patch.stop()
        self._env_patch.stop()
        from ai.config import clear_ollama_probe_cache

        clear_ollama_probe_cache()

    def test_offline_when_no_key(self) -> None:
        settings = resolve_llm_settings()
        self.assertFalse(settings.available)
        self.assertFalse(ai_available())

    def test_gemini_preset(self) -> None:
        with patch.dict(
            os.environ,
            {
                "AI_PROVIDER": "gemini",
                "GEMINI_API_KEY": "test-gemini-key",
            },
            clear=True,
        ):
            settings = resolve_llm_settings()
            self.assertEqual(settings.provider, "gemini")
            self.assertEqual(settings.label, "Google Gemini (free tier)")
            self.assertEqual(settings.api_key, "test-gemini-key")
            self.assertIn("generativelanguage.googleapis.com", settings.base_url)
            self.assertEqual(settings.model, "gemini-2.0-flash")
            self.assertFalse(settings.supports_json_mode)
            self.assertTrue(settings.available)
            self.assertTrue(ai_available())

    def test_together_preset(self) -> None:
        with patch.dict(
            os.environ,
            {
                "AI_PROVIDER": "together",
                "TOGETHER_API_KEY": "test-together-key",
            },
            clear=True,
        ):
            settings = resolve_llm_settings()
            self.assertEqual(settings.provider, "together")
            self.assertEqual(settings.api_key, "test-together-key")
            self.assertEqual(settings.base_url, "https://api.together.xyz/v1")
            self.assertTrue(settings.available)
            self.assertTrue(ai_available())

    def test_explicit_base_url_overrides_preset(self) -> None:
        with patch.dict(
            os.environ,
            {
                "AI_PROVIDER": "gemini",
                "GEMINI_API_KEY": "key",
                "OPENAI_BASE_URL": "https://custom.example/v1",
            },
            clear=True,
        ):
            settings = resolve_llm_settings()
            self.assertEqual(settings.base_url, "https://custom.example/v1")

    def test_openai_key_without_provider(self) -> None:
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}, clear=True):
            settings = resolve_llm_settings()
        self.assertEqual(settings.provider, "openai")
        self.assertTrue(settings.available)

    def test_groq_accepts_openai_compatible_key(self) -> None:
        with patch.dict(
            os.environ,
            {
                "AI_PROVIDER": "groq",
                "OPENAI_API_KEY": "gsk-legacy-style",
            },
            clear=True,
        ):
            settings = resolve_llm_settings()
            self.assertEqual(settings.provider, "groq")
            self.assertEqual(settings.api_key, "gsk-legacy-style")
            self.assertTrue(settings.available)

    def test_gemini_ignores_openai_api_key(self) -> None:
        with patch.dict(
            os.environ,
            {
                "AI_PROVIDER": "gemini",
                "OPENAI_API_KEY": "sk-openai-should-not-leak",
                "GEMINI_API_KEY": "gemini-only",
            },
            clear=True,
        ):
            settings = resolve_llm_settings()
            self.assertEqual(settings.provider, "gemini")
            self.assertEqual(settings.api_key, "gemini-only")

    def test_gemini_without_gemini_key_stays_unavailable(self) -> None:
        with patch.dict(
            os.environ,
            {
                "AI_PROVIDER": "gemini",
                "OPENAI_API_KEY": "sk-openai-only",
            },
            clear=True,
        ):
            settings = resolve_llm_settings()
            self.assertEqual(settings.provider, "gemini")
            self.assertEqual(settings.api_key, "")
            self.assertFalse(settings.available)

    def test_ollama_placeholder_without_key(self) -> None:
        with patch.dict(os.environ, {"AI_PROVIDER": "ollama"}, clear=True):
            settings = resolve_llm_settings()
            self.assertEqual(settings.provider, "ollama")
            self.assertEqual(settings.api_key, "ollama")
            self.assertTrue(settings.available)
            self.assertTrue(settings.free)

    def test_auto_detect_ollama_when_reachable(self) -> None:
        self._ollama_patch.stop()
        with patch("ai.config.ollama_reachable", return_value=True):
            settings = resolve_llm_settings()
        self._ollama_patch = patch("ai.config.ollama_reachable", return_value=False)
        self._ollama_patch.start()
        self.assertEqual(settings.provider, "ollama")
        self.assertTrue(settings.available)
        self.assertTrue(settings.free)

    def test_prefers_gemini_free_key_over_openai(self) -> None:
        with patch.dict(
            os.environ,
            {
                "GEMINI_API_KEY": "gemini-free",
                "OPENAI_API_KEY": "sk-paid",
            },
            clear=True,
        ):
            settings = resolve_llm_settings()
        self.assertEqual(settings.provider, "gemini")
        self.assertEqual(settings.api_key, "gemini-free")
        self.assertTrue(settings.free)

    def test_offline_provider_flag(self) -> None:
        with patch.dict(os.environ, {"AI_PROVIDER": "offline"}, clear=True):
            settings = resolve_llm_settings()
        self.assertFalse(settings.available)

    def test_normalize_base_url_together(self) -> None:
        self.assertEqual(
            normalize_base_url("https://api.together.xyz/v1"),
            "https://api.together.xyz/v1",
        )

    def test_normalize_base_url_azure_style(self) -> None:
        self.assertEqual(
            normalize_base_url("https://example.openai.azure.com"),
            "https://example.openai.azure.com/openai/v1",
        )


if __name__ == "__main__":
    unittest.main()
