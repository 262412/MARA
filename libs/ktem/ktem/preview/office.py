from __future__ import annotations

import logging
import os
import shutil
import subprocess
import tempfile
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from ktem.utils.dependencies import find_soffice_binary

from .errors import (
    PreviewCleanupError,
    PreviewConversionError,
    PreviewError,
    PreviewErrorCode,
)
from .models import ConversionAttempt, PreviewSource
from .source import (
    OFFICE_EXTENSIONS,
    classify_preview_source,
    is_office_source,
    is_valid_pdf,
    legacy_preview_cache_signature,
    source_signature,
)

_conversion_locks_guard = threading.Lock()
_conversion_locks: dict[tuple[str, str], threading.Lock] = {}


def get_preview_cache_dir() -> Path:
    root = Path(os.environ.get("GRADIO_TEMP_DIR", tempfile.gettempdir()))
    cache_dir = root / "pdf_previews"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir


def _conversion_lock(cache_dir: Path, signature: str) -> threading.Lock:
    key = (str(cache_dir.resolve()), signature)
    with _conversion_locks_guard:
        return _conversion_locks.setdefault(key, threading.Lock())


def _default_docx_converter(input_path: Path, output_path: Path) -> None:
    from docx2pdf import convert

    convert(str(input_path), str(output_path))


def _conversion_error(
    code: PreviewErrorCode,
    source: PreviewSource,
    stage: str,
    converter: str,
    details: str,
) -> PreviewConversionError:
    return PreviewConversionError(
        code,
        stage=stage,
        source_path=source.path,
        converter=converter,
        details=details,
    )


class _OfficeConverterRunner:
    """Run individual converter processes and locate their raw output."""

    def __init__(
        self,
        *,
        timeout: int,
        soffice_finder: Callable[[], str],
        process_runner: Callable[..., Any],
        docx_converter: Callable[[Path, Path], None],
    ) -> None:
        self._timeout = max(1, timeout)
        self._soffice_finder = soffice_finder
        self._process_runner = process_runner
        self._docx_converter = docx_converter

    def convert_with_soffice(
        self,
        source: PreviewSource,
        input_path: Path,
        output_dir: Path,
        profile_dir: Path,
    ) -> Path:
        soffice = self._soffice_finder()
        if not soffice:
            raise _conversion_error(
                PreviewErrorCode.CONVERTER_UNAVAILABLE,
                source,
                "converter_lookup",
                "libreoffice",
                "Install LibreOffice or configure SOFFICE_PATH.",
            )
        command = [
            str(soffice),
            f"-env:UserInstallation={profile_dir.resolve().as_uri()}",
            "--headless",
            "--convert-to",
            "pdf",
            "--outdir",
            str(output_dir),
            str(input_path),
        ]
        try:
            result = self._process_runner(
                command,
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=self._timeout,
            )
        except subprocess.TimeoutExpired as exc:
            raise _conversion_error(
                PreviewErrorCode.CONVERTER_TIMEOUT,
                source,
                "conversion",
                "libreoffice",
                f"LibreOffice exceeded the {self._timeout} second timeout.",
            ) from exc
        except OSError as exc:
            raise _conversion_error(
                PreviewErrorCode.CONVERTER_FAILED,
                source,
                "conversion",
                "libreoffice",
                f"LibreOffice could not be started: {exc}",
            ) from exc
        return self._check_process_output(source, input_path, output_dir, result)

    def _check_process_output(
        self,
        source: PreviewSource,
        input_path: Path,
        output_dir: Path,
        result: Any,
    ) -> Path:
        return_code = int(getattr(result, "returncode", 1))
        stdout = str(getattr(result, "stdout", "") or "").strip()
        stderr = str(getattr(result, "stderr", "") or "").strip()
        if return_code != 0:
            details = f"LibreOffice exited with code {return_code}."
            diagnostics = stderr or stdout
            if diagnostics:
                details += f" Diagnostics: {diagnostics[:500]}"
            raise _conversion_error(
                PreviewErrorCode.CONVERTER_FAILED,
                source,
                "conversion",
                "libreoffice",
                details,
            )
        candidate = output_dir / f"{input_path.stem}.pdf"
        if not candidate.is_file():
            raise _conversion_error(
                PreviewErrorCode.OUTPUT_MISSING,
                source,
                "output_validation",
                "libreoffice",
                "LibreOffice reported success but did not create the expected PDF.",
            )
        return candidate

    def convert_with_docx2pdf(
        self,
        source: PreviewSource,
        input_path: Path,
        output_dir: Path,
    ) -> Path:
        candidate = output_dir / f"{input_path.stem}.docx2pdf.pdf"
        try:
            self._docx_converter(input_path, candidate)
        except (ImportError, ModuleNotFoundError) as exc:
            raise _conversion_error(
                PreviewErrorCode.CONVERTER_UNAVAILABLE,
                source,
                "converter_lookup",
                "docx2pdf",
                f"Install docx2pdf to enable the Word fallback converter: {exc}",
            ) from exc
        except Exception as exc:
            raise _conversion_error(
                PreviewErrorCode.CONVERTER_FAILED,
                source,
                "conversion",
                "docx2pdf",
                f"docx2pdf failed: {exc}",
            ) from exc
        if not candidate.is_file():
            raise _conversion_error(
                PreviewErrorCode.OUTPUT_MISSING,
                source,
                "output_validation",
                "docx2pdf",
                "docx2pdf returned without creating the expected PDF.",
            )
        return candidate


