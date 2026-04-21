from __future__ import annotations

from typing import Callable

from decouple import config

from kotaemon.base import Document

from .base import BaseReranking


def _resolve_cohere_api_key_from_ktem() -> str:
    from ktem.embeddings.manager import (
        embedding_models_manager as embeddings,
    )

    cohere_model = embeddings.get("cohere")
    return cohere_model._kwargs.get("cohere_api_key", "")  # type: ignore[attr-defined]


class CohereReranking(BaseReranking):
    model_name: str = "rerank-v4.0-fast"
    cohere_api_key: str = config("COHERE_API_KEY", "")
    cohere_api_key_resolver: Callable[[], str | None] | None = None
    use_key_from_ktem: bool = False

    def run(self, documents: list[Document], query: str) -> list[Document]:
        """Use Cohere Reranker model to re-order documents
        with their relevance score"""
        try:
            import cohere
        except ImportError:
            raise ImportError(
                "Please install Cohere `pip install cohere` to use Cohere Reranking"
            )

        # try to get COHERE_API_KEY from embeddings
        if not self.cohere_api_key:
            resolved_api_key = None

            if self.cohere_api_key_resolver is not None:
                resolved_api_key = self.cohere_api_key_resolver()
            elif self.use_key_from_ktem:
                try:
                    resolved_api_key = _resolve_cohere_api_key_from_ktem()
                except Exception as e:
                    print("Cannot get Cohere API key from `ktem`", e)

            if resolved_api_key and resolved_api_key != "your-key":
                self.cohere_api_key = resolved_api_key

        if not self.cohere_api_key:
            print("Cohere API key not found. Skipping rerankings.")
            return documents

        cohere_client = cohere.Client(self.cohere_api_key)
        compressed_docs: list[Document] = []

        if not documents:  # to avoid empty api call
            return compressed_docs

        _docs = [d.content for d in documents]
        response = cohere_client.rerank(
            model=self.model_name, query=query, documents=_docs
        )
        for r in response.results:
            doc = documents[r.index]
            doc.metadata["reranking_score"] = r.relevance_score
            compressed_docs.append(doc)

        return compressed_docs
