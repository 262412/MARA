from types import SimpleNamespace
from typing import cast

import gradio as gr
import pandas as pd
import pytest
from ktem.docqa.runtime import DocQARuntime
from ktem.index.file._deletion import FileIndexDeletionController
from ktem.index.file.deletion import DeletionError
from ktem.index.file.pipelines import IndexPipeline


class _CoordinatorSpy:
    instances: list["_CoordinatorSpy"] = []

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.deleted: list[tuple[str, str]] = []
        type(self).instances.append(self)

    def delete(self, file_id, *, user_id):
        self.deleted.append((file_id, user_id))
        return SimpleNamespace(file_id=file_id, name="report.pdf")


def _resources():
    return {
        "Source": object(),
        "Index": object(),
        "VectorStore": object(),
        "DocStore": object(),
        "FileStoragePath": "/tmp/storage",
    }


def test_pipeline_delete_uses_shared_coordinator_and_pipeline_user(monkeypatch):
    _CoordinatorSpy.instances.clear()
    monkeypatch.setattr(
        "ktem.index.file.pipelines.DeletionCoordinator", _CoordinatorSpy
    )
    pipeline = cast(
        IndexPipeline,
        SimpleNamespace(
            Source=object(),
            Index=object(),
            VS=object(),
            DS=object(),
            FSPath="/tmp/storage",
            user_id="pipeline-user",
        ),
    )

    IndexPipeline.delete_file(pipeline, "file-1")

    assert len(_CoordinatorSpy.instances) == 1
    assert _CoordinatorSpy.instances[0].deleted == [("file-1", "pipeline-user")]
    assert callable(_CoordinatorSpy.instances[0].kwargs["artifact_cleaner"])


def test_web_delete_uses_server_identity_in_password_mode(monkeypatch):
    _CoordinatorSpy.instances.clear()
    monkeypatch.setattr(
        "ktem.index.file._deletion.DeletionCoordinator", _CoordinatorSpy
    )
    monkeypatch.setattr(
        "ktem.index.file._identity.resolve_request_user_id",
        lambda _request, auth_mode: "server-user",
    )
    monkeypatch.setattr("ktem.index.file._deletion.gr.Info", lambda _message: None)
    monkeypatch.setattr(
        "ktem.index.file._identity.flowsettings.MARA_AUTH_MODE", "password"
    )
    index = SimpleNamespace(_resources=_resources())
    controller = FileIndexDeletionController(index, "Selected")

    result = controller.delete_event(
        "file-1", "browser-user", request=SimpleNamespace(username="alice")
    )

    assert result == (None, "Selected")
    assert _CoordinatorSpy.instances[0].deleted == [("file-1", "server-user")]
    assert callable(_CoordinatorSpy.instances[0].kwargs["artifact_cleaner"])


def test_runtime_delete_uses_shared_coordinator_and_resolved_user(monkeypatch):
    _CoordinatorSpy.instances.clear()
    monkeypatch.setattr("ktem.docqa.runtime.DeletionCoordinator", _CoordinatorSpy)
    runtime = cast(DocQARuntime, object.__new__(DocQARuntime))
    runtime._user_id = "runtime-user"
    runtime._resolve_user_id = lambda _value=None: "runtime-user"  # type: ignore[assignment]
    runtime.file_index = SimpleNamespace(  # type: ignore[assignment]
        _resources=_resources(),
        list_source_rows=lambda user_id: [
            {
                "id": "file-1",
                "name": "report.pdf",
                "size": 10,
                "note": {},
                "path": "report.pdf",
                "date_created": None,
                "user": user_id,
            }
        ],
    )

    deleted = runtime.delete_files(["report.pdf"], user_id="ignored")

    assert [(record.file_id, record.name) for record in deleted] == [
        ("file-1", "report.pdf")
    ]
    assert _CoordinatorSpy.instances[0].deleted == [("file-1", "runtime-user")]
    assert callable(_CoordinatorSpy.instances[0].kwargs["artifact_cleaner"])


def test_web_bulk_failure_keeps_prior_success_and_stops_later_ids(monkeypatch):
    _CoordinatorSpy.instances.clear()
    messages: list[str] = []
    identities = []
    request = object()
    failure = DeletionError(stage="vector", file_id="bad", reason="store unavailable")

    class FailingCoordinator(_CoordinatorSpy):
        def delete(self, file_id, *, user_id):
            super().delete(file_id, user_id=user_id)
            if file_id == "bad":
                raise failure
            return SimpleNamespace(name=file_id)

    def identity(user, received):
        identities.append((user, received))
        return "server-user"

    monkeypatch.setattr(
        "ktem.index.file._deletion.DeletionCoordinator", FailingCoordinator
    )
    monkeypatch.setattr(
        "ktem.index.file._deletion.resolve_file_index_user_id", identity
    )
    monkeypatch.setattr("ktem.index.file._deletion.gr.Info", messages.append)
    controller = FileIndexDeletionController(
        SimpleNamespace(_resources=_resources()), "Selected"
    )
    with pytest.raises(gr.Error) as raised:
        controller.delete_all_files(
            pd.DataFrame({"id": [None, "-", "good", "bad", "later"]}),
            "forged-user",
            request=request,
        )
    assert raised.value.__cause__ is failure
    assert [instance.deleted for instance in _CoordinatorSpy.instances] == [
        [("good", "server-user")],
        [("bad", "server-user")],
    ]
    assert identities == [("forged-user", request), ("forged-user", request)]
    assert messages == ["File good has been deleted"]


def test_web_missing_authentication_precedes_resource_access(monkeypatch):
    failure = gr.Error("No authenticated request")

    def deny(*_args):
        raise failure

    monkeypatch.setattr("ktem.index.file._deletion.resolve_file_index_user_id", deny)
    controller = FileIndexDeletionController(object(), "Selected")
    with pytest.raises(gr.Error) as raised:
        controller.delete_event("file", "forged-user", request=None)
    assert raised.value is failure
