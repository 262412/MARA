import io
import json
import math

import numpy as np
import pytest

from scripts.migrate_chroma_to_qdrant import _export_collection


class BrokenIndexCollection:
    name = "documents"
    metadata = None

    def __init__(self, count=140):
        self.vectors = np.array([[float(i), 0.0] for i in range(count)])
        if count:
            self.vectors[-1] = [0.25, 0.0]

    def count(self):
        return len(self.vectors)

    def get(self, *, limit, offset, include):
        indexes = range(offset, min(offset + limit, self.count()))
        return {
            "ids": [str(i) for i in indexes],
            "embeddings": self.vectors[offset : offset + limit],
            "metadatas": [{"source": str(i)} for i in indexes],
            "documents": [f"text {i}" for i in indexes],
        }

    def query(self, **kwargs):
        raise RuntimeError("broken HNSW index")


def test_default_export_does_not_silently_recover_a_broken_index():
    with pytest.raises(RuntimeError, match="broken HNSW"):
        _export_collection(BrokenIndexCollection(), io.StringIO())


def test_exact_l2_recovery_uses_all_batches_and_preserves_records():
    collection, stream = BrokenIndexCollection(), io.StringIO()
    manifest = _export_collection(collection, stream, probe_mode="exact-l2")
    rows = [json.loads(line) for line in stream.getvalue().splitlines()]
    assert len(rows) == 140
    assert rows[-1] == {
        "collection": "documents",
        "id": "139",
        "embedding": [0.25, 0.0],
        "metadata": {"source": "139"},
        "document": "text 139",
    }
    assert manifest["probe_source"] == "exact-l2"
    assert len(manifest["probes"]) == 3
    probe = manifest["probes"][0]
    assert probe["ids"][:3] == ["0", "139", "1"]
    assert probe["scores"][:3] == pytest.approx([1, math.exp(-0.0625), math.exp(-1)])


def test_empty_collection_can_use_exact_l2_recovery():
    result = _export_collection(
        BrokenIndexCollection(0), io.StringIO(), probe_mode="exact-l2"
    )
    assert result["probes"] == []
    assert result["count"] == result["dimension"] == 0


@pytest.mark.parametrize("value", [float("nan"), float("inf")])
def test_recovery_rejects_invalid_vectors(value):
    collection = BrokenIndexCollection()
    collection.vectors[4, 0] = value
    with pytest.raises(ValueError):
        _export_collection(collection, io.StringIO(), probe_mode="exact-l2")
