from __future__ import annotations

import os
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import unquote, urlparse

import pytest
from ktem_tests.preview_test_utils import SuccessfulSofficeRunner, write_ooxml


@pytest.fixture(autouse=True)
def _temporary_runtime(monkeypatch, tmp_path):
    monkeypatch.setenv("KH_APP_DATA_DIR", str(tmp_path / "app-data"))


def _service(cache_dir: Path, **kwargs):
    from ktem.preview.office import OfficeConversionService

    return OfficeConversionService(cache_dir=cache_dir, **kwargs)


def _error_types():
    from ktem.preview.errors import PreviewConversionError, PreviewErrorCode

    return PreviewConversionError, PreviewErrorCode


def test_conversion_uses_isolated_output_and_user_profile_then_cleans_them(tmp_path):
    source = write_ooxml(tmp_path / "layout.docx")
    runner = SuccessfulSofficeRunner()
    service = _service(
        tmp_path / "cache",
        soffice_finder=lambda: "/opt/libreoffice/program/soffice",
        process_runner=runner,
    )

    output = service.convert_to_pdf(source, source.name)

    assert output.is_file()
    assert output.parent == tmp_path / "cache"
    command = runner.commands[0]
    output_dir = Path(command[command.index("--outdir") + 1])
    profile_arg = next(
        value for value in command if value.startswith("-env:UserInstallation=")
    )
    profile_uri = profile_arg.split("=", 1)[1]
    profile_dir = Path(unquote(urlparse(profile_uri).path))
    assert not output_dir.exists()
    assert not profile_dir.exists()
    assert not list((tmp_path / "cache").glob(".preview-job-*"))


def test_cache_path_is_signature_derived_and_reused(tmp_path):
    source = write_ooxml(tmp_path / "layout.pptx")
    runner = SuccessfulSofficeRunner()
    service = _service(
        tmp_path / "cache",
        soffice_finder=lambda: "soffice",
        process_runner=runner,
    )

    first = service.convert_to_pdf(source, source.name)
    second = service.convert_to_pdf(source, source.name)

    assert first == second
    assert first.name.startswith("layout_")
    assert first.suffix == ".pdf"
    assert runner.calls == 1


def test_invalid_existing_cache_is_replaced_by_a_fresh_valid_conversion(tmp_path):
    source = write_ooxml(tmp_path / "layout.pptx")
    cache_dir = tmp_path / "cache"
    first_runner = SuccessfulSofficeRunner()
    first_service = _service(
        cache_dir,
        soffice_finder=lambda: "soffice",
        process_runner=first_runner,
    )
    output = first_service.convert_to_pdf(source, source.name)
    output.write_bytes(b"corrupt-cache-entry")

    retry_runner = SuccessfulSofficeRunner()
    retry_service = _service(
        cache_dir,
        soffice_finder=lambda: "soffice",
        process_runner=retry_runner,
    )

    recovered = retry_service.convert_to_pdf(source, source.name)

    assert recovered == output
    assert recovered.is_file()
    assert retry_runner.calls == 1


def test_same_names_in_different_directories_never_share_cache_entries(tmp_path):
    first_source = write_ooxml(tmp_path / "one" / "report.pptx")
    second_source = write_ooxml(tmp_path / "two" / "report.pptx")
    runner = SuccessfulSofficeRunner()
    service = _service(
        tmp_path / "cache",
        soffice_finder=lambda: "soffice",
        process_runner=runner,
    )

    first = service.convert_to_pdf(first_source, first_source.name)
    second = service.convert_to_pdf(second_source, second_source.name)

    assert first != second
    assert first.is_file() and second.is_file()
    assert runner.calls == 2


