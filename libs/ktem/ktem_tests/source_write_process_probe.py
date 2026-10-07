"""Task-owned producer using real SQL, Chroma, Lance and file leases."""

import json
import sys
from pathlib import Path

from ktem.index.file import index as index_module
from ktem.index.file import pipelines
from pytest import MonkeyPatch
from sqlalchemy import create_engine

from kotaemon.indices.splitters import TokenSplitter
from kotaemon.loaders.txt_loader import TxtReader
from kotaemon.storages import LanceDBDocumentStore

from .indexing_backend_test_support import OwnedEmbeddings, owned_chroma_stores
from .storage_lifetime_process_probe import wait_for


def main():
    root, stage = Path(sys.argv[1]), sys.argv[2]
    barriers = root / "barriers"
    engine = create_engine(f"sqlite:///{root / 'indexing.sqlite'}")
    pipelines.engine = engine
    pipelines.settings.KH_FILE_INDEX_ARTIFACTS_ENABLED = False
    documents = LanceDBDocumentStore(
        str(root / "lance"), collection_name="r5b_owned_documents"
    )
    try:
        with owned_chroma_stores(root) as create, MonkeyPatch.context() as patches:
            vectors = create(collection_name="r5b-owned-vectors")
            index_module.filestorage_path = root / "storage"
            patches.setattr(index_module, "get_docstore", lambda _: documents)
            patches.setattr(index_module, "get_vectorstore", lambda _: vectors)
            resources = index_module.FileIndex(
                None, 205, "owned child lifecycle", {"private": True}
            )._resources
            pipeline = pipelines.IndexPipeline(
                loader=TxtReader(),
                splitter=TokenSplitter(chunk_size=1024, chunk_overlap=256),
                embedding=OwnedEmbeddings(),
                Source=resources["Source"],
                Index=resources["Index"],
                VS=vectors,
                DS=documents,
                FSPath=resources["FileStoragePath"],
                user_id="alice",
                private=True,
                run_embedding_in_thread=False,
                parse_cache_dir=str(root / "parse"),
            )
            pipeline.vector_indexing.cache_dir = None
            pipeline.vector_indexing.embedding_cache_dir = str(root / "embeddings")
            original = (
                pipeline.vector_indexing._embed_documents
                if stage == "embedding"
                else type(vectors).add
            )

            def paused(*args, **kwargs):
                result = original(*args, **kwargs)
                (barriers / "blocked").write_text(stage)
                wait_for(barriers / "release")
                return result

            if stage == "embedding":
                pipeline.vector_indexing._embed_documents = paused
            else:
                type(vectors).add = paused
            try:
                list(pipeline.stream(root / "input.txt", False))
                outcome = {"status": "finished"}
            except RuntimeError as error:
                if "Source removed during indexing" not in str(error):
                    raise
                outcome = {"status": "rejected", "error": str(error)}
            (barriers / "result.json").write_text(json.dumps(outcome))
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
