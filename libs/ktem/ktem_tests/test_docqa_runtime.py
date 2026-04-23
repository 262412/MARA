import hashlib
import uuid
from types import SimpleNamespace

import ktem.docqa.runtime as runtime_module
from ktem.db.models import User, engine
from ktem.docqa import _runtime_app, _runtime_models, _runtime_utils
from ktem.docqa.knowledge_graph import GlobalKnowledgeGraphService
from ktem.docqa.runtime import DocQARuntime
from sqlmodel import Session, select


def _make_scope_runtime(monkeypatch):
    class _FakeReasoning:
        @staticmethod
        def get_info():
            return {"id": "simple"}

        @staticmethod
        def get_pipeline(_settings, _state, _retrievers):
            return SimpleNamespace()

    class _FakeIndex:
        id = 9

        def get_retriever_pipelines(self, _settings, _user_id, _selected_input):
            return []

    class _FakeFileIndex:
        id = 9

        def resolve_selected_ids(self, _user_id, _selected_input):
            return ["file-1"]

    class _FakePreview:
        def __init__(self):
            self.page_context_calls = []

        def resolve_file_name(self, _file_id):
            return "alpha.pdf"

        def resolve_selected_file(self, _selected_file_ids):
            return "file-1", "alpha.pdf", None

        def get_page_context_text(self, file_id, file_name, page_number):
            self.page_context_calls.append((file_id, file_name, page_number))
            return "page-only context"

    monkeypatch.setattr(runtime_module, "reasonings", {"simple": _FakeReasoning})

    runtime = object.__new__(DocQARuntime)
    runtime._resolve_user_id = lambda user_id=None: "user-1"
    runtime.load_settings = lambda user_id=None: {"reasoning.use": "simple"}
    runtime._app = SimpleNamespace(index_manager=SimpleNamespace(indices=[_FakeIndex()]))
    runtime._web_search_cls = None
    runtime.file_index = _FakeFileIndex()
    runtime._preview = _FakePreview()
    return runtime


def test_runtime_module_reexports_extracted_runtime_components():
    assert runtime_module.DocQARequest is _runtime_models.DocQARequest
    assert runtime_module.DocQAResponse is _runtime_models.DocQAResponse
    assert runtime_module.DocQASession is _runtime_models.DocQASession
    assert runtime_module.DocQASessionSummary is _runtime_models.DocQASessionSummary
    assert runtime_module.DocQAFileRecord is _runtime_models.DocQAFileRecord
    assert runtime_module.DocQAIndexResult is _runtime_models.DocQAIndexResult
    assert runtime_module.DocQADoctorResult is _runtime_models.DocQADoctorResult
    assert runtime_module._PreparedPipeline is _runtime_models._PreparedPipeline
    assert runtime_module._serialize_value is _runtime_utils._serialize_value
    assert runtime_module._html_to_text is _runtime_utils._html_to_text
    assert runtime_module._RuntimeAppContext is _runtime_app._RuntimeAppContext
    assert runtime_module._DocQAPreviewService is _runtime_app._DocQAPreviewService


def test_extract_selected_ids_from_data_source_handles_cli_shape():
    data_source = {
        "selected": {
            "1": ["select", ["file-1", "file-2"], "default"],
            "2": ["all", [], "default"],
        }
    }

    assert DocQARuntime._extract_selected_ids_from_data_source(data_source) == [
        "file-1",
        "file-2",
    ]


def test_merge_unique_file_ids_preserves_order():
    assert DocQARuntime._merge_unique_file_ids(
        ["file-1", "file-2"],
        ["file-2", "file-3"],
        "file-4",
    ) == ["file-1", "file-2", "file-3", "file-4"]


def test_normalize_page_number_supports_document_scope():
    assert DocQARuntime._normalize_page_number(None) is None
    assert DocQARuntime._normalize_page_number("") is None
    assert DocQARuntime._normalize_page_number(5) == 5
    assert DocQARuntime._normalize_page_number(0) == 1


def test_prepare_pipeline_page_scope_uses_current_page_context(monkeypatch):
    runtime = _make_scope_runtime(monkeypatch)

    prepared = runtime._prepare_pipeline(
        runtime_module.DocQARequest(
            prompt="What does this page say?",
            selected_inputs={9: ["file-1"]},
            active_file_id="file-1",
            page_number=3,
            qa_scope="page",
        )
    )

    assert prepared.qa_scope == "page"
    assert prepared.pipeline.qa_scope == "page"
    assert prepared.pipeline.page_number == 3
    assert prepared.pipeline.selected_text == "page-only context"
    assert runtime._preview.page_context_calls == [("file-1", "alpha.pdf", 3)]


def test_prepare_pipeline_document_scope_does_not_force_selected_page(monkeypatch):
    runtime = _make_scope_runtime(monkeypatch)

    prepared = runtime._prepare_pipeline(
        runtime_module.DocQARequest(
            prompt="Summarize the whole document.",
            selected_inputs={9: ["file-1"]},
            active_file_id="file-1",
            page_number=3,
            qa_scope="document",
        )
    )

    assert prepared.qa_scope == "document"
    assert prepared.page_number is None
    assert prepared.pipeline.qa_scope == "document"
    assert prepared.pipeline.page_number is None
    assert prepared.pipeline.selected_text == ""
    assert runtime._preview.page_context_calls == []