def test_same_source_concurrency_coalesces_across_service_instances(tmp_path):
    source = write_ooxml(tmp_path / "shared.pptx")
    runner = SuccessfulSofficeRunner(delay=0.05)
    services = [
        _service(
            tmp_path / "cache",
            soffice_finder=lambda: "soffice",
            process_runner=runner,
        )
        for _ in range(4)
    ]

    with ThreadPoolExecutor(max_workers=4) as executor:
        outputs = list(
            executor.map(
                lambda service: service.convert_to_pdf(source, source.name),
                services,
            )
        )

    assert len(set(outputs)) == 1
    assert outputs[0].is_file()
    assert runner.calls == 1


def test_conversion_concurrency_is_bounded(tmp_path):
    sources = [write_ooxml(tmp_path / f"source-{index}.pptx") for index in range(5)]
    runner = SuccessfulSofficeRunner(delay=0.05)
    service = _service(
        tmp_path / "cache",
        max_concurrency=2,
        soffice_finder=lambda: "soffice",
        process_runner=runner,
    )

    with ThreadPoolExecutor(max_workers=5) as executor:
        outputs = list(
            executor.map(
                lambda source: service.convert_to_pdf(source, source.name),
                sources,
            )
        )

    assert all(output.is_file() for output in outputs)
    assert runner.max_active == 2


def test_missing_converter_raises_typed_actionable_error(tmp_path):
    PreviewConversionError, PreviewErrorCode = _error_types()
    source = write_ooxml(tmp_path / "slides.pptx")
    service = _service(tmp_path / "cache", soffice_finder=lambda: "")

    with pytest.raises(PreviewConversionError) as caught:
        service.convert_to_pdf(source, source.name)

    assert caught.value.code is PreviewErrorCode.CONVERTER_UNAVAILABLE
    assert caught.value.stage == "converter_lookup"
    assert caught.value.source_path == source.resolve()
    assert caught.value.converter == "libreoffice"
    assert "install" in caught.value.details.lower()


def test_nonzero_converter_exit_retains_stderr(tmp_path):
    PreviewConversionError, PreviewErrorCode = _error_types()
    source = write_ooxml(tmp_path / "slides.pptx")

    def nonzero_runner(_command, **_kwargs):
        return SimpleNamespace(returncode=17, stdout="", stderr="filter failed")

    service = _service(
        tmp_path / "cache",
        soffice_finder=lambda: "soffice",
        process_runner=nonzero_runner,
    )

    with pytest.raises(PreviewConversionError) as caught:
        service.convert_to_pdf(source, source.name)

    assert caught.value.code is PreviewErrorCode.CONVERTER_FAILED
    assert caught.value.stage == "conversion"
    assert caught.value.converter == "libreoffice"
    assert "17" in caught.value.details
    assert "filter failed" in caught.value.details


def test_converter_timeout_is_typed(tmp_path):
    PreviewConversionError, PreviewErrorCode = _error_types()
    source = write_ooxml(tmp_path / "slides.pptx")

    def timeout_runner(command, **_kwargs):
        raise subprocess.TimeoutExpired(command, 120)

    service = _service(
        tmp_path / "cache",
        soffice_finder=lambda: "soffice",
        process_runner=timeout_runner,
    )

    with pytest.raises(PreviewConversionError) as caught:
        service.convert_to_pdf(source, source.name)

    assert caught.value.code is PreviewErrorCode.CONVERTER_TIMEOUT
    assert caught.value.stage == "conversion"
    assert caught.value.converter == "libreoffice"
    assert "120" in caught.value.details


def test_success_without_output_raises_output_missing(tmp_path):
    PreviewConversionError, PreviewErrorCode = _error_types()
    source = write_ooxml(tmp_path / "slides.pptx")
    service = _service(
        tmp_path / "cache",
        soffice_finder=lambda: "soffice",
        process_runner=lambda *_args, **_kwargs: SimpleNamespace(
            returncode=0, stdout="ok", stderr=""
        ),
    )

    with pytest.raises(PreviewConversionError) as caught:
        service.convert_to_pdf(source, source.name)

    assert caught.value.code is PreviewErrorCode.OUTPUT_MISSING
    assert caught.value.stage == "output_validation"
    assert caught.value.converter == "libreoffice"


