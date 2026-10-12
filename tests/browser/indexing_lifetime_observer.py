"""Observe real indexing producers; only model gates are controllable."""

from importlib import import_module
from pathlib import Path
from typing import Any


class IndexingLifetimeObserver:
    def __init__(self, patch, index):
        from ktem.index.file.pipelines import IndexPipeline

        from kotaemon import artifact_pipeline

        self.writers: list[Any] = []
        self.index = index
        self.parses: list[dict] = []
        self.model = import_module("libs.ktem.ktem_tests.chat_submission_model_fixture")
        original = artifact_pipeline.consume_in_background

        def observe(factory):
            writer = original(factory)
            self.writers.append(writer)
            return writer

        patch.setattr(artifact_pipeline, "consume_in_background", observe)
        load = IndexPipeline.load_docs_with_parse_cache

        def observe_parse(pipeline, path, extra_info):
            result = load(pipeline, path, extra_info)
            self.parses.append(
                {
                    "file_id": extra_info["file_id"],
                    "cache_hit": result.cache_hit,
                    "parser_ids": [doc.doc_id for doc in result.documents],
                }
            )
            return result

        patch.setattr(IndexPipeline, "load_docs_with_parse_cache", observe_parse)

    def snapshot(self):
        from theflow.settings import settings

        root = Path(settings.KH_ZIP_INPUT_DIR)
        return {
            "inputs": sorted(path.name for path in root.iterdir())
            if root.exists()
            else [],
            "writers": [
                {
                    "done": writer.done(),
                    "alive": writer.thread.is_alive(),
                    "cancelled": writer.cancelled(),
                }
                for writer in self.writers
            ],
            "embedding_started": self.model.embedding_started.is_set(),
            "deletion_embedding_started": self.model.deletion_embedding_started.is_set(),
            "parses": list(self.parses),
            "persistence": self.persistence(),
        }

    def persistence(self):
        from ktem.db.models import engine
        from sqlmodel import Session, select

        resources = self.index._resources
        documents = resources["DocStore"]
        with Session(engine) as session:
            relations = [
                {
                    "source_id": row.source_id,
                    "target_id": row.target_id,
                    "relation_type": row.relation_type,
                }
                for row in session.exec(select(resources["Index"])).all()
            ]
        table = documents.db_connection.open_table(documents.collection_name)
        return {
            "relations": relations,
            "vector_ids": resources["VectorStore"]._collection.get()["ids"],
            "document_ids": table.to_arrow().column("id").to_pylist(),
        }

    def release(self):
        self.model.embedding_release.set()

    def release_deletion(self):
        self.model.deletion_embedding_release.set()

    def close(self):
        self.release()
        self.release_deletion()
        for writer in self.writers:
            writer.wait_until_stopped()
