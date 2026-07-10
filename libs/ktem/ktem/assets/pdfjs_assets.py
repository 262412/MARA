"""Offline, verified materialization of the vendored PDF.js distribution."""

from __future__ import annotations

import errno
import hashlib
import json
import os
import re
import shutil
import stat
import tempfile
import zipfile
from dataclasses import dataclass
from importlib import resources
from pathlib import Path, PurePosixPath

PDFJS_VERSION = "6.1.200"
PDFJS_VERSION_DIST = f"pdfjs-{PDFJS_VERSION}-dist"
PDFJS_ARCHIVE_NAME = f"{PDFJS_VERSION_DIST}.zip"
PDFJS_ARCHIVE_SHA256 = (
    "9e1584d768ed099aa4be27ea423f89a038c2005f1ee417ea4f35ba4591ec1846"
)
PDFJS_RELEASE_URL = (
    "https://github.com/mozilla/pdf.js/releases/download/v6.1.200/"
    "pdfjs-6.1.200-dist.zip"
)
PDFJS_RUNTIME_FILE_SHA256 = {
    "build/pdf.mjs": "506017c72d304788a1139393988a74c6c23c2f077a3558ac5f67555aee966950",
    "web/viewer.html": "b81716acf3653f38ded0696768a91e2b1bd1a3208786b008120cc553f1d5ac05",
}

_VENDOR_RESOURCE_PARTS = ("vendor", "pdfjs", PDFJS_ARCHIVE_NAME)
_RUNTIME_MARKER = ".mara-pdfjs.json"
_REQUIRED_FILES = ("LICENSE", "build/pdf.mjs", "web/viewer.html")
_WINDOWS_ABSOLUTE_PATH = re.compile(r"^[A-Za-z]:")


class PdfJsAssetError(RuntimeError):
    """Raised when the packaged PDF.js asset cannot be trusted or materialized."""


