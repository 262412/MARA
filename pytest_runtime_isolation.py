from __future__ import annotations

import os
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, MutableMapping

ISOLATED_RUNTIME_ENV_KEYS = (
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
)


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
        ):
            path.mkdir(parents=True, exist_ok=True)

    def environment(self) -> dict[str, str]:
        cache_dir = self.cache_dir
        return {
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
        }


def activate_test_runtime(
    environment: MutableMapping[str, str], root: Path
) -> tuple[dict[str, str | None], TestRuntimePaths]:
    paths = TestRuntimePaths.from_root(root)
    paths.create_directories()
    snapshot = {key: environment.get(key) for key in ISOLATED_RUNTIME_ENV_KEYS}
    environment.update(paths.environment())
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
        runtime_dir = str(environment.get("MARA_RUNTIME_DIR") or "").strip()
        if runtime_dir:
            parent = Path(runtime_dir).expanduser().resolve().parent / "mara_pytest"
        else:
            parent = Path(tempfile.gettempdir()).resolve() / "mara_pytest"
    parent.mkdir(parents=True, exist_ok=True)
    return Path(tempfile.mkdtemp(prefix="session-", dir=parent)).resolve()


@dataclass
class ActiveTestRuntime:
    environment: MutableMapping[str, str]
    snapshot: dict[str, str | None]
    paths: TestRuntimePaths
    closed: bool = False

    @classmethod
    def start(cls, environment: MutableMapping[str, str]) -> "ActiveTestRuntime":
        root = create_session_runtime_root(environment)
        snapshot, paths = activate_test_runtime(environment, root)
        return cls(environment=environment, snapshot=snapshot, paths=paths)

    def close(self) -> None:
        if self.closed:
            return
        restore_environment(self.environment, self.snapshot)
        shutil.rmtree(self.paths.root, ignore_errors=True)
        self.closed = True


def start_process_test_runtime() -> ActiveTestRuntime:
    return ActiveTestRuntime.start(os.environ)