class OfficeConversionService:
    """Strict Office-to-PDF conversion with validated, atomic caching."""

    def __init__(
        self,
        cache_dir: str | Path,
        *,
        logger: logging.Logger | None = None,
        max_concurrency: int = 2,
        timeout: int = 120,
        soffice_finder: Callable[[], str] | None = None,
        process_runner: Callable[..., Any] | None = None,
        docx_converter: Callable[[Path, Path], None] | None = None,
    ) -> None:
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.cache: dict[str, str] = {}
        self._semaphore = threading.BoundedSemaphore(max(1, max_concurrency))
        self._converter_runner = _OfficeConverterRunner(
            timeout=timeout,
            soffice_finder=soffice_finder or find_soffice_binary,
            process_runner=process_runner or subprocess.run,
            docx_converter=docx_converter or _default_docx_converter,
        )

    def convert_to_pdf(
        self,
        file_path: str | Path,
        file_name: str | None = None,
    ) -> Path:
        source = classify_preview_source(file_path, file_name=file_name)
        if source.extension not in OFFICE_EXTENSIONS:
            raise PreviewConversionError(
                PreviewErrorCode.SOURCE_TYPE_MISMATCH,
                stage="source_classification",
                source_path=source.path,
                converter="office",
                details=f"{source.extension!r} is not a supported Office source.",
            )
        output_path = self._cache_path(source)
        lock = _conversion_lock(self.cache_dir, source.signature)
        try:
            with lock:
                cached = self._cached_output(source, output_path)
                if cached is not None:
                    return cached
                with self._semaphore:
                    converted = self._convert_new(source, output_path)
                self.cache[source.signature] = str(converted)
                return converted
        except PreviewError:
            raise
        except Exception as exc:
            raise PreviewConversionError(
                PreviewErrorCode.CONVERTER_FAILED,
                stage="conversion",
                source_path=source.path,
                converter="office",
                details=f"Unexpected Office conversion failure: {exc}",
            ) from exc

    def get_cached_pdf(
        self,
        file_path: str | Path,
        file_name: str | None = None,
    ) -> Path | None:
        source = classify_preview_source(file_path, file_name=file_name)
        if source.extension not in OFFICE_EXTENSIONS:
            return None
        return self._cached_output(source, self._cache_path(source))

    def _cache_path(self, source: PreviewSource) -> Path:
        cache_signature = legacy_preview_cache_signature(source.path)
        return self.cache_dir / f"{source.path.stem}_{cache_signature[:12]}.pdf"

    def _cached_output(
        self,
        source: PreviewSource,
        expected_path: Path,
    ) -> Path | None:
        cached = Path(self.cache.get(source.signature, expected_path))
        if not cached.is_file():
            return None
        if is_valid_pdf(cached):
            self.cache[source.signature] = str(cached)
            return cached
        self.cache.pop(source.signature, None)
        return None

    def _convert_new(self, source: PreviewSource, output_path: Path) -> Path:
        workspace = Path(tempfile.mkdtemp(prefix=".preview-job-", dir=self.cache_dir))
        failure: PreviewError | None = None
        converted: Path | None = None
        try:
            converted = self._run_conversion_attempts(source, output_path, workspace)
        except PreviewError as exc:
            failure = exc

        try:
            shutil.rmtree(workspace)
        except OSError as exc:
            prior = f" Prior failure: {failure}" if failure is not None else ""
            raise PreviewCleanupError(
                PreviewErrorCode.CLEANUP_FAILED,
                stage="cleanup",
                source_path=source.path,
                converter="filesystem",
                details=f"Unable to remove isolated workspace {workspace}: {exc}.{prior}",
                attempts=getattr(failure, "attempts", ()),
            ) from exc

        if failure is not None:
            raise failure
        if converted is None:
            raise PreviewConversionError(
                PreviewErrorCode.OUTPUT_MISSING,
                stage="output_validation",
                source_path=source.path,
                converter="office",
                details="Conversion ended without a published PDF.",
            )
        return converted

    def _run_conversion_attempts(
        self,
        source: PreviewSource,
        output_path: Path,
        workspace: Path,
    ) -> Path:
        input_dir = workspace / "input"
        output_dir = workspace / "output"
        profile_dir = workspace / "profile"
        for directory in (input_dir, output_dir, profile_dir):
            directory.mkdir(parents=True, exist_ok=True)
        input_path = input_dir / f"source{source.extension}"
        try:
            shutil.copyfile(source.path, input_path)
        except OSError as exc:
            raise PreviewConversionError(
                PreviewErrorCode.CONVERTER_FAILED,
                stage="input_staging",
                source_path=source.path,
                converter="filesystem",
                details=f"Unable to stage Office source for conversion: {exc}",
            ) from exc

        attempts: list[ConversionAttempt] = []
        converters = [
            lambda: self._converter_runner.convert_with_soffice(
                source, input_path, output_dir, profile_dir
            )
        ]
        if source.extension in {".doc", ".docx"}:
            converters.append(
                lambda: self._converter_runner.convert_with_docx2pdf(
                    source, input_path, output_dir
                )
            )
        for convert in converters:
            try:
                candidate = convert()
                return self._publish(source, candidate, output_path)
            except PreviewConversionError as exc:
                attempts.append(exc.as_attempt())
        raise self._merged_attempt_error(source, attempts)

    def _publish(
        self,
        source: PreviewSource,
        candidate: Path,
        output_path: Path,
    ) -> Path:
        if not is_valid_pdf(candidate):
            raise _conversion_error(
                PreviewErrorCode.OUTPUT_INVALID,
                source,
                "output_validation",
                "office",
                f"Converter output is not a valid PDF: {candidate}",
            )
        if output_path.is_file() and is_valid_pdf(output_path):
            return output_path
        os.replace(candidate, output_path)
        return output_path

    def _merged_attempt_error(
        self,
        source: PreviewSource,
        attempts: list[ConversionAttempt],
    ) -> PreviewConversionError:
        if not attempts:
            return _conversion_error(
                PreviewErrorCode.CONVERTER_FAILED,
                source,
                "conversion",
                "office",
                "No Office converter was attempted.",
            )
        final = attempts[-1]
        details = "; ".join(
            f"{attempt.converter} ({attempt.code}): {attempt.details}"
            for attempt in attempts
        )
        return PreviewConversionError(
            PreviewErrorCode(final.code),
            stage=final.stage,
            source_path=source.path,
            converter=final.converter,
            details=details,
            attempts=attempts,
        )


