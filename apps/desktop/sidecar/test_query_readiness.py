from __future__ import annotations

import unittest

from .query_readiness import (
    QueryReadiness,
    classify_query_failure,
    evaluate_query_readiness,
)


class QueryReadinessTest(unittest.TestCase):
    def test_no_default_llm_fails_closed_without_google_fallback(self) -> None:
        readiness = evaluate_query_readiness(
            {
                "KH_LLMS": {},
                "KH_EMBEDDINGS": {
                    "ollama": {
                        "default": True,
                        "spec": {
                            "__type__": "kotaemon.embeddings.OpenAIEmbeddings",
                            "model": "nomic-embed-text",
                            "api_key": "ollama",
                        },
                    }
                },
            },
            desktop=True,
        )

        self.assertFalse(readiness.query_ready)
        self.assertEqual(readiness.query_issue_code, "llm_not_configured")
        self.assertFalse(readiness.query_retryable)
        self.assertEqual(readiness.query_provider, "")
        self.assertEqual(readiness.query_model, "")
        self.assertEqual(readiness.embedding_provider, "ollama")
        self.assertEqual(readiness.embedding_model, "nomic-embed-text")

    def test_missing_credentials_are_distinct_from_missing_provider(self) -> None:
        readiness = evaluate_query_readiness(
            {
                "KH_LLMS": {
                    "openai": {
                        "default": True,
                        "spec": {
                            "__type__": "kotaemon.llms.ChatOpenAI",
                            "model": "chat-model",
                            "api_key": "",
                        },
                    }
                },
                "KH_EMBEDDINGS": {},
            },
            desktop=True,
        )

        self.assertFalse(readiness.query_ready)
        self.assertEqual(readiness.query_issue_code, "llm_credentials_missing")
        self.assertEqual(readiness.query_provider, "openai")
        self.assertEqual(readiness.query_model, "chat-model")

    def test_provider_and_model_are_safe_labels(self) -> None:
        readiness = evaluate_query_readiness(
            {
                "KH_LLMS": {
                    "azure": {
                        "default": True,
                        "spec": {
                            "__type__": "kotaemon.llms.AzureChatOpenAI",
                            "model": "deployment",
                            "azure_deployment": "deployment",
                            "azure_endpoint": "https://secret.example/tenant",
                            "api_key": "secret-key",
                        },
                    }
                },
                "KH_EMBEDDINGS": {},
            },
            desktop=True,
        )

        self.assertTrue(readiness.query_ready)
        self.assertEqual(readiness.query_provider, "azure")
        self.assertEqual(readiness.query_model, "deployment")
        self.assertNotIn("secret", str(readiness.as_dict()).lower())
        self.assertNotIn("https://", str(readiness.as_dict()).lower())

    def test_failure_classification_is_stable_and_path_free(self) -> None:
        class RateLimitedError(RuntimeError):
            status_code = 429

        class AuthenticationError(RuntimeError):
            response = type("Response", (), {"status_code": 401})()

        cases = [
            (
                ModuleNotFoundError("/private/module.py"),
                "llm_dependency_missing",
                False,
            ),
            (PermissionError("401 /private/response.json"), "llm_auth_failed", False),
            (
                AuthenticationError("provider body /private/raw"),
                "llm_auth_failed",
                False,
            ),
            (
                ValueError("API key is missing at /private/config"),
                "llm_credentials_missing",
                False,
            ),
            (RateLimitedError("429 raw provider body"), "llm_rate_limited", True),
            (TimeoutError("timeout /private/model"), "llm_unavailable", True),
            (RuntimeError("unexpected /private/trace"), "query_runtime_failed", False),
        ]
        for error, code, retryable in cases:
            with self.subTest(code=code):
                classified = classify_query_failure(error)
                self.assertEqual(classified.code, code)
                self.assertEqual(classified.retryable, retryable)
                self.assertNotIn("/private", classified.message)
                self.assertNotIn("raw provider body", classified.message)

    def test_query_readiness_payload_is_explicit(self) -> None:
        readiness = QueryReadiness.ready(
            query_provider="openai",
            query_model="chat-model",
            embedding_provider="ollama",
            embedding_model="nomic-embed-text",
        )
        self.assertEqual(
            readiness.as_dict(),
            {
                "query_ready": True,
                "query_issue_code": None,
                "query_message": "Answer generation is ready.",
                "query_action": "none",
                "query_retryable": False,
                "query_provider": "openai",
                "query_model": "chat-model",
                "embedding_provider": "ollama",
                "embedding_model": "nomic-embed-text",
            },
        )

    def test_ollama_reuses_openai_runtime_dependency_check(self) -> None:
        settings = {
            "KH_LLMS": {
                "ollama": {
                    "default": True,
                    "spec": {
                        "__type__": "kotaemon.llms.ChatOpenAI",
                        "model": "llama3",
                        "api_key": "ollama",
                    },
                }
            },
            "KH_EMBEDDINGS": {},
        }

        ready = evaluate_query_readiness(
            settings,
            desktop=True,
            module_available=lambda name: name == "openai",
        )
        missing = evaluate_query_readiness(
            settings,
            desktop=True,
            module_available=lambda _name: False,
        )

        self.assertTrue(ready.query_ready)
        self.assertEqual(missing.query_issue_code, "llm_dependency_missing")


if __name__ == "__main__":
    unittest.main()
