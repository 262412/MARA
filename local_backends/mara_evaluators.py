from __future__ import annotations

from typing import Any

from benchmark.research_adapters import research_adapter_metrics


class _LocalProxyEvaluator:
    adapter_name = ""

    def __call__(self, prediction: dict[str, Any]) -> dict[str, Any]:
        metrics = research_adapter_metrics(prediction).get(self.adapter_name) or {}
        return {
            "metrics": dict(metrics),
            "metadata": {
                "implementation": self.__class__.__name__,
                "backend": "local_proxy",
                "paper_grade": False,
            },
        }


class ALCELocalEvaluator(_LocalProxyEvaluator):
    adapter_name = "alce"


class MMDocRAGLocalEvaluator(_LocalProxyEvaluator):
    adapter_name = "mmdocrag"


class RAGTruthLocalEvaluator(_LocalProxyEvaluator):
    adapter_name = "ragtruth"


class RagasLocalEvaluator(_LocalProxyEvaluator):
    adapter_name = "ragas"
