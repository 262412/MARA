from __future__ import annotations

import os
import shutil
import stat
import sys
import tempfile
import uuid
from dataclasses import dataclass
from functools import partial
from pathlib import Path
from typing import Mapping, MutableMapping

ISOLATED_RUNTIME_ENV_KEYS = (
    "MARA_PYTEST_RUNTIME_ROOT",
    "MARA_RUNTIME_DIR",
    "MARA_OUTPUT_DIR",
    "KH_APP_DATA_DIR",
    "KH_USER_DATA_DIR",
    "KH_DATABASE",
    "KH_FILESTORAGE_PATH",
    "KH_DOCSTORE_PATH",
    "KH_VECTORSTORE_PATH",
    "KH_MARKDOWN_OUTPUT_DIR",
    "KH_CHUNKS_OUTPUT_DIR",
    "KH_PARSE_CACHE_DIR",
    "KH_EMBEDDING_CACHE_DIR",
    "KH_VISION_CACHE_DIR",
    "KH_OCR_CACHE_DIR",
    "KH_FORMULA_OCR_CACHE_DIR",
    "KH_OFFICE_PDF_CACHE_DIR",
    "KH_ZIP_OUTPUT_DIR",
    "KH_ZIP_INPUT_DIR",
    "GRADIO_TEMP_DIR",
    "XDG_CACHE_HOME",
    "XDG_CONFIG_HOME",
    "XDG_DATA_HOME",
    "HF_HOME",
    "HF_HUB_CACHE",
    "HF_XET_CACHE",
    "TORCH_HOME",
    "TIKTOKEN_CACHE_DIR",
    "THEFLOW_SETTINGS_MODULE",
    "THEFLOW_TEMP_PATH",
    "NLTK_DATA",
    "TMP",
    "TEMP",
    "TMPDIR",
)

OWNER_MARKER = ".mara-pytest-owner"


def _seed_nltk_cache(target: Path) -> None:
    """Copy bundled read-only resources; tests must never prepare site-packages."""
    for entry in sys.path:
        source = Path(entry) / "llama_index/core/_static/nltk_cache"
        if source.is_dir():
            shutil.copytree(source, target, dirs_exist_ok=True)
            return


def _dispose_session_database(root: Path) -> None:
    module = sys.modules.get("ktem.db.engine")
    engine = vars(module).get("engine") if module else None
    if engine is None:
        return
    database = engine.url.database
    if database and Path(database).resolve().is_relative_to(root):
        engine.dispose()


def _close_session_caches(root: Path) -> None:
    module = sys.modules.get("theflow.cache.filebased")
    caches = vars(module).get("_local_caches", {}) if module else {}
    for key, cache in list(caches.items()):
        if Path(cache.directory).resolve().is_relative_to(root):
            cache.close()
            del caches[key]


def _remove_readonly_fixture(root: Path, operation, filename, exc_info) -> None:
    error = exc_info[1]
    path = Path(filename)
    if (
        os.name != "nt"
        or operation is not os.unlink
        or not isinstance(error, PermissionError)
        or getattr(error, "winerror", None) != 5
        or path.is_symlink()
        or not path.resolve().is_relative_to(root)
    ):
        raise error
    mode = path.stat().st_mode
    if not stat.S_ISREG(mode) or mode & stat.S_IWRITE:
        raise error
    path.chmod(mode | stat.S_IWRITE)
    operation(filename)


@dataclass(frozen=True)
class TestRuntimePaths:
    root: Path
    app_data_dir: Path
    user_data_dir: Path
    database_path: Path
    file_storage_path: Path
    docstore_path: Path
    vectorstore_path: Path
    cache_dir: Path
    output_dir: Path

    @classmethod
    def from_root(cls, root: Path) -> "TestRuntimePaths":
        root = Path(root).resolve()
        app_data_dir = root / "ktem_app_data"
        user_data_dir = app_data_dir / "user_data"
        return cls(
            root=root,
            app_data_dir=app_data_dir,
            user_data_dir=user_data_dir,
            database_path=user_data_dir / "sql.db",
            file_storage_path=user_data_dir / "files",
            docstore_path=user_data_dir / "docstore",
            vectorstore_path=user_data_dir / "vectorstore",
            cache_dir=root / "cache",
            output_dir=root / "outputs",
        )

    def create_directories(self) -> None:
        for path in (
            self.app_data_dir,
            self.file_storage_path,
            self.docstore_path,
            self.vectorstore_path,
            self.cache_dir,
            self.output_dir,
            self.root / "config",
            self.root / "tmp",
            self.cache_dir / "nltk",
        ):
            path.mkdir(parents=True, exist_ok=True)
        _seed_nltk_cache(self.cache_dir / "nltk")

    def environment(self) -> dict[str, str]:
        cache_dir = self.cache_dir
        return {
            "MARA_PYTEST_RUNTIME_ROOT": str(self.root),
            "MARA_RUNTIME_DIR": str(self.root),
            "MARA_OUTPUT_DIR": str(self.output_dir),
            "KH_APP_DATA_DIR": str(self.app_data_dir),
            "KH_USER_DATA_DIR": str(self.user_data_dir),
            "KH_DATABASE": f"sqlite:///{self.database_path}",
            "KH_FILESTORAGE_PATH": str(self.file_storage_path),
            "KH_DOCSTORE_PATH": str(self.docstore_path),
            "KH_VECTORSTORE_PATH": str(self.vectorstore_path),
            "KH_MARKDOWN_OUTPUT_DIR": str(self.app_data_dir / "markdown_cache_dir"),
            "KH_CHUNKS_OUTPUT_DIR": str(self.app_data_dir / "chunks_cache_dir"),
            "KH_PARSE_CACHE_DIR": str(self.app_data_dir / "parse_cache_dir"),
            "KH_EMBEDDING_CACHE_DIR": str(self.app_data_dir / "embedding_cache_dir"),
            "KH_VISION_CACHE_DIR": str(self.app_data_dir / "vision_cache_dir"),
            "KH_OCR_CACHE_DIR": str(self.app_data_dir / "ocr_cache_dir"),
            "KH_FORMULA_OCR_CACHE_DIR": str(
                self.app_data_dir / "formula_ocr_cache_dir"
            ),
            "KH_OFFICE_PDF_CACHE_DIR": str(self.app_data_dir / "office_pdf_cache_dir"),
            "KH_ZIP_OUTPUT_DIR": str(self.app_data_dir / "zip_cache_dir"),
            "KH_ZIP_INPUT_DIR": str(self.app_data_dir / "zip_cache_dir_in"),
            "GRADIO_TEMP_DIR": str(self.app_data_dir / "gradio_tmp"),
            "XDG_CACHE_HOME": str(cache_dir / "xdg-cache"),
            "XDG_CONFIG_HOME": str(cache_dir / "xdg-config"),
            "XDG_DATA_HOME": str(cache_dir / "xdg-data"),
            "HF_HOME": str(cache_dir / "huggingface"),
            "HF_HUB_CACHE": str(cache_dir / "huggingface" / "hub"),
            "HF_XET_CACHE": str(cache_dir / "huggingface" / "xet"),
            "TORCH_HOME": str(cache_dir / "torch"),
            "TIKTOKEN_CACHE_DIR": str(cache_dir / "tiktoken"),
            "THEFLOW_SETTINGS_MODULE": "ktem.default_flowsettings",
            "THEFLOW_TEMP_PATH": str(cache_dir / "theflow-temp"),
            "NLTK_DATA": str(cache_dir / "nltk"),
            "TMP": str(self.root / "tmp"),
            "TEMP": str(self.root / "tmp"),
            "TMPDIR": str(self.root / "tmp"),
        }


