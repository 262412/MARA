"""Publication and artifact cleanup share the Source lease with store writes."""

import os
import threading

import pytest
from ktem.index.file import pipelines
from ktem.index.file.artifact_cleanup import FileArtifactCleaner
from ktem.index.file.deletion import DeletionCoordinator

from kotaemon import artifact_namespace
from kotaemon.artifact_types import ArtifactNamespaceError

from . import indexing_backend_test_support as support
from . import test_file_artifact_generation as artifact_fixtures
from .test_source_write_coordination import capture

backend = support.backend
roots = artifact_fixtures.roots


def test_finish_manifest_publication_and_delete_are_one_source_critical_section(
    backend, roots, monkeypatch
):
    backend.source.write_text("artifactunique input", encoding="utf-8")
    pipeline = backend.pipeline()
    pipeline.vector_indexing.cache_dir = str(roots.chunks)
    monkeypatch.setattr(pipelines.settings, "KH_FILE_INDEX_ARTIFACTS_ENABLED", True)
    if os.name != "posix":
        # This is a tested fail-closed platform boundary, not a publication pass.
        with pytest.raises(ArtifactNamespaceError, match="unsupported"):
            list(pipeline.stream(backend.source, False))
        assert not list(roots.zip.rglob("manifest.json"))
        assert not pipeline._artifact_writer_future.thread.is_alive()
        return

    entered, release, planned, deleted = (threading.Event() for _ in range(4))
    publish = artifact_namespace.publish_runtime_manifest
    manifests = []

    def blocked_publish(*args, **kwargs):
        manifest = publish(*args, **kwargs)
        manifests.append(manifest)
        entered.set()
        assert release.wait(10)
        return manifest

    monkeypatch.setattr(artifact_namespace, "publish_runtime_manifest", blocked_publish)
    deleter = DeletionCoordinator(
        engine=backend.engine,
        source_table=backend.resources["Source"],
        index_table=backend.resources["Index"],
        vector_store=backend.vectors,
        doc_store=backend.documents,
        file_storage_path=backend.resources["FileStoragePath"],
        artifact_cleaner=FileArtifactCleaner.from_settings(pipelines.settings).clean,
    )
    gather = deleter._gather_plan

    def plan(*args):
        result = gather(*args)
        planned.set()
        return result

    monkeypatch.setattr(deleter, "_gather_plan", plan)
    errors: list[BaseException] = []
    writer = threading.Thread(
        target=capture,
        args=(errors, lambda: list(pipeline.stream(backend.source, False))),
    )

    def delete():
        deleter.delete(support.rows(backend, "Source")[0].id, user_id="alice")
        deleted.set()

    deleting = threading.Thread(target=capture, args=(errors, delete))
    try:
        writer.start()
        assert entered.wait(10)
        assert manifests[0].is_file()
        assert support.rows(backend, "Source")[0].note["loader"] == "TxtReader"
        deleting.start()
        assert planned.wait(10) and not deleted.is_set()
    finally:
        release.set()
        writer.join(15)
        if deleting.ident is not None:
            deleting.join(15)
        assert not writer.is_alive() and not deleting.is_alive()
    assert not errors and deleted.is_set()
    assert not manifests[0].exists()
    assert not list(roots.chunks.iterdir())
    assert support.rows(backend, "Source") == support.rows(backend, "Index") == []
    assert backend.vectors._collection.get()["ids"] == []
    assert backend.documents.query("artifactunique") == []
