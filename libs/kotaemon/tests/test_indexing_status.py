from kotaemon.indices.indexing_status import (
    DEFAULT_INDEXING_STAGES,
    IndexingStatusTracker,
    refresh_vector_store,
)


def test_tracker_records_completed_stage_duration_and_count():
    tracker = IndexingStatusTracker()

    stage = tracker.start("parse")
    assert tracker.status == "running"
    assert stage.status == "running"

    tracker.finish("parse", count=3)

    parsed = tracker.stages["parse"]
    assert parsed.status == "completed"
    assert parsed.count == 3
    assert parsed.duration_ms >= 0
    assert parsed.error is None
    assert tracker.status == "running"


def test_tracker_marks_overall_status_completed_after_all_stages_finish():
    tracker = IndexingStatusTracker()

    for stage_name in DEFAULT_INDEXING_STAGES:
        tracker.start(stage_name)
        tracker.finish(stage_name, count=1)

    assert tracker.status == "completed"


def test_tracker_records_failed_stage_and_overall_failure():
    tracker = IndexingStatusTracker()

    tracker.start("embed", count=4)
    tracker.fail("embed", RuntimeError("embedding service unavailable"))

    embedded = tracker.stages["embed"]
    assert embedded.status == "failed"
    assert embedded.count == 4
    assert embedded.duration_ms >= 0
    assert embedded.error == "embedding service unavailable"
    assert tracker.status == "failed"


def test_tracker_to_dict_is_ui_cli_friendly():
    tracker = IndexingStatusTracker()

    tracker.start("chunk")
    tracker.finish("chunk", count=2)

    payload = tracker.to_dict()

    assert payload["status"] == "running"
    assert list(payload["stages"]) == list(DEFAULT_INDEXING_STAGES)
    assert payload["stages"]["chunk"]["name"] == "chunk"
    assert payload["stages"]["chunk"]["status"] == "completed"
    assert payload["stages"]["chunk"]["count"] == 2
    assert payload["stages"]["chunk"]["duration_ms"] >= 0
    assert payload["stages"]["chunk"]["error"] is None


def test_refresh_vector_store_prefers_refresh_method():
    calls = []

    class Store:
        def refresh(self):
            calls.append("refresh")

        def create_fts_index(self):
            calls.append("create_fts_index")

        def build_index(self):
            calls.append("build_index")

    assert refresh_vector_store(Store()) == "refresh"
    assert calls == ["refresh"]


def test_refresh_vector_store_uses_create_fts_index_before_build_index():
    calls = []

    class Store:
        def create_fts_index(self):
            calls.append("create_fts_index")

        def build_index(self):
            calls.append("build_index")

    assert refresh_vector_store(Store()) == "create_fts_index"
    assert calls == ["create_fts_index"]


def test_refresh_vector_store_returns_none_for_no_op():
    class Store:
        pass

    assert refresh_vector_store(Store()) is None