def activate_test_runtime(
    environment: MutableMapping[str, str], root: Path
) -> tuple[dict[str, str | None], TestRuntimePaths]:
    paths = TestRuntimePaths.from_root(root)
    paths.create_directories()
    cleared = {key for key in environment if key.startswith("MARA_DESKTOP_")} | {
        "KOTAEMON_RUNTIME_SETTINGS_BOOTSTRAPPED"
    }
    snapshot = {
        key: environment.get(key)
        for key in (*ISOLATED_RUNTIME_ENV_KEYS, *cleared, "PYTHONDONTWRITEBYTECODE")
    }
    for key in cleared:
        environment.pop(key, None)
    environment.update(paths.environment())
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    return snapshot, paths


def restore_environment(
    environment: MutableMapping[str, str], snapshot: Mapping[str, str | None]
) -> None:
    for key, value in snapshot.items():
        if value is None:
            environment.pop(key, None)
        else:
            environment[key] = value


def create_session_runtime_root(environment: Mapping[str, str]) -> Path:
    explicit_parent = str(environment.get("MARA_PYTEST_RUNTIME_PARENT") or "").strip()
    if explicit_parent:
        parent = Path(explicit_parent).expanduser().resolve()
    else:
        parent = Path(tempfile.gettempdir()).resolve() / "mara_pytest"
    if parent.is_relative_to(Path(sys.prefix).resolve()):
        raise RuntimeError(
            "Test runtime parent cannot be inside the Python environment"
        )
    parent.mkdir(parents=True, exist_ok=True)
    return Path(tempfile.mkdtemp(prefix="session-", dir=parent)).resolve()


@dataclass
class ActiveTestRuntime:
    environment: MutableMapping[str, str]
    snapshot: dict[str, str | None]
    paths: TestRuntimePaths
    closed: bool = False
    owned_root: Path | None = None
    owner_token: str = ""

    @classmethod
    def start(cls, environment: MutableMapping[str, str]) -> "ActiveTestRuntime":
        root = create_session_runtime_root(environment)
        owner_token = uuid.uuid4().hex
        (root / OWNER_MARKER).write_text(owner_token, encoding="utf-8")
        snapshot, paths = activate_test_runtime(environment, root)
        return cls(
            environment=environment,
            snapshot=snapshot,
            paths=paths,
            owned_root=root,
            owner_token=owner_token,
        )

    def close(self) -> None:
        if self.closed:
            return
        try:
            root = self.paths.root
            if (
                self.owned_root != root
                or root.resolve() != root
                or not self.owner_token
                or (root / OWNER_MARKER).is_symlink()
                or not (root / OWNER_MARKER).is_file()
                or (root / OWNER_MARKER).read_text(encoding="utf-8") != self.owner_token
            ):
                raise RuntimeError(
                    "Refusing to clean a runtime not owned by this test session"
                )
            _dispose_session_database(root)
            _close_session_caches(root)
            shutil.rmtree(root, onerror=partial(_remove_readonly_fixture, root))
        finally:
            restore_environment(self.environment, self.snapshot)
            self.closed = True


def start_process_test_runtime() -> ActiveTestRuntime:
    flow_module = sys.modules.get("theflow.settings")
    settings = vars(flow_module).get("settings") if flow_module else None
    if "ktem" in sys.modules or (
        settings is not None and vars(settings).get("_initialized", False)
    ):
        raise RuntimeError("Test isolation must start before importing ktem")
    return ActiveTestRuntime.start(os.environ)