def test_bad_converter_output_is_never_published(tmp_path):
    PreviewConversionError, PreviewErrorCode = _error_types()
    source = write_ooxml(tmp_path / "slides.pptx")

    def bad_output_runner(command, **_kwargs):
        output_dir = Path(command[command.index("--outdir") + 1])
        input_path = Path(command[-1])
        (output_dir / f"{input_path.stem}.pdf").write_bytes(b"not-a-pdf")
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    cache_dir = tmp_path / "cache"
    service = _service(
        cache_dir,
        soffice_finder=lambda: "soffice",
        process_runner=bad_output_runner,
    )

    with pytest.raises(PreviewConversionError) as caught:
        service.convert_to_pdf(source, source.name)

    assert caught.value.code is PreviewErrorCode.OUTPUT_INVALID
    assert caught.value.stage == "output_validation"
    assert not list(cache_dir.glob("slides_*.pdf"))


def test_docx_retry_error_retains_all_converter_diagnostics(tmp_path):
    PreviewConversionError, PreviewErrorCode = _error_types()
    source = write_ooxml(tmp_path / "report.docx")

    def nonzero_runner(_command, **_kwargs):
        return SimpleNamespace(returncode=9, stdout="", stderr="soffice failed")

    def failed_docx_converter(_source, _output):
        raise RuntimeError("docx2pdf failed")

    service = _service(
        tmp_path / "cache",
        soffice_finder=lambda: "soffice",
        process_runner=nonzero_runner,
        docx_converter=failed_docx_converter,
    )

    with pytest.raises(PreviewConversionError) as caught:
        service.convert_to_pdf(source, source.name)

    assert caught.value.code is PreviewErrorCode.CONVERTER_FAILED
    assert [attempt.converter for attempt in caught.value.attempts] == [
        "libreoffice",
        "docx2pdf",
    ]
    assert "soffice failed" in caught.value.details
    assert "docx2pdf failed" in caught.value.details


def test_cleanup_failure_is_typed_without_deleting_published_output(
    monkeypatch, tmp_path
):
    import ktem.preview.office as office_module
    from ktem.preview.errors import PreviewCleanupError, PreviewErrorCode

    source = write_ooxml(tmp_path / "slides.pptx")
    runner = SuccessfulSofficeRunner()
    cache_dir = tmp_path / "cache"
    service = _service(
        cache_dir,
        soffice_finder=lambda: "soffice",
        process_runner=runner,
    )

    monkeypatch.setattr(
        office_module.shutil,
        "rmtree",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("cleanup denied")),
    )

    with pytest.raises(PreviewCleanupError) as caught:
        service.convert_to_pdf(source, source.name)

    assert caught.value.code is PreviewErrorCode.CLEANUP_FAILED
    assert caught.value.stage == "cleanup"
    assert caught.value.converter == "filesystem"
    assert "cleanup denied" in caught.value.details
    assert len(list(cache_dir.glob("slides_*.pdf"))) == 1


def test_atomic_publish_never_exposes_partial_cache_file(monkeypatch, tmp_path):
    import ktem.preview.office as office_module

    source = write_ooxml(tmp_path / "slides.pptx")
    runner = SuccessfulSofficeRunner()
    replacements: list[tuple[Path, Path]] = []
    original_replace = os.replace

    def recording_replace(source_path, target_path):
        replacements.append((Path(source_path), Path(target_path)))
        assert Path(source_path).is_file()
        assert not Path(target_path).exists()
        original_replace(source_path, target_path)

    monkeypatch.setattr(office_module.os, "replace", recording_replace)
    service = _service(
        tmp_path / "cache",
        soffice_finder=lambda: "soffice",
        process_runner=runner,
    )

    output = service.convert_to_pdf(source, source.name)

    assert replacements == [(replacements[0][0], output)]
    assert output.is_file()
