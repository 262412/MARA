from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Iterable

SIDECAR_SUFFIX = ".mara-elements.json"
PARSER_BACKEND = "pymupdf_text_blocks"


def build_pdf_ocr_layout_sidecar(
    pdf_path: str | Path,
    *,
    document_id: str | None = None,
    fitz_module: Any | None = None,
) -> dict[str, Any]:
    path = Path(pdf_path)
    fitz = fitz_module or _import_fitz()
    document = fitz.open(str(path))
    try:
        records = [
            record
            for page_number in range(1, len(document) + 1)
            for record in _page_records(
                document.load_page(page_number - 1),
                page_number,
            )
        ]
    finally:
        close = getattr(document, "close", None)
        if callable(close):
            close()

    return {
        "schema_version": "1",
        "parser_backend": PARSER_BACKEND,
        "source_document_id": document_id or path.stem,
        "source_file_name": path.name,
        "layout_elements": records,
    }


def write_pdf_ocr_layout_sidecar(
    pdf_path: str | Path,
    output_dir: str | Path,
    *,
    document_id: str | None = None,
    fitz_module: Any | None = None,
) -> Path:
    path = Path(pdf_path)
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    sidecar = build_pdf_ocr_layout_sidecar(
        path,
        document_id=document_id,
        fitz_module=fitz_module,
    )
    out_path = sidecar_path_for_pdf(path, out_dir)
    out_path.write_text(
        json.dumps(sidecar, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return out_path


def sidecar_path_for_pdf(pdf_path: str | Path, output_dir: str | Path) -> Path:
    return Path(output_dir) / f"{Path(pdf_path).name}{SIDECAR_SUFFIX}"


def _page_records(page: Any, page_number: int) -> list[dict[str, Any]]:
    records = []
    for block_index, block in enumerate(_text_blocks(page), start=1):
        text = _block_text(block)
        if not text:
            continue
        element_type = _infer_element_type(text)
        records.append(
            {
                "page_label": str(page_number),
                "element_id": f"{element_type}-{page_number}-{block_index}",
                "element_id_aliases": _element_id_aliases(element_type, block_index),
                "element_type": element_type,
                "element_type_aliases": _element_type_aliases(element_type),
                "type": element_type,
                "text": text,
                "bbox": _block_bbox(block),
                "metadata": {
                    "parser_backend": PARSER_BACKEND,
                    "block_index": block_index,
                    "element_id_aliases": _element_id_aliases(
                        element_type, block_index
                    ),
                    "element_type_aliases": _element_type_aliases(element_type),
                },
            }
        )
    return records


def _text_blocks(page: Any) -> Iterable[Any]:
    return page.get_text("blocks", sort=True) or []


def _block_text(block: Any) -> str:
    if isinstance(block, dict):
        raw_text = block.get("text", "")
    elif isinstance(block, (list, tuple)) and len(block) >= 5:
        raw_text = block[4]
    else:
        raw_text = ""
    lines = [line.strip() for line in str(raw_text or "").splitlines()]
    return "\n".join(line for line in lines if line)


def _block_bbox(block: Any) -> list[float] | None:
    if isinstance(block, dict):
        bbox = block.get("bbox")
    elif isinstance(block, (list, tuple)) and len(block) >= 4:
        bbox = block[:4]
    else:
        bbox = None
    if not isinstance(bbox, (list, tuple)) or len(bbox) != 4:
        return None
    return [float(value) for value in bbox]


def _infer_element_type(text: str) -> str:
    lines = [line for line in str(text or "").splitlines() if line.strip()]
    numeric_tokens = re.findall(r"[$(]?\d[\d,]*(?:\.\d+)?%?\)?", text)
    if len(lines) >= 2 and len(numeric_tokens) >= 4:
        return "table"
    return "text"


def _element_id_aliases(element_type: str, block_index: int) -> list[str]:
    aliases = [f"{element_type}{block_index}", f"text{block_index}"]
    aliases.append(f"image{block_index}")
    return _unique(aliases)


def _element_type_aliases(element_type: str) -> list[str]:
    aliases = [element_type]
    if element_type in {"table", "text"}:
        aliases.extend(["figure", "image"])
    return _unique(aliases)


def _unique(values: list[str]) -> list[str]:
    output: list[str] = []
    for value in values:
        item = str(value or "").strip()
        if item and item not in output:
            output.append(item)
    return output


def _import_fitz() -> Any:
    try:
        import fitz
    except ImportError as exc:
        raise RuntimeError(
            "PyMuPDF is required to build PDF OCR/layout sidecars."
        ) from exc
    return fitz


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build non-gold OCR/layout sidecars from PDF text blocks.",
    )
    parser.add_argument("pdfs", nargs="+", help="PDF files to process.")
    parser.add_argument(
        "--output-dir",
        required=True,
        help="Directory where .mara-elements.json sidecars will be written.",
    )
    args = parser.parse_args(argv)

    output_dir = Path(args.output_dir)
    for raw_pdf in args.pdfs:
        path = Path(raw_pdf)
        written = write_pdf_ocr_layout_sidecar(
            path,
            output_dir,
            document_id=path.stem,
        )
        print(written)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
