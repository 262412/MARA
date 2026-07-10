from __future__ import annotations

import fnmatch
import logging
import os
from copy import deepcopy
from pathlib import Path
from typing import Any, Callable, Generator

from sqlalchemy.orm import Session

from .archive import ArchiveExtractionError, extract_supported_zip_files
from .utils import download_arxiv_pdf, is_arxiv_url

logger = logging.getLogger(__name__)
IndexUpdates = Generator[tuple[str, str], None, list[str] | None]


class FileIndexingService:
    def __init__(
        self,
        *,
        index: Any,
        supported_file_types: list[str],
        zip_input_dir: str | Path,
        engine: Any,
        demo_mode: bool,
        notify: Callable[[str, str], None],
        archive_extractor: Callable[..., list[str]] = extract_supported_zip_files,
        arxiv_downloader: Callable[..., str] = download_arxiv_pdf,
        arxiv_validator: Callable[[str], bool] = is_arxiv_url,
    ) -> None:
        self._index = index
        self._supported_file_types = list(supported_file_types)
        self._zip_input_dir = Path(zip_input_dir)
        self._engine = engine
        self._demo_mode = demo_mode
        self._notify = notify
        self._archive_extractor = archive_extractor
        self._arxiv_downloader = arxiv_downloader
        self._arxiv_validator = arxiv_validator

    def extract_archives(self, files: list[str]) -> tuple[list[str], list[str]]:
        archives = [path for path in files if str(path).lower().endswith(".zip")]
        remaining = [path for path in files if not str(path).lower().endswith(".zip")]
        errors: list[str] = []
        extracted_count = 0
        for archive in archives:
            try:
                extracted = self._archive_extractor(
                    archive,
                    destination_parent=self._zip_input_dir,
                    supported_types=set(self._supported_file_types),
                )
                remaining.extend(extracted)
                extracted_count += len(extracted)
            except ArchiveExtractionError as exc:
                errors.append(str(exc))
        if extracted_count:
            print(f"Update zip files: {extracted_count}")
        return remaining, errors

    def index(
        self,
        files: list[str],
        urls: Any,
        *,
        reindex: bool,
        settings: dict[str, Any],
        user_id: Any,
    ) -> IndexUpdates:
        prepared_files, errors = self._prepare_inputs(files, urls)
        if prepared_files is None:
            self._notify("info", "No uploaded file")
            yield "", ""
            return None
        if errors:
            self._notify("warning", ", ".join(errors))
            yield "", ""
            return None
        self._notify("info", f"Start indexing {len(prepared_files)} files...")
        return (
            yield from self._stream_index(
                prepared_files,
                reindex=reindex,
                settings=settings,
                user_id=user_id,
            )
        )

    def _prepare_inputs(
        self,
        files: list[str],
        urls: Any,
    ) -> tuple[list[str] | None, list[str]]:
        if urls:
            url_files = [item.strip() for item in str(urls).split("\n")]
            return url_files, self.validate_urls(url_files)
        if not files:
            return None, []
        expanded, archive_errors = self.extract_archives(files)
        return expanded, [*self.validate_files(expanded), *archive_errors]

    def _stream_index(
        self,
        files: list[str],
        *,
        reindex: bool,
        settings: dict[str, Any],
        user_id: Any,
    ) -> IndexUpdates:
        pipeline = self._index.get_indexing_pipeline(settings, user_id)
        outputs: list[str] = []
        debugs: list[str] = []
        output_stream = pipeline.stream(files, reindex=reindex)
        try:
            while True:
                response = next(output_stream)
                if response is None:
                    continue
                _capture_progress(response, outputs, debugs)
                yield "\n".join(outputs), "\n".join(debugs)
        except StopIteration as exc:
            results, _index_errors, _docs = exc.value or ([], [], [])
        except Exception as exc:
            logger.exception(
                "File indexing failed: index_id=%s user_id=%s stage=stream",
                getattr(self._index, "id", None),
                user_id,
            )
            debugs.append(f"Error: {exc}")
            yield "\n".join(outputs), "\n".join(debugs)
            return None

        successful_ids = [item for item in results if item]
        if successful_ids:
            self._notify(
                "info",
                f"Successfully index {len(successful_ids)} files",
            )
        return list(results)

    def index_files_with_default_loaders(
        self,
        files: list[str],
        *,
        reindex: bool,
        settings: dict[str, Any],
        user_id: Any,
    ) -> list[str]:
        existing_ids, to_process = _partition_existing(
            self._index,
            files,
            settings,
            user_id,
        )
        quick_settings = _quick_index_settings(self._index.id, settings)
        returned_ids: list[str] = []
        if to_process:
            returned_ids = _drain_updates(
                self.index(
                    to_process,
                    [],
                    reindex=reindex,
                    settings=quick_settings,
                    user_id=user_id,
                )
            )
        return [*existing_ids, *returned_ids]

    def index_urls_with_default_loaders(
        self,
        urls: str,
        *,
        reindex: bool,
        settings: dict[str, Any],
        user_id: Any,
    ) -> list[str]:
        quick_settings = _quick_index_settings(self._index.id, settings)
        if not self._demo_mode:
            if not urls:
                return []
            return _drain_updates(
                self.index(
                    [],
                    urls,
                    reindex=reindex,
                    settings=quick_settings,
                    user_id=user_id,
                )
            )

        split_urls = urls.split("\n")
        if not all(self._arxiv_validator(url) for url in split_urls):
            raise ValueError("All URLs must be valid arXiv URLs")
        output_files = [
            self._arxiv_downloader(
                url,
                output_path=os.environ.get("GRADIO_TEMP_DIR", "/tmp"),
            )
            for url in split_urls
        ]
        existing_ids, to_process = _partition_existing(
            self._index,
            output_files,
            quick_settings,
            user_id,
        )
        returned_ids = (
            _drain_updates(
                self.index(
                    to_process,
                    [],
                    reindex=reindex,
                    settings=quick_settings,
                    user_id=user_id,
                )
            )
            if to_process
            else []
        )
        return [*existing_ids, *returned_ids]

    def index_directory(
        self,
        folder_path: str,
        *,
        reindex: bool,
        settings: dict[str, Any],
        user_id: Any,
    ) -> IndexUpdates:
        if not folder_path:
            yield "", ""
            return None
        files = _directory_files(folder_path)
        return (
            yield from self.index(
                files,
                [],
                reindex=reindex,
                settings=settings,
                user_id=user_id,
            )
        )

    def validate_files(self, files: list[str]) -> list[str]:
        paths = [Path(file) for file in files]
        errors: list[str] = []
        if max_file_size := self._index.config.get("max_file_size", 0):
            oversized = [
                path.name for path in paths if path.stat().st_size > max_file_size * 1e6
            ]
            if oversized:
                names = ", ".join(oversized)
                if len(names) > 60:
                    names = names[:55] + "..."
                errors.append(
                    f"Maximum file size ({max_file_size} MB) exceeded: {names}"
                )
        if max_files := self._index.config.get("max_number_of_files", 0):
            with Session(self._engine) as session:
                current = session.query(self._index._resources["Source"].id).count()
            if len(paths) + current > max_files:
                errors.append(f"Maximum number of files ({max_files}) will be exceeded")
        return errors

    @staticmethod
    def validate_urls(urls: list[str]) -> list[str]:
        return [f"Invalid url `{url}`" for url in urls if not url.startswith("http")]