@dataclass(frozen=True)
class PdfJsMaterialization:
    """Result of a PDF.js materialization attempt."""

    path: Path
    created: bool


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as archive_file:
            for chunk in iter(lambda: archive_file.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as exc:
        raise PdfJsAssetError(f"Cannot read packaged PDF.js archive: {exc}") from exc
    return digest.hexdigest()


def _runtime_app_data_dir(app_data_dir: Path | str | None = None) -> Path:
    if app_data_dir is not None:
        configured = str(app_data_dir)
    else:
        configured = os.environ.get("KH_APP_DATA_DIR", "").strip()
        if not configured:
            from ktem.runtime_bootstrap import get_runtime_paths

            configured = str(get_runtime_paths().data_dir)
    return Path(configured).expanduser().resolve()


def get_pdfjs_runtime_dir(app_data_dir: Path | str | None = None) -> Path:
    """Return the single runtime PDF.js directory below ``KH_APP_DATA_DIR``."""

    return _runtime_app_data_dir(app_data_dir) / "assets" / "pdfjs" / PDFJS_VERSION


def _marker_payload(
    expected_sha256: str,
    expected_file_hashes: dict[str, str],
) -> dict[str, object]:
    return {
        "files": expected_file_hashes,
        "sha256": expected_sha256,
        "version": PDFJS_VERSION,
        "version_dist": PDFJS_VERSION_DIST,
    }


def _corrupt_destination_error(destination: Path, detail: str) -> PdfJsAssetError:
    return PdfJsAssetError(
        "PDF.js runtime directory is incomplete or corrupt "
        f"({detail}): {destination}. Remove that directory and rerun MARA app init."
    )


def _runtime_regular_files(destination: Path) -> set[str]:
    regular_files: set[str] = set()
    for runtime_path in destination.rglob("*"):
        relative_name = runtime_path.relative_to(destination).as_posix()
        if runtime_path.is_symlink():
            raise _corrupt_destination_error(
                destination,
                f"runtime symbolic link is forbidden: {relative_name}",
            )
        try:
            path_mode = runtime_path.stat().st_mode
        except OSError as exc:
            raise _corrupt_destination_error(
                destination,
                f"cannot inspect runtime path {relative_name}: {exc}",
            ) from exc
        if stat.S_ISDIR(path_mode):
            continue
        if not stat.S_ISREG(path_mode):
            raise _corrupt_destination_error(
                destination,
                f"unsupported runtime file type: {relative_name}",
            )
        if relative_name != _RUNTIME_MARKER:
            regular_files.add(relative_name)
    return regular_files


def _validate_materialized_destination(
    destination: Path,
    *,
    expected_sha256: str,
    expected_file_hashes: dict[str, str],
) -> None:
    if destination.is_symlink() or not destination.is_dir():
        raise _corrupt_destination_error(destination, "not a regular directory")

    for relative_name in _REQUIRED_FILES:
        required_path = destination / relative_name
        if required_path.is_symlink() or not required_path.is_file():
            raise _corrupt_destination_error(
                destination,
                f"missing required file {relative_name}",
            )

    marker_path = destination / _RUNTIME_MARKER
    if marker_path.is_symlink() or not marker_path.is_file():
        raise _corrupt_destination_error(destination, f"missing {_RUNTIME_MARKER}")
    try:
        marker = json.loads(marker_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise _corrupt_destination_error(
            destination,
            f"invalid {_RUNTIME_MARKER}: {exc}",
        ) from exc
    if marker != _marker_payload(expected_sha256, expected_file_hashes):
        raise _corrupt_destination_error(
            destination,
            f"unexpected {_RUNTIME_MARKER} contents",
        )

    actual_files = _runtime_regular_files(destination)
    expected_files = set(expected_file_hashes)
    unexpected_files = sorted(actual_files - expected_files)
    if unexpected_files:
        raise _corrupt_destination_error(
            destination,
            f"unexpected runtime file: {unexpected_files[0]}",
        )
    missing_files = sorted(expected_files - actual_files)
    if missing_files:
        raise _corrupt_destination_error(
            destination,
            f"missing runtime file: {missing_files[0]}",
        )
    for relative_name, expected_hash in expected_file_hashes.items():
        runtime_file = destination / relative_name
        try:
            actual_hash = _sha256(runtime_file)
        except PdfJsAssetError as exc:
            raise _corrupt_destination_error(destination, str(exc)) from exc
        if actual_hash != expected_hash:
            raise _corrupt_destination_error(
                destination,
                f"content hash mismatch for {relative_name}",
            )


def _safe_archive_path(info: zipfile.ZipInfo) -> PurePosixPath:
    name = info.filename
    if (
        not name
        or "\\" in name
        or "\x00" in name
        or name.startswith("/")
        or _WINDOWS_ABSOLUTE_PATH.match(name)
    ):
        raise PdfJsAssetError(f"Found unsafe PDF.js archive member: {name!r}")

    member_path = PurePosixPath(name)
    if member_path.is_absolute() or any(
        part in {"", ".", ".."} for part in member_path.parts
    ):
        raise PdfJsAssetError(f"Found unsafe PDF.js archive member: {name!r}")

    unix_mode = (info.external_attr >> 16) & 0xFFFF
    file_type = stat.S_IFMT(unix_mode)
    if file_type == stat.S_IFLNK:
        raise PdfJsAssetError(
            f"PDF.js archive member must not be a symbolic link: {name!r}"
        )
    if file_type not in {0, stat.S_IFREG, stat.S_IFDIR}:
        raise PdfJsAssetError(
            f"PDF.js archive member has an unsupported file type: {name!r}"
        )
    return member_path


def _validated_archive_members(
    archive: zipfile.ZipFile,
) -> list[tuple[zipfile.ZipInfo, PurePosixPath]]:
    members: list[tuple[zipfile.ZipInfo, PurePosixPath]] = []
    normalized_names: set[str] = set()
    regular_files: set[str] = set()
    for info in archive.infolist():
        member_path = _safe_archive_path(info)
        normalized_name = member_path.as_posix().rstrip("/")
        if normalized_name in normalized_names:
            raise PdfJsAssetError(
                f"PDF.js archive contains a duplicate member: {info.filename!r}"
            )
        normalized_names.add(normalized_name)
        if not info.is_dir():
            regular_files.add(member_path.as_posix())
        members.append((info, member_path))

    for required_name in _REQUIRED_FILES:
        if required_name not in regular_files:
            raise PdfJsAssetError(
                f"PDF.js archive is missing required file {required_name}."
            )
    return members


def _archive_runtime_file_hashes(
    archive: zipfile.ZipFile,
    members: list[tuple[zipfile.ZipInfo, PurePosixPath]],
) -> dict[str, str]:
    hashes: dict[str, str] = {}
    try:
        for info, relative_path in members:
            if info.is_dir():
                continue
            digest = hashlib.sha256()
            with archive.open(info, "r") as source:
                for chunk in iter(lambda: source.read(1024 * 1024), b""):
                    digest.update(chunk)
            hashes[relative_path.as_posix()] = digest.hexdigest()
    except (OSError, RuntimeError, zipfile.BadZipFile) as exc:
        raise PdfJsAssetError(
            f"Could not verify executable files in the PDF.js archive: {exc}"
        ) from exc
    return hashes


def _copy_member(
    archive: zipfile.ZipFile,
    info: zipfile.ZipInfo,
    destination: Path,
) -> None:
    if info.is_dir():
        destination.mkdir(parents=True, exist_ok=True)
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    with archive.open(info, "r") as source, destination.open("xb") as output:
        shutil.copyfileobj(source, output)


def _extract_archive(
    archive: zipfile.ZipFile,
    members: list[tuple[zipfile.ZipInfo, PurePosixPath]],
    temporary_directory: Path,
) -> None:
    try:
        for info, relative_path in members:
            _copy_member(archive, info, temporary_directory / relative_path)
    except (OSError, RuntimeError, zipfile.BadZipFile) as exc:
        raise PdfJsAssetError(f"Failed to extract PDF.js archive: {exc}") from exc


def _prepare_destination_parent(app_data_dir: Path) -> tuple[Path, Path]:
    requested_parent = app_data_dir / "assets" / "pdfjs"
    for existing_parent in (requested_parent.parent, requested_parent):
        if existing_parent.exists() or existing_parent.is_symlink():
            resolved_existing_parent = existing_parent.resolve()
            if not resolved_existing_parent.is_relative_to(app_data_dir):
                raise PdfJsAssetError(
                    "PDF.js runtime directory must remain below KH_APP_DATA_DIR; "
                    f"resolved parent was {resolved_existing_parent}."
                )
    try:
        requested_parent.mkdir(parents=True, exist_ok=True)
        resolved_parent = requested_parent.resolve()
    except OSError as exc:
        raise PdfJsAssetError(
            f"Cannot prepare PDF.js runtime directory below KH_APP_DATA_DIR: {exc}"
        ) from exc
    if not resolved_parent.is_relative_to(app_data_dir):
        raise PdfJsAssetError(
            "PDF.js runtime directory must remain below KH_APP_DATA_DIR; "
            f"resolved parent was {resolved_parent}."
        )
    return resolved_parent, resolved_parent / PDFJS_VERSION


def _write_runtime_marker(
    temporary_directory: Path,
    *,
    expected_sha256: str,
    expected_file_hashes: dict[str, str],
) -> None:
    marker_path = temporary_directory / _RUNTIME_MARKER
    try:
        marker_path.write_text(
            json.dumps(
                _marker_payload(expected_sha256, expected_file_hashes),
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
    except OSError as exc:
        raise PdfJsAssetError(f"Failed to write PDF.js runtime marker: {exc}") from exc


def _publish_runtime_directory(
    temporary_directory: Path,
    destination: Path,
    *,
    expected_sha256: str,
    expected_file_hashes: dict[str, str],
) -> PdfJsMaterialization:
    _validate_materialized_destination(
        temporary_directory,
        expected_sha256=expected_sha256,
        expected_file_hashes=expected_file_hashes,
    )
    try:
        os.rename(temporary_directory, destination)
    except OSError as exc:
        if exc.errno in {errno.EEXIST, errno.ENOTEMPTY}:
            _validate_materialized_destination(
                destination,
                expected_sha256=expected_sha256,
                expected_file_hashes=expected_file_hashes,
            )
            return PdfJsMaterialization(path=destination, created=False)
        raise PdfJsAssetError(
            f"Failed to publish PDF.js runtime directory atomically: {exc}"
        ) from exc
    return PdfJsMaterialization(path=destination, created=True)


def _materialize_pdfjs_archive(
    *,
    archive_path: Path | str,
    expected_sha256: str,
    app_data_dir: Path | str | None = None,
) -> PdfJsMaterialization:
    """Materialize one already-local PDF.js archive after strict validation."""

    archive_path = Path(archive_path)
    actual_sha256 = _sha256(archive_path)
    if actual_sha256 != expected_sha256:
        raise PdfJsAssetError(
            "PDF.js archive SHA-256 mismatch: "
            f"expected {expected_sha256}, actual {actual_sha256}."
        )

    runtime_root = _runtime_app_data_dir(app_data_dir)
    destination_parent, destination = _prepare_destination_parent(runtime_root)
    try:
        archive = zipfile.ZipFile(archive_path)
    except (OSError, zipfile.BadZipFile) as exc:
        raise PdfJsAssetError(
            f"Packaged PDF.js asset is not a valid ZIP archive: {exc}"
        ) from exc

    temporary_directory: Path | None = None
    try:
        with archive:
            try:
                members = _validated_archive_members(archive)
            except zipfile.BadZipFile as exc:
                raise PdfJsAssetError(
                    f"Packaged PDF.js asset is not a valid ZIP archive: {exc}"
                ) from exc
            expected_file_hashes = _archive_runtime_file_hashes(archive, members)
            if destination.exists() or destination.is_symlink():
                _validate_materialized_destination(
                    destination,
                    expected_sha256=expected_sha256,
                    expected_file_hashes=expected_file_hashes,
                )
                return PdfJsMaterialization(path=destination, created=False)
            temporary_directory = Path(
                tempfile.mkdtemp(
                    prefix=f".{PDFJS_VERSION}.",
                    dir=destination_parent,
                )
            )
            _extract_archive(archive, members, temporary_directory)

        assert temporary_directory is not None
        _write_runtime_marker(
            temporary_directory,
            expected_sha256=expected_sha256,
            expected_file_hashes=expected_file_hashes,
        )
        return _publish_runtime_directory(
            temporary_directory,
            destination,
            expected_sha256=expected_sha256,
            expected_file_hashes=expected_file_hashes,
        )
    finally:
        if temporary_directory is not None and temporary_directory.exists():
            shutil.rmtree(temporary_directory, ignore_errors=True)


def materialize_pdfjs(
    *,
    app_data_dir: Path | str | None = None,
) -> PdfJsMaterialization:
    """Materialize the fixed, packaged PDF.js release without network access."""

    resource = resources.files("ktem.assets")
    for part in _VENDOR_RESOURCE_PARTS:
        resource = resource.joinpath(part)
    with resources.as_file(resource) as archive_path:
        return _materialize_pdfjs_archive(
            archive_path=archive_path,
            expected_sha256=PDFJS_ARCHIVE_SHA256,
            app_data_dir=app_data_dir,
        )


def main() -> int:
    """Materialize the vendored asset for platform launcher scripts."""

    print(materialize_pdfjs().path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
