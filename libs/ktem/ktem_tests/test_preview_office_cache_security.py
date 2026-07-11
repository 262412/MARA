from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import pytest
from ktem_tests.preview_test_utils import (
    SuccessfulSofficeRunner,
    write_ooxml,
    write_text_pdf,
)


@pytest.fixture(autouse=True)
def _temporary_runtime(monkeypatch, tmp_path):
    monkeypatch.setenv("KH_APP_DATA_DIR", str(tmp_path / "app-data"))
    monkeypatch.setenv("GRADIO_TEMP_DIR", str(tmp_path / "gradio"))


def _service(cache_dir: Path, runner: SuccessfulSofficeRunner):
    from ktem.preview.office import OfficeConversionService

    return OfficeConversionService(
        cache_dir,
        soffice_finder=lambda: "soffice",
        process_runner=runner,
    )


def _source_and_output(service, source_path: Path):
    from ktem.preview.source import classify_preview_source

    source = classify_preview_source(source_path, file_name=source_path.name)
    return source, service._cache_path(source)


def test_prepositioned_valid_pdf_is_not_a_trusted_conversion(tmp_path):
    source_path = write_ooxml(tmp_path / "source" / "report.docx")
    runner = SuccessfulSofficeRunner()
    service = _service(tmp_path / "cache", runner)
    _source, output_path = _source_and_output(service, source_path)
    poison = write_text_pdf(output_path, ["attacker-controlled cache entry"])
    poison_bytes = poison.read_bytes()

    output = service.convert_to_pdf(source_path, source_path.name)

    assert runner.calls == 1
    assert output == output_path
    assert output.read_bytes() != poison_bytes


def test_canonical_cache_leaf_symlink_is_rejected_without_reading_target(tmp_path):
    from ktem.preview.errors import PreviewConversionError

    source_path = write_ooxml(tmp_path / "source" / "report.docx")
    runner = SuccessfulSofficeRunner()
    service = _service(tmp_path / "cache", runner)
    _source, output_path = _source_and_output(service, source_path)
    victim = write_text_pdf(tmp_path / "victim.pdf", ["private target"])
    victim_bytes = victim.read_bytes()
    output_path.symlink_to(victim)

    with pytest.raises(PreviewConversionError, match="symlink"):
        service.convert_to_pdf(source_path, source_path.name)

    assert runner.calls == 0
    assert output_path.is_symlink()
    assert victim.read_bytes() == victim_bytes


def test_publish_replaces_existing_valid_but_untrusted_target(tmp_path):
    source_path = write_ooxml(tmp_path / "source" / "report.docx")
    runner = SuccessfulSofficeRunner()
    service = _service(tmp_path / "cache", runner)
    source, output_path = _source_and_output(service, source_path)
    poison = write_text_pdf(output_path, ["poison"])
    poison_bytes = poison.read_bytes()
    candidate = write_text_pdf(tmp_path / "candidate.pdf", ["trusted conversion"])
    candidate_bytes = candidate.read_bytes()

    published = service._publish(source, candidate, output_path)

    assert published == output_path
    assert published.read_bytes() == candidate_bytes
    assert published.read_bytes() != poison_bytes


def test_attested_cache_is_reused_across_service_instances(tmp_path):
    source_path = write_ooxml(tmp_path / "source" / "report.docx")
    cache_dir = tmp_path / "cache"
    first_runner = SuccessfulSofficeRunner()
    first = _service(cache_dir, first_runner)

    first_output = first.convert_to_pdf(source_path, source_path.name)

    second_runner = SuccessfulSofficeRunner()
    second = _service(cache_dir, second_runner)
    second_output = second.convert_to_pdf(source_path, source_path.name)

    assert second_output == first_output
    assert first_runner.calls == 1
    assert second_runner.calls == 0


def test_cache_writer_cannot_forge_attestation_after_replacing_artifact(tmp_path):
    source_path = write_ooxml(tmp_path / "source" / "report.docx")
    cache_dir = tmp_path / "cache"
    first_runner = SuccessfulSofficeRunner()
    first = _service(cache_dir, first_runner)
    output = first.convert_to_pdf(source_path, source_path.name)
    manifest_path = output.with_name(f".{output.name}.attestation.json")

    poison = write_text_pdf(output, ["attacker replacement"])
    poison_bytes = poison.read_bytes()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["artifact_sha256"] = hashlib.sha256(poison_bytes).hexdigest()
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    retry_runner = SuccessfulSofficeRunner()
    recovered = _service(cache_dir, retry_runner).convert_to_pdf(
        source_path, source_path.name
    )

    assert recovered == output
    assert retry_runner.calls == 1
    assert recovered.read_bytes() != poison_bytes


def test_web_visible_cache_name_keeps_legacy_signature(tmp_path):
    from ktem.preview.office import OfficePreviewConversionService

    source_path = write_ooxml(tmp_path / "source" / "report.docx")
    runner = SuccessfulSofficeRunner()
    service = OfficePreviewConversionService()
    service._core._converter_runner._soffice_finder = lambda: "soffice"
    service._core._converter_runner._process_runner = runner

    output = Path(service.convert_to_pdf_preview(str(source_path), source_path.name))

    stat = os.stat(source_path)
    payload = f"{os.path.abspath(source_path)}|{stat.st_size}|{int(stat.st_mtime_ns)}"
    legacy_signature = hashlib.md5(payload.encode("utf-8")).hexdigest()
    assert output.name == f"report_{legacy_signature[:12]}.pdf"
    assert runner.calls == 1
