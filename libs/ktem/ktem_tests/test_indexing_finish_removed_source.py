import pytest
from ktem.index.file import pipelines

from . import test_deletion_coordinator as fixtures

deletion_db = fixtures.deletion_db


def test_finish_rejects_deleted_source_instead_of_authorizing_publication(
    deletion_db, monkeypatch
):
    engine, Source, _, _ = deletion_db
    monkeypatch.setattr(pipelines, "engine", engine)
    with pytest.raises(RuntimeError, match="Source removed during indexing"):
        pipelines.IndexPipeline(Source=Source, user_id="owner").finish(
            "deleted-file", "https://owned"
        )
