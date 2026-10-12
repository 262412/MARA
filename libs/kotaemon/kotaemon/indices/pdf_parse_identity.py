"""Identity for the installed PDF reader stack, independent of caller policy."""

import hashlib
import importlib.metadata
import inspect
import sys
from pathlib import Path
from typing import Any

from kotaemon.base import Document


class PDFParseIdentityUnavailable(ValueError):
    """The installed reader cannot be identified reliably enough to reuse output."""


def pdf_parse_identity(loader: Any, path: Path) -> dict[str, Any] | None:
    reader = getattr(loader, "_reader", loader)
    classes = {type(loader), type(reader), Document}
    pdf_bases = {
        cls
        for cls in type(reader).__mro__
        if cls.__module__ == "llama_index.readers.file.docs.base"
        and cls.__name__ == "PDFReader"
    }
    if not pdf_bases:
        if reader is not loader and path.suffix.casefold() == ".pdf":
            raise PDFParseIdentityUnavailable(
                f"Unidentified wrapped PDF reader {type(reader).__module__}.{type(reader).__qualname__}"
            )
        return None
    classes.update(pdf_bases)
    distributions = ["llama-index-readers-file", "llama-index-core"]
    parameters = {}
    if pdf_bases:
        distributions.append("pypdf")
        parameters["return_full_document"] = reader.return_full_document
        parameters["physical_page_policy"] = getattr(
            reader, "physical_page_policy", None
        )
    thumbnail = any(
        cls.__module__ == "kotaemon.loaders.pdf_loader"
        and cls.__name__ == "PDFThumbnailReader"
        for cls in type(reader).__mro__
    )
    if thumbnail:
        distributions.extend(["PyMuPDF", "Pillow"])
        parameters["thumbnail_dpi"] = sys.modules[
            "kotaemon.loaders.pdf_loader"
        ].PDF_LOADER_DPI
    try:
        implementations = {
            f"{cls.__module__}.{cls.__qualname__}": hashlib.sha256(
                Path(inspect.getfile(cls)).read_bytes()
            ).hexdigest()
            for cls in classes
        }
        versions = {name: importlib.metadata.version(name) for name in distributions}
        if not all(versions.values()):
            raise ValueError("empty distribution version")
    except (
        OSError,
        TypeError,
        ValueError,
        importlib.metadata.PackageNotFoundError,
    ) as exc:
        raise PDFParseIdentityUnavailable(str(exc)) from exc
    return {
        "policy": "mara-pdf-reader-identity-v2",
        "implementations": implementations,
        "distributions": versions,
        "parameters": parameters,
    }


def physical_pdf_reader(loader: Any) -> Any:
    reader = getattr(loader, "_reader", loader)
    if getattr(reader, "physical_page_policy", None) == "mara-pdf-physical-pages-v1":
        return reader
    return None
