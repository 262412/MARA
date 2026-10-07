import base64
from io import BytesIO
from pathlib import Path
from typing import Dict, List, Optional

from decouple import config
from fsspec import AbstractFileSystem
from llama_index.readers.file import PDFReader as NativePDFReader
from PIL import Image

from kotaemon.base import Document

PDF_LOADER_DPI = config("PDF_LOADER_DPI", default=40, cast=int)


def get_page_thumbnails(
    file_path: Path, pages: list[int], dpi: int = PDF_LOADER_DPI
) -> List[Image.Image]:
    """Get image thumbnails of the pages in the PDF file.

    Args:
        file_path (Path): path to the image file
        page_number (list[int]): list of page numbers to extract

    Returns:
        list[Image.Image]: list of page thumbnails
    """

    img: Image.Image
    suffix = file_path.suffix.lower()
    assert suffix == ".pdf", "This function only supports PDF files."
    try:
        import fitz
    except ImportError:
        raise ImportError("Please install PyMuPDF: 'pip install PyMuPDF'")

    output_imgs = []
    with fitz.open(file_path) as doc:
        for page_number in pages:
            page = doc.load_page(page_number)
            pm = page.get_pixmap(dpi=dpi)
            img = Image.frombytes("RGB", [pm.width, pm.height], pm.samples)
            output_imgs.append(convert_image_to_base64(img))

    return output_imgs


def convert_image_to_base64(img: Image.Image) -> str:
    # convert the image into base64
    img_bytes = BytesIO()
    img.save(img_bytes, format="PNG")
    img_base64 = base64.b64encode(img_bytes.getvalue()).decode("utf-8")
    img_base64 = f"data:image/png;base64,{img_base64}"

    return img_base64


class PDFReader(NativePDFReader):
    """Add one-based positions at the native one-record-per-physical-page boundary."""

    physical_page_policy = "mara-pdf-physical-pages-v1"

    @staticmethod
    def validate_extra_info(extra_info):
        reserved = {"page_number", "page", "page_idx", "page_label"}
        if extra_info and reserved.intersection(extra_info):
            raise ValueError("PDF page position and label are parser-owned metadata")

    def load_data(self, file, extra_info=None, fs=None):
        self.validate_extra_info(extra_info)
        documents = super().load_data(file, extra_info, fs)
        if not self.return_full_document:
            # NativePDFReader emits each physical page, including empty pages,
            # before any MARA filtering/splitting. Display labels are unrelated.
            for page_number, document in enumerate(documents, 1):
                document.metadata["page_number"] = page_number
        return documents

    def valid_cached_documents(self, payload):
        if not all(
            isinstance(item, dict) and isinstance(item.get("metadata"), dict)
            for item in payload
        ):
            return False
        metadata = [item["metadata"] for item in payload]
        if self.return_full_document:
            return len(metadata) == 1 and not any(
                key in metadata[0]
                for key in ("page_number", "page", "page_idx", "page_label")
            )
        if any(
            type(item.get("page_number")) is not int or item["page_number"] < 1
            for item in metadata
        ):
            return False
        text_pages = [
            item["page_number"] for item in metadata if item.get("type") != "thumbnail"
        ]
        thumbnails = [
            item["page_number"] for item in metadata if item.get("type") == "thumbnail"
        ]
        return text_pages == list(range(1, len(text_pages) + 1)) and (
            not thumbnails or thumbnails == text_pages
        )


class PDFThumbnailReader(PDFReader):
    """PDF parser with thumbnail for each page."""

    def __init__(self) -> None:
        """
        Initialize PDFReader.
        """
        super().__init__(return_full_document=False)

    def load_data(
        self,
        file: Path,
        extra_info: Optional[Dict] = None,
        fs: Optional[AbstractFileSystem] = None,
    ) -> List[Document]:
        """Parse file."""
        documents = super().load_data(file, extra_info, fs)

        # PyMuPDF accepts zero-based positions; convert exactly at this boundary.
        page_thumbnails = get_page_thumbnails(
            file, [doc.metadata["page_number"] - 1 for doc in documents]
        )

        documents.extend(
            [
                Document(
                    text="Page thumbnail",
                    metadata={
                        "image_origin": page_thumbnail,
                        "type": "thumbnail",
                        **(extra_info if extra_info is not None else {}),
                        "page_label": document.metadata["page_label"],
                        "page_number": document.metadata["page_number"],
                    },
                )
                for page_thumbnail, document in zip(page_thumbnails, documents)
            ]
        )

        return documents
