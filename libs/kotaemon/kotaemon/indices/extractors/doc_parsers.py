from typing import Any

from kotaemon.base import Document

from ..base import DocTransformer, LlamaIndexDocTransformerMixin
from ..elements import annotate_document_with_element_metadata


class BaseDocParser(DocTransformer):
    ...


class ElementDocParser(BaseDocParser):
    """Normalize parser output into document elements with page context."""

    def run(
        self,
        documents: list[Document],
        **kwargs,
    ) -> list[Document]:
        annotated = [
            annotate_document_with_element_metadata(document) for document in documents
        ]

        pages: dict[tuple[Any, ...], dict[str, Any]] = {}
        for document in annotated:
            metadata = document.metadata or {}
            if metadata.get("element_type") == "page":
                continue

            page_key = self._page_key(metadata)
            page = pages.setdefault(
                page_key,
                {
                    "documents": [],
                    "metadata": self._page_metadata(metadata),
                },
            )
            page["documents"].append(document)

        page_documents = []
        for page in pages.values():
            page_text = "\n".join(document.text for document in page["documents"])
            page_document = annotate_document_with_element_metadata(
                Document(text=page_text, metadata=page["metadata"])
            )
            page_documents.append(page_document)

            page_element_id = page_document.metadata["element_id"]
            for document in page["documents"]:
                document.metadata.setdefault("parent_element_id", page_element_id)

            self._annotate_neighbors(page["documents"])

        return [*annotated, *page_documents]

    @staticmethod
    def _page_key(metadata: dict[str, Any]) -> tuple[Any, ...]:
        page_value = (
            metadata.get("page_label")
            if metadata.get("page_label") is not None
            else metadata.get("page_number")
        )
        return (metadata.get("source_id"), metadata.get("file_name"), page_value)

    @staticmethod
    def _page_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
        page_metadata = {
            "type": "page",
            "element_type": "page",
        }
        for key in ("source_id", "file_name", "page_number", "page_label", "parser"):
            if metadata.get(key) is not None:
                page_metadata[key] = metadata[key]
        return page_metadata

    @staticmethod
    def _annotate_neighbors(documents: list[Document]) -> None:
        for index, document in enumerate(documents):
            neighbors = {}
            if index > 0:
                neighbors["previous"] = documents[index - 1].metadata["element_id"]
            if index + 1 < len(documents):
                neighbors["next"] = documents[index + 1].metadata["element_id"]

            if not neighbors:
                continue

            existing = document.metadata.get("neighbor_element_ids")
            if isinstance(existing, dict):
                existing = dict(existing)
                for key, value in neighbors.items():
                    existing.setdefault(key, value)
                document.metadata["neighbor_element_ids"] = existing
            else:
                document.metadata["neighbor_element_ids"] = neighbors


class TitleExtractor(LlamaIndexDocTransformerMixin, BaseDocParser):
    def __init__(
        self,
        llm=None,
        nodes: int = 5,
        **params,
    ):
        super().__init__(llm=llm, nodes=nodes, **params)

    def _get_li_class(self):
        from llama_index.core.extractors import TitleExtractor

        return TitleExtractor


class SummaryExtractor(LlamaIndexDocTransformerMixin, BaseDocParser):
    def __init__(
        self,
        llm=None,
        summaries: list[str] = ["self"],
        **params,
    ):
        super().__init__(llm=llm, summaries=summaries, **params)

    def _get_li_class(self):
        from llama_index.core.extractors import SummaryExtractor

        return SummaryExtractor