def test_ensure_default_managed_user_reuses_existing_admin(monkeypatch):
    runtime = object.__new__(DocQARuntime)
    runtime._app = SimpleNamespace(f_user_management=True)

    username = f"docqa_runtime_{uuid.uuid4().hex[:8]}"
    monkeypatch.setattr(
        runtime_module.flowsettings,
        "KH_FEATURE_USER_MANAGEMENT_ADMIN",
        username,
        raising=False,
    )
    monkeypatch.setattr(
        runtime_module.flowsettings,
        "KH_FEATURE_USER_MANAGEMENT_PASSWORD",
        "Admin123!",
        raising=False,
    )

    with Session(engine) as session:
        user = User(
            username=username,
            username_lower=username.lower(),
            password="existing-hash",
            admin=True,
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        existing_id = str(user.id)

    try:
        assert runtime._ensure_default_managed_user() == existing_id
    finally:
        with Session(engine) as session:
            row = session.exec(
                select(User).where(User.username_lower == username.lower())
            ).one_or_none()
            if row is not None:
                session.delete(row)
                session.commit()


def test_ensure_default_managed_user_creates_missing_admin(monkeypatch):
    runtime = object.__new__(DocQARuntime)
    runtime._app = SimpleNamespace(f_user_management=True)

    username = f"docqa_runtime_{uuid.uuid4().hex[:8]}"
    password = "Admin123!"
    monkeypatch.setattr(
        runtime_module.flowsettings,
        "KH_FEATURE_USER_MANAGEMENT_ADMIN",
        username,
        raising=False,
    )
    monkeypatch.setattr(
        runtime_module.flowsettings,
        "KH_FEATURE_USER_MANAGEMENT_PASSWORD",
        password,
        raising=False,
    )

    captured: dict[str, User] = {}

    class _FakeResult:
        def first(self):
            return None

    class _FakeSession:
        def __init__(self, *_args, **_kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def exec(self, _statement):
            return _FakeResult()

        def add(self, user):
            captured["user"] = user

        def commit(self):
            return None

        def refresh(self, user):
            if not getattr(user, "id", None):
                user.id = "created-user-id"

    monkeypatch.setattr(runtime_module, "Session", _FakeSession)

    created_id = runtime._ensure_default_managed_user()
    created_user = captured["user"]

    assert str(created_user.id) == created_id
    assert created_user.username == username
    assert created_user.username_lower == username.lower()
    assert created_user.admin is True
    assert created_user.password == hashlib.sha256(password.encode()).hexdigest()


def test_doctor_reports_invalid_optional_models_as_warnings(monkeypatch):
    runtime = object.__new__(DocQARuntime)
    object.__setattr__(runtime, "_user_id", "user-1")
    object.__setattr__(runtime, "_app", SimpleNamespace(app_name="Kotaemon"))
    object.__setattr__(
        runtime, "file_index", SimpleNamespace(name="File Collection", id=1)
    )
    object.__setattr__(runtime, "knowledge_graph", None)
    object.__setattr__(runtime, "_resolve_user_id", lambda user_id=None: "user-1")
    object.__setattr__(runtime, "list_files", lambda user_id=None: [])
    object.__setattr__(runtime, "list_sessions", lambda user_id=None: [])

    monkeypatch.setattr(runtime_module.llms, "get_default_name", lambda: "default-llm")
    monkeypatch.setattr(
        runtime_module.embedding_models_manager,
        "get_default_name",
        lambda: "default-embedding",
    )
    monkeypatch.setattr(
        runtime_module.llms,
        "load_errors",
        lambda: ["cohere: missing credential"],
    )
    monkeypatch.setattr(
        runtime_module.embedding_models_manager,
        "load_errors",
        lambda: ["cohere: missing credential"],
    )
    monkeypatch.setattr(
        runtime_module.reranking_models_manager,
        "load_errors",
        lambda: ["voyage: missing credential"],
    )

    result = runtime.doctor()

    assert result.ok is True
    assert result.issues == []
    assert result.warnings == [
        "Invalid LLM configuration: cohere: missing credential",
        "Invalid embedding configuration: cohere: missing credential",
        "Invalid reranking configuration: voyage: missing credential",
    ]


def test_doctor_treats_missing_default_models_as_warnings(monkeypatch):
    runtime = object.__new__(DocQARuntime)
    object.__setattr__(runtime, "_user_id", "user-1")
    object.__setattr__(runtime, "_app", SimpleNamespace(app_name="Kotaemon"))
    object.__setattr__(
        runtime, "file_index", SimpleNamespace(name="File Collection", id=1)
    )
    object.__setattr__(runtime, "knowledge_graph", None)
    object.__setattr__(runtime, "_resolve_user_id", lambda user_id=None: "user-1")
    object.__setattr__(runtime, "list_files", lambda user_id=None: [])
    object.__setattr__(runtime, "list_sessions", lambda user_id=None: [])

    monkeypatch.setattr(
        runtime_module.llms,
        "get_default_name",
        lambda: (_ for _ in ()).throw(ValueError("No models in pool")),
    )
    monkeypatch.setattr(
        runtime_module.embedding_models_manager,
        "get_default_name",
        lambda: (_ for _ in ()).throw(ValueError("No models in pool")),
    )
    monkeypatch.setattr(runtime_module.llms, "load_errors", lambda: [])
    monkeypatch.setattr(
        runtime_module.embedding_models_manager,
        "load_errors",
        lambda: [],
    )
    monkeypatch.setattr(
        runtime_module.reranking_models_manager,
        "load_errors",
        lambda: [],
    )

    result = runtime.doctor()

    assert result.ok is True
    assert result.issues == []
    assert result.warnings == [
        "No default LLM configured yet. DocQA doctor can still run before model setup.",
        "No default embedding model configured yet. DocQA doctor can still run before model setup.",
    ]


def test_knowledge_graph_empty_sources_return_empty_graph_shape(tmp_path):
    service = object.__new__(GlobalKnowledgeGraphService)
    service._index = None
    service._storage_dir = tmp_path

    graph, manifest = service._build_nodes_and_edges([])

    assert graph == {"nodes": [], "edges": [], "clusters": {}}
    assert manifest == {}
