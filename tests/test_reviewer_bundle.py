import hashlib
import tomllib
import zipfile

import pytest
from packaging.specifiers import SpecifierSet

from scripts import build_reviewer_bundle as builder
from scripts.prepare_reviewer_dependencies import source_requirements


def wheel(path, name, version="1.0"):
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(
            f"{name}-{version}.dist-info/METADATA",
            f"Metadata-Version: 2.1\nName: {name}\nVersion: {version}\n",
        )
    return path


def test_vendor_wheel_replaces_only_matching_locked_hashes(tmp_path):
    archive = wheel(tmp_path / "example_pkg-1.0-py3-none-any.whl", "example-pkg")
    original = "example-pkg==1.0 \\\n    --hash=sha256:old\nuntouched==2.0 \\\n    --hash=sha256:retained\n"
    result = builder.vendor_requirements(original, [archive])
    assert hashlib.sha256(archive.read_bytes()).hexdigest() in result
    assert "sha256:old" not in result
    assert "untouched==2.0" in result
    assert "sha256:retained" in result


def test_vendor_wheel_cannot_silently_change_locked_version(tmp_path):
    archive = wheel(tmp_path / "example-2.0-py3-none-any.whl", "example", "2.0")
    with pytest.raises(ValueError, match="locked version"):
        builder.vendor_requirements("example==1.0 --hash=sha256:old\n", [archive])


def test_bootstrap_rejects_unverified_uv_before_extracting(tmp_path):
    source = tmp_path / "uv.whl"
    source.write_bytes(b"modified installer")
    destination = tmp_path / "tools"
    with pytest.raises(ValueError, match="SHA-256"):
        builder.extract_uv(source, destination)
    assert not destination.exists()


def test_manifest_records_relative_paths_and_detectable_content_changes(tmp_path):
    (tmp_path / "sample.txt").write_text("public sample", encoding="utf-8")
    before = builder.file_hashes(tmp_path)
    assert set(before) == {"sample.txt"}
    (tmp_path / "sample.txt").write_text("changed", encoding="utf-8")
    assert before != builder.file_hashes(tmp_path)


def test_prebuild_selection_keeps_hashes_and_respects_platform_markers():
    lock = {
        "package": [
            {"name": "source-only", "version": "1.0"},
            {"name": "linux-only", "version": "1.0"},
            {
                "name": "portable",
                "version": "1.0",
                "wheels": [
                    {"url": "https://example.test/portable-1.0-py3-none-any.whl"}
                ],
            },
        ]
    }
    source = "source-only==1.0 \\\n    --hash=sha256:source\n"
    text = (
        source
        + "portable==1.0 \\\n    --hash=sha256:wheel\nlinux-only==1.0 ; sys_platform == 'unused-platform' \\\n    --hash=sha256:linux\n"
    )
    selected = source_requirements(lock, text)
    assert selected == [source.strip()]


def test_reviewer_python_satisfies_current_runtime_contract():
    project = tomllib.loads((builder.ROOT / "pyproject.toml").read_text("utf-8"))
    assert builder.PYTHON_VERSION in SpecifierSet(project["project"]["requires-python"])


def test_prebuild_selection_includes_locked_local_source():
    lock = {
        "package": [
            {
                "name": "nltk",
                "version": "3.10.3.post1+mara.1",
                "source": {"directory": "vendor/nltk"},
            }
        ]
    }
    assert source_requirements(lock, "./vendor/nltk\n") == ["./vendor/nltk"]


def test_vendor_local_source_becomes_version_and_hash_pinned(tmp_path):
    archive = wheel(tmp_path / "nltk.whl", "nltk", "3.10.3.post1+mara.1")
    local_packages = {"./vendor/nltk": ("nltk", "3.10.3.post1+mara.1")}
    result = builder.vendor_requirements("./vendor/nltk\n", [archive], local_packages)
    assert result.startswith("nltk==3.10.3.post1+mara.1")
    assert hashlib.sha256(archive.read_bytes()).hexdigest() in result
    assert "vendor/nltk" not in result


def test_vendor_local_source_rejects_wrong_version(tmp_path):
    archive = wheel(tmp_path / "nltk.whl", "nltk", "3.10.3")
    with pytest.raises(ValueError, match="locked version"):
        builder.vendor_requirements(
            "./vendor/nltk\n",
            [archive],
            {"./vendor/nltk": ("nltk", "3.10.3.post1+mara.1")},
        )
