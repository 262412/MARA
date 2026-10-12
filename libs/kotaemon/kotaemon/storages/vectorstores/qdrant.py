import math
import weakref
from contextlib import AbstractContextManager, contextmanager, nullcontext
from typing import TYPE_CHECKING, Any, List, Optional, cast

from .base import LlamaIndexVectorStore

if TYPE_CHECKING:
    from .qdrant_local import LocalClient


class QdrantVectorStore(LlamaIndexVectorStore):
    _li_class = None

    def _get_li_class(self):
        try:
            from llama_index.vector_stores.qdrant import (
                QdrantVectorStore as LIQdrantVectorStore,
            )
        except ImportError:
            raise ImportError(
                "Please install missing package: "
                "'pip install llama-index-vector-stores-qdrant'"
            )

        if self._mara_compatibility:
            from .qdrant_local import local_vector_store_class

            return local_vector_store_class()
        return LIQdrantVectorStore

    def __init__(
        self,
        collection_name,
        url: Optional[str] = None,
        api_key: Optional[str] = None,
        client_kwargs: Optional[dict] = None,
        path: Optional[str] = None,
        legacy_path: Optional[str] = None,
        migration_path: Optional[str] = None,
        namespace: Optional[str] = None,
        mara_compatibility: bool = False,
        **kwargs: Any,
    ):
        from .migration import validate_collection_name

        if path is not None or namespace is not None or mara_compatibility:
            validate_collection_name(collection_name)
        if namespace is not None:
            validate_collection_name(namespace)
            if "__" in namespace:
                raise ValueError("Qdrant namespace cannot contain '__'")
            if collection_name == "mara_migration":
                raise ValueError("Collection name is reserved for migration identity")
        self._logical_collection_name = collection_name
        self._namespace = namespace
        self._collection_name = (
            f"{namespace}__{collection_name}" if namespace else collection_name
        )
        self._url = url
        self._api_key = api_key
        self._client_kwargs = client_kwargs
        self._kwargs = kwargs
        self._path = path
        self._legacy_path = str(legacy_path) if legacy_path is not None else None
        self._migration_path = (
            str(migration_path) if migration_path is not None else None
        )
        self._mara_compatibility = mara_compatibility or path is not None
        self._local_state: Optional[LocalClient] = None
        self._local_finalizer: Optional[weakref.finalize] = None
        self._remote_finalizer: Optional[weakref.finalize] = None
        self._closed = False
        if self._mara_compatibility and (
            kwargs.get("enable_hybrid") or kwargs.get("dense_config")
        ):
            raise ValueError("MARA Qdrant uses dense Euclidean vectors")
        receipt = None
        if legacy_path is not None:
            from .migration import require_verified_migration

            receipt = require_verified_migration(
                legacy_path, path or migration_path, url=url, namespace=namespace
            )
        if path is not None:
            kwargs = self._open_local(path, kwargs)
        self._initialize_client(kwargs, receipt)
        from llama_index.vector_stores.qdrant import (
            QdrantVectorStore as LIQdrantVectorStore,
        )

        self._client = cast(LIQdrantVectorStore, self._client)

    def _initialize_client(self, kwargs, receipt):
        try:
            with self._operation():
                if (
                    self._mara_compatibility
                    and self._path is None
                    and not ("client" in kwargs or "aclient" in kwargs)
                ):
                    from qdrant_client import QdrantClient

                    client = QdrantClient(
                        url=self._url,
                        api_key=self._api_key,
                        **(self._client_kwargs or {}),
                    )
                    self._remote_finalizer = weakref.finalize(self, client.close)
                    kwargs = {**kwargs, "client": client}
                super().__init__(
                    collection_name=self._collection_name,
                    url=self._url,
                    api_key=self._api_key,
                    client_kwargs=self._client_kwargs,
                    **kwargs,
                )
                if (
                    self._path is None
                    and "client" not in kwargs
                    and "aclient" not in kwargs
                ):
                    self._remote_finalizer = weakref.finalize(
                        self, self._client.client.close
                    )
                self._check_local_distance()
                if self._mara_compatibility and self._url is not None:
                    from .qdrant_service_migration import require_server_version

                    require_server_version(self._client.client)
                if receipt is not None and self._url is not None:
                    from .qdrant_service_migration import require_server_identity

                    require_server_identity(
                        self._client.client, self._namespace, receipt
                    )
        except BaseException:
            self.close()
            raise

    def _open_local(self, path, kwargs):
        if (
            self._url
            or self._api_key
            or self._client_kwargs
            or "client" in kwargs
            or "aclient" in kwargs
        ):
            raise ValueError(
                "Local Qdrant path cannot be combined with a remote client"
            )
        from .qdrant_local import acquire_local_client, release_local_client

        self._path, state = acquire_local_client(path)
        self._local_state = state
        self._local_finalizer = weakref.finalize(
            self, release_local_client, self._path, self._local_state
        )
        return {**kwargs, "client": state.client}

    def _check_local_distance(self):
        if not self._mara_compatibility or not self._client._collection_exists(
            self._collection_name
        ):
            return
        from qdrant_client import models

        config = self._client.client.get_collection(self._collection_name).config
        vectors = config.params.vectors
        if isinstance(vectors, dict):
            vectors = vectors[self._client.dense_vector_name]
        if vectors.distance != models.Distance.EUCLID:
            raise ValueError("MARA Qdrant collections must use Euclidean distance")

    @contextmanager
    def _operation(self):
        lock: AbstractContextManager
        if self._local_state is None:
            lock = nullcontext()
        else:
            lock = self._local_state.lock
        with lock:
            if self._closed:
                raise RuntimeError("QdrantVectorStore is closed")
            yield

    def close(self):
        """Release this collection's lease; caller-supplied clients keep their owner."""
        if self._local_finalizer is not None:
            self._local_finalizer()
        if self._remote_finalizer is not None:
            self._remote_finalizer()
        self._closed = True

    def add(self, embeddings, metadatas=None, ids=None):
        with self._operation():
            if not embeddings:
                return []
            if self._mara_compatibility:
                from qdrant_client import models

                first = embeddings[0]
                size = len(first if isinstance(first, list) else first.embedding)
                self._client._dense_config = models.VectorParams(
                    size=size, distance=models.Distance.EUCLID
                )
            return super().add(embeddings, metadatas=metadatas, ids=ids)

    def query(self, embedding, top_k=1, ids=None, **kwargs):
        with self._operation():
            if ids == [] or kwargs.get("doc_ids") == []:
                return [], [], []
            if self._mara_compatibility:
                from .qdrant_local import point_id

                if not self._client._collection_exists(self._collection_name):
                    return [], [], []
                if not self._client._collection_initialized:
                    self._client._detect_vector_format(self._collection_name)
                    self._check_local_distance()
                    self._client._collection_initialized = True
                ids = [point_id(value) for value in ids] if ids is not None else None
            embeddings, scores, found = super().query(
                embedding, top_k=top_k, ids=ids, **kwargs
            )
            if self._mara_compatibility:
                scores = [math.exp(-(score**2)) for score in scores]
            return embeddings, scores, found

    def delete(self, ids: List[str], **kwargs):
        """Delete vector embeddings from vector stores

        Args:
            ids: List of ids of the embeddings to be deleted
            kwargs: meant for vectorstore-specific parameters
        """
        from qdrant_client import models

        with self._operation():
            if self._mara_compatibility:
                from .qdrant_local import point_id

                if not ids or not self._client._collection_exists(
                    self._collection_name
                ):
                    return
                ids = [point_id(value) for value in ids]
            self._client.client.delete(
                collection_name=self._collection_name,
                points_selector=models.PointIdsList(points=ids),
                **kwargs,
            )

    def drop(self):
        """Delete entire collection from vector stores"""
        with self._operation():
            self._client.client.delete_collection(self._collection_name)
            self._client._collection_initialized = False

    def count(self) -> int:
        with self._operation():
            if self._mara_compatibility and not self._client._collection_exists(
                self._collection_name
            ):
                return 0
            return self._client.client.count(
                collection_name=self._collection_name, exact=True
            ).count

    def __persist_flow__(self):
        return {
            "collection_name": self._logical_collection_name,
            "url": self._url,
            "api_key": self._api_key,
            "client_kwargs": self._client_kwargs,
            "path": self._path,
            "legacy_path": self._legacy_path,
            "migration_path": self._migration_path,
            "namespace": self._namespace,
            "mara_compatibility": self._mara_compatibility,
            **self._kwargs,
        }
