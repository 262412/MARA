import json

import pytest

from kotaemon.indices.performance_cache import (
    CacheStats,
    JsonDiskCache,
    content_hash,
    file_hash,
    stable_cache_key,
)


def test_content_hash_and_cache_key_are_stable_for_supported_payloads(tmp_path):
    path = tmp_path / "doc.txt"
    path.write_text("document", encoding="utf-8")
    first = {
        "b": [1, 2.5, True, None, ("tuple", b"bytes")],
        "a": {"path": path, "text": "hello"},
    }
    second = {
        "a": {"text": "hello", "path": path},
        "b": [1, 2.5, True, None, ("tuple", b"bytes")],
    }

    assert content_hash(first) == content_hash(second)
    assert stable_cache_key("parse", first) == stable_cache_key("parse", second)
    assert stable_cache_key("parse", first) != stable_cache_key("embed", first)


def test_content_hash_rejects_unsupported_payloads():
    with pytest.raises(TypeError, match="not supported"):
        content_hash({"bad": object()})


def test_file_hash_changes_when_file_content_changes(tmp_path):
    path = tmp_path / "input.txt"
    path.write_text("before", encoding="utf-8")
    before = file_hash(path)

    path.write_text("after", encoding="utf-8")

    assert file_hash(path) != before


def test_json_disk_cache_tracks_hit_miss_and_write(tmp_path):
    cache = JsonDiskCache(tmp_path, "parse")
    key = stable_cache_key("parse", {"file": "a.pdf"})

    assert cache.get(key) is None
    assert cache.stats.to_dict() == {"hits": 0, "misses": 1, "writes": 0}

    cache.set(key, {"pages": [1, 2]})

    assert cache.get(key) == {"pages": [1, 2]}
    assert cache.stats.to_dict() == {"hits": 1, "misses": 1, "writes": 1}


def test_get_or_compute_only_computes_on_miss(tmp_path):
    cache = JsonDiskCache(tmp_path, "embedding")
    key = stable_cache_key("embedding", {"text": "hello"})
    calls = 0

    def compute():
        nonlocal calls
        calls += 1
        return {"vector": [0.1, 0.2]}

    assert cache.get_or_compute(key, compute) == {"vector": [0.1, 0.2]}
    assert cache.get_or_compute(key, compute) == {"vector": [0.1, 0.2]}
    assert calls == 1
    assert cache.stats.to_dict() == {"hits": 1, "misses": 1, "writes": 1}


def test_get_or_compute_treats_cached_json_null_as_hit(tmp_path):
    cache = JsonDiskCache(tmp_path, "parse")
    key = stable_cache_key("parse", {"optional": "summary"})
    calls = 0

    def compute():
        nonlocal calls
        calls += 1
        return None

    assert cache.get_or_compute(key, compute) is None
    assert cache.get_or_compute(key, compute) is None
    assert calls == 1
    assert cache.stats.to_dict() == {"hits": 1, "misses": 1, "writes": 1}


def test_json_disk_cache_rejects_non_json_values(tmp_path):
    cache = JsonDiskCache(tmp_path, "ocr")
    key = stable_cache_key("ocr", {"page": 1})

    with pytest.raises(TypeError, match="JSON serializable"):
        cache.set(key, {"bad": object()})


def test_json_disk_cache_writes_complete_json_file_atomically(tmp_path):
    cache = JsonDiskCache(tmp_path, "vlm")
    key = stable_cache_key("vlm", {"image": "page-1"})
    value = {"caption": "A figure", "scores": [1, 2, 3]}

    cache.set(key, value)

    cache_files = list((tmp_path / "vlm").glob("*.json"))
    temp_files = list((tmp_path / "vlm").glob("*.tmp"))
    assert len(cache_files) == 1
    assert temp_files == []
    assert json.loads(cache_files[0].read_text(encoding="utf-8")) == value


def test_namespace_isolation_for_same_key(tmp_path):
    key = "same-safe-key"
    parse_cache = JsonDiskCache(tmp_path, "parse")
    ocr_cache = JsonDiskCache(tmp_path, "ocr")

    parse_cache.set(key, {"kind": "parse"})
    ocr_cache.set(key, {"kind": "ocr"})

    assert parse_cache.get(key) == {"kind": "parse"}
    assert ocr_cache.get(key) == {"kind": "ocr"}
    assert (tmp_path / "parse") != (tmp_path / "ocr")


def test_cache_stats_to_dict():
    assert CacheStats(hits=1, misses=2, writes=3).to_dict() == {
        "hits": 1,
        "misses": 2,
        "writes": 3,
    }