def _capture_progress(response: Any, outputs: list[str], debugs: list[str]) -> None:
    if response.channel == "index":
        content = response.content
        if content["status"] == "success":
            outputs.append(f"✅ | {content['file_name']}")
        elif content["status"] == "failed":
            outputs.append(f"❌ | {content['file_name']}: {content['message']}")
    elif response.channel == "debug":
        debugs.append(str(response.text))


def _quick_index_settings(index_id: Any, settings: dict[str, Any]) -> dict[str, Any]:
    updated = deepcopy(settings)
    updated[f"index.options.{index_id}.reader_mode"] = "default"
    updated[f"index.options.{index_id}.quick_index_mode"] = True
    return updated


def _partition_existing(
    index: Any,
    files: list[str],
    settings: dict[str, Any],
    user_id: Any,
) -> tuple[list[str], list[str]]:
    existing_ids: list[str] = []
    to_process: list[str] = []
    for raw_path in files:
        path = Path(str(raw_path))
        existing_id = (
            index.get_indexing_pipeline(settings, user_id)
            .route(path)
            .get_id_if_exists(path)
        )
        if existing_id:
            existing_ids.append(existing_id)
        else:
            to_process.append(raw_path)
    return existing_ids, to_process


def _drain_updates(updates: IndexUpdates) -> list[str]:
    while True:
        try:
            next(updates)
        except StopIteration as exc:
            return list(exc.value or [])


def _directory_files(folder_path: str) -> list[str]:
    include_patterns: list[str] = []
    exclude_patterns: list[str] = ["*.png", "*.gif", "*/.*"]
    if include_patterns and exclude_patterns:
        raise ValueError("Cannot have both include and exclude patterns")
    include_patterns = [_absolute_pattern(item) for item in include_patterns]
    exclude_patterns = [_absolute_pattern(item) for item in exclude_patterns]
    files = [str(path) for path in Path(folder_path).glob("**/*.*")]
    for pattern in include_patterns:
        files = fnmatch.filter(names=files, pat=pattern)
    for pattern in exclude_patterns:
        files = [path for path in files if not fnmatch.fnmatch(path, pattern)]
    return files


def _absolute_pattern(pattern: str) -> str:
    if pattern.startswith("*"):
        return str(Path.cwd() / "**" / pattern)
    return str(Path.cwd() / pattern.strip("/"))


__all__ = ["FileIndexingService", "IndexUpdates"]
