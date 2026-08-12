from __future__ import annotations

import unittest

from .query_readiness import (
    QueryReadiness,
    classify_query_failure,
    evaluate_query_readiness,
)


class _ProviderError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        status_code: int,
        code: str | None = None,
        request_id: str | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.body = {"code": code} if code else None
        self.request_id = request_id


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
            request_id = "provider-rate-123"

        class AuthenticationError(RuntimeError):
            response = type("Response", (), {"status_code": 401})()

        cases = [
            (
                ModuleNotFoundError("/private/module.py"),
                "llm_dependency_missing",
                False,
            ),
            (
                PermissionError("401 /private/response.json"),
                "llm_authentication_failed",
                False,
            ),
            (
                AuthenticationError("provider body /private/raw"),
                "llm_authentication_failed",
                False,
            ),
            (
                ValueError("API key is missing at /private/config"),
                "llm_credentials_missing",
                False,
            ),
            (RateLimitedError("429 raw provider body"), "llm_rate_limited", True),
            (
                TimeoutError("timeout /private/model"),
                "llm_provider_unreachable",
                True,
            ),
            (RuntimeError("unexpected /private/trace"), "query_runtime_failed", False),
        ]
        for error, code, retryable in cases:
            with self.subTest(code=code):
                classified = classify_query_failure(error)
                self.assertEqual(classified.code, code)
                self.assertEqual(classified.retryable, retryable)
                self.assertNotIn("/private", classified.message)
                self.assertNotIn("raw provider body", classified.message)

    def test_provider_model_failures_keep_safe_request_identity(self) -> None:
        cases = [
            (
                _ProviderError(
                    "provider body /private/raw",
                    status_code=404,
                    code="model_not_found",
                    request_id="provider-model-404",
                ),
                "llm_model_not_found",
            ),
            (
                _ProviderError(
                    "unsupported model /private/raw",
                    status_code=400,
                    code="unsupported_model",
                ),
                "llm_model_unsupported",
            ),
            (
                _ProviderError(
                    "forbidden /private/raw",
                    status_code=403,
                    request_id="provider-access-403",
                ),
                "llm_model_access_denied",
            ),
        ]
        for error, code in cases:
            with self.subTest(code=code):
                classified = classify_query_failure(error)
                self.assertEqual(classified.code, code)
                self.assertFalse(classified.retryable)
                self.assertNotIn("/private", str(classified.as_dict()))

        model_missing = classify_query_failure(
            _ProviderError(
                "secret-key provider body /private/raw",
                status_code=404,
                code="model_not_found",
                request_id="provider-model-404",
            )
        )
        self.assertEqual(model_missing.provider_request_id, "provider-model-404")
        self.assertEqual(
            model_missing.diagnostic,
            "provider_status=404 provider_code=model_not_found",
        )
        self.assertNotIn("secret-key", str(model_missing.as_dict()))

    def test_model_text_never_masquerades_as_a_missing_dependency(self) -> None:
        self.assertEqual(
            classify_query_failure(RuntimeError("unknown model")).code,
            "llm_model_not_found",
        )
        self.assertEqual(
            classify_query_failure(RuntimeError("unsupported model")).code,
            "llm_model_unsupported",
        )

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