class OfficePreviewConversionService:
    """Legacy Web/DocQA facade preserving empty-string fallback behavior."""

    def __init__(
        self,
        logger: logging.Logger | None = None,
        cache_dir: str | Path | None = None,
        max_concurrency: int = 2,
    ) -> None:
        self._logger = logger or logging.getLogger(__name__)
        self._core = OfficeConversionService(
            cache_dir or get_preview_cache_dir(),
            logger=self._logger,
            max_concurrency=max_concurrency,
            soffice_finder=self.find_soffice_binary,
        )
        self._office_pdf_cache = self._core.cache
        self._office_pdf_job_status: dict[str, str] = {}
        self._office_pdf_job_ts: dict[str, float] = {}
        self._office_pdf_job_lock = threading.Lock()
        self._last_errors: dict[str, PreviewError] = {}

    @staticmethod
    def find_soffice_binary() -> str:
        return find_soffice_binary()

    def get_status(self, file_path: str) -> str:
        if not file_path:
            return ""
        key = source_signature(file_path)
        with self._office_pdf_job_lock:
            return self._office_pdf_job_status.get(key, "")

    def convert_to_pdf_preview(self, file_path: str, file_name: str) -> str:
        try:
            return str(self._core.convert_to_pdf(file_path, file_name))
        except PreviewError as exc:
            self._record_error(file_path, exc)
            return ""

    def get_cached_pdf_preview(self, file_path: str) -> str:
        try:
            cached = self._core.get_cached_pdf(file_path)
        except PreviewError as exc:
            self._record_error(file_path, exc)
            return ""
        if cached is None:
            return ""
        key = source_signature(file_path)
        with self._office_pdf_job_lock:
            self._office_pdf_job_status[key] = "done"
        return str(cached)

    def schedule_conversion(self, file_path: str, file_name: str) -> None:
        if not is_office_source(file_name, file_path):
            return
        if not file_path or not Path(file_path).is_file():
            return
        if self.get_cached_pdf_preview(file_path):
            return

        job_key = source_signature(file_path)
        now = time.time()
        with self._office_pdf_job_lock:
            status = self._office_pdf_job_status.get(job_key, "")
            last_run = self._office_pdf_job_ts.get(job_key, 0.0)
            if status in {"queued", "running"} and now - last_run <= 180:
                return
            self._office_pdf_job_status[job_key] = "queued"
            self._office_pdf_job_ts[job_key] = now

        threading.Thread(
            target=self._run_scheduled_conversion,
            args=(file_path, file_name, job_key),
            name=f"office-pdf-preview-{job_key[:8]}",
            daemon=True,
        ).start()

    def _run_scheduled_conversion(
        self,
        file_path: str,
        file_name: str,
        job_key: str,
    ) -> None:
        self._set_job_status(job_key, "running")
        output = self.convert_to_pdf_preview(file_path, file_name)
        status = "done" if output and Path(output).is_file() else "failed"
        self._set_job_status(job_key, status)

    def _set_job_status(self, job_key: str, status: str) -> None:
        with self._office_pdf_job_lock:
            self._office_pdf_job_status[job_key] = status
            self._office_pdf_job_ts[job_key] = time.time()

    def _record_error(self, file_path: str, error: PreviewError) -> None:
        key = source_signature(file_path)
        self._last_errors[key] = error
        self._logger.warning(
            "Office preview conversion failed file=%s converter=%s stage=%s "
            "code=%s details=%s",
            error.source_path,
            error.converter,
            error.stage,
            error.code.value,
            error.details,
        )

    @staticmethod
    def _cleanup_temp_input(temp_input_path: str) -> None:
        if not temp_input_path:
            return
        try:
            Path(temp_input_path).unlink(missing_ok=True)
        except OSError:
            return
