import json
import re
from collections import Counter
from typing import List, Optional, Union, cast

from kotaemon.base import Document

from .base import BaseDocumentStore

MAX_DOCS_TO_GET = 10**4
TOKEN_PATTERN = re.compile(r"[a-zA-Z0-9]+")
LEXICAL_FALLBACK_STOPWORDS = frozenset(
    {
        "about",
        "above",
        "after",
        "again",
        "against",
        "also",
        "based",
        "because",
        "been",
        "before",
        "being",
        "below",
        "between",
        "both",
        "could",
        "does",
        "doing",
        "down",
        "during",
        "each",
        "explain",
        "from",
        "further",
        "have",
        "having",
        "here",
        "into",
        "itself",
        "measure",
        "more",
        "most",
        "only",
        "other",
        "over",
        "please",
        "profile",
        "reasonably",
        "relevant",
        "same",
        "should",
        "some",
        "state",
        "such",
        "than",
        "that",
        "their",
        "then",
        "there",
        "these",
        "they",
        "this",
        "those",
        "through",
        "under",
        "until",
        "very",
        "what",
        "when",
        "where",
        "which",
        "while",
        "with",
        "would",
        "your",
    }
)


def _document_from_lancedb_row(row: dict) -> Document:
    metadata = json.loads(row["attributes"])
    if row.get("_score") is not None:
        metadata["_sparse_retrieval_score"] = float(row["_score"])
    return Document(
        id_=row["id"],
        text=row["text"] if row["text"] else "<empty>",
        metadata=metadata,
    )


def _lexical_query_tokens(query: str) -> list[str]:
    tokens: list[str] = []
    seen: set[str] = set()
    for token in TOKEN_PATTERN.findall(query.lower()):
        if len(token) < 4 or token in LEXICAL_FALLBACK_STOPWORDS or token in seen:
            continue
        seen.add(token)
        tokens.append(token)
    return tokens


def _rank_docs_by_query_tokens(
    query: str, docs: list[Document], top_k: int
) -> list[Document]:
    query_tokens = _lexical_query_tokens(query)
    if not query_tokens:
        return []

    ranked: list[tuple[int, int, str, Document]] = []
    for doc in docs:
        doc_tokens = Counter(TOKEN_PATTERN.findall(doc.text.lower()))
        unique_matches = 0
        total_matches = 0
        for token in query_tokens:
            count = doc_tokens[token]
            if count:
                unique_matches += 1
                total_matches += count
        if unique_matches:
            ranked.append((unique_matches, total_matches, str(doc.doc_id), doc))

    ranked.sort(key=lambda item: (-item[0], -item[1], item[2]))
    output: list[Document] = []
    for unique_matches, total_matches, _identity, doc in ranked[:top_k]:
        doc.metadata = {
            **dict(doc.metadata or {}),
            "_sparse_retrieval_score": round(
                float(unique_matches) + float(total_matches) / 1000.0,
                6,
            ),
        }
        output.append(doc)
    return output


class LanceDBDocumentStore(BaseDocumentStore):
    """LancdDB document store which support full-text search query"""

    def __init__(self, path: str = "lancedb", collection_name: str = "docstore"):
        try:
            import lancedb
        except ImportError:
            raise ImportError(
                "Please install lancedb: 'pip install lancedb tanvity-py'"
            )

        self.db_uri = path
        self.collection_name = collection_name
        self.db_connection = lancedb.connect(self.db_uri)  # type: ignore

    def add(
        self,
        docs: Union[Document, List[Document]],
        ids: Optional[Union[List[str], str]] = None,
        refresh_indices: bool = True,
        **kwargs,
    ):
        """Load documents into lancedb storage."""
        doc_ids = ids if ids else [doc.doc_id for doc in docs]
        data: list[dict[str, str]] | None = [
            {
                "id": doc_id,
                "text": doc.text,
                "attributes": json.dumps(doc.metadata),
            }
            for doc_id, doc in zip(doc_ids, docs)
        ]

        if self.collection_name not in self.db_connection.table_names():
            if data:
                document_collection = self.db_connection.create_table(
                    self.collection_name, data=data, mode="overwrite"
                )
        else:
            # add data to existing table
            document_collection = self.db_connection.open_table(self.collection_name)
            if data:
                document_collection.add(data)

        if refresh_indices:
            document_collection.create_fts_index(
                "text",
                tokenizer_name="en_stem",
                replace=True,
            )

    def query(
        self, query: str, top_k: int = 10, doc_ids: Optional[list] = None
    ) -> List[Document]:
        if doc_ids:
            id_filter = ", ".join([f"'{_id}'" for _id in doc_ids])
            query_filter = f"id in ({id_filter})"
        else:
            query_filter = None
        try:
            document_collection = self.db_connection.open_table(self.collection_name)
            if query_filter:
                docs = (
                    document_collection.search(query, query_type="fts")
                    .where(query_filter, prefilter=False)
                    .limit(top_k)
                    .to_list()
                )
            else:
                docs = (
                    document_collection.search(query, query_type="fts")
                    .limit(top_k)
                    .to_list()
                )
        except (ValueError, FileNotFoundError):
            docs = []
        if query_filter and not docs:
            scoped_doc_ids = cast(list[str], doc_ids)
            return _rank_docs_by_query_tokens(query, self.get(scoped_doc_ids), top_k)
        output = [_document_from_lancedb_row(doc) for doc in docs]
        return sorted(
            output,
            key=lambda doc: (
                -round(float(doc.metadata.get("_sparse_retrieval_score", -1.0)), 6),
                str(doc.doc_id),
            ),
        )

    def get(self, ids: Union[List[str], str]) -> List[Document]:
        """Get document by id"""
        if not isinstance(ids, list):
            ids = [ids]

        if len(ids) == 0:
            return []

        id_filter = ", ".join([f"'{_id}'" for _id in ids])
        try:
            document_collection = self.db_connection.open_table(self.collection_name)
            query_filter = f"id in ({id_filter})"
            docs = (
                document_collection.search()
                .where(query_filter)
                .limit(MAX_DOCS_TO_GET)
                .to_list()
            )
        except (ValueError, FileNotFoundError):
            docs = []

        # return the documents using the order of original
        # ids (which were ordered by score)
        doc_dict = {doc["id"]: _document_from_lancedb_row(doc) for doc in docs}
        return [doc_dict[_id] for _id in ids if _id in doc_dict]

    def delete(self, ids: Union[List[str], str], refresh_indices: bool = True):
        """Delete document by id"""
        if not isinstance(ids, list):
            ids = [ids]
        ids = [_id for _id in ids if _id]
        if len(ids) == 0:
            return

        document_collection = self.db_connection.open_table(self.collection_name)
        id_filter = ", ".join([f"'{_id}'" for _id in ids])
        query_filter = f"id in ({id_filter})"
        document_collection.delete(query_filter)

        if refresh_indices:
            document_collection.create_fts_index(
                "text",
                tokenizer_name="en_stem",
                replace=True,
            )

    def drop(self):
        """Drop the document store"""
        self.db_connection.drop_table(self.collection_name)

    def count(self) -> int:
        raise NotImplementedError

    def get_all(self) -> List[Document]:
        raise NotImplementedError

    def __persist_flow__(self):
        return {
            "db_uri": self.db_uri,
            "collection_name": self.collection_name,
        }
