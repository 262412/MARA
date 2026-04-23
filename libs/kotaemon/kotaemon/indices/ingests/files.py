from pathlib import Path
from typing import Type

from decouple import config
from llama_index.core.readers.base import BaseReader
from llama_index.readers.file import PDFReader
from theflow.settings import settings as flowsettings

from kotaemon.base import BaseComponent, Document, Param
from kotaemon.indices.extractors import BaseDocParser
from kotaemon.indices.extractors.doc_parsers import ElementDocParser
from kotaemon.indices.elements import annotate_document_with_element_metadata
from kotaemon.indices.splitters import BaseSplitter, TokenSplitter
from kotaemon.loaders import (
    AdobeReader,
    AzureAIDocumentIntelligenceLoader,
    DirectoryReader,
    DoclingReader,
    HtmlReader,
    MathpixPDFReader,
    MhtmlReader,
    OCRReader,
    PandasExcelReader,
    PDFThumbnailReader,
    TxtReader,
    UnstructuredReader,
    WebReader,
)

web_reader = WebReader()
unstructured = UnstructuredReader()
adobe_reader = AdobeReader()
azure_reader = AzureAIDocumentIntelligenceLoader(
    endpoint=str(config("AZURE_DI_ENDPOINT", default="")),
    credential=str(config("AZURE_DI_CREDENTIAL", default="")),
    cache_dir=getattr(flowsettings, "KH_MARKDOWN_OUTPUT_DIR", None),
)
docling_reader = DoclingReader()
adobe_reader.vlm_endpoint = (
    azure_reader.vlm_endpoint
) = docling_reader.vlm_endpoint = getattr(flowsettings, "KH_VLM_ENDPOINT", "")


KH_DEFAULT_FILE_EXTRACTORS: dict[str, BaseReader] = {
    ".xlsx": PandasExcelReader(),
    ".docx": unstructured,
    ".pptx": unstructured,
    ".ppt": unstructured,
    ".xls": unstructured,
    ".doc": unstructured,
    ".html": HtmlReader(),
    ".mhtml": MhtmlReader(),
    ".png": unstructured,
    ".jpeg": unstructured,
    ".jpg": unstructured,
    ".tiff": unstructured,
    ".tif": unstructured,
    ".pdf": PDFThumbnailReader(),
    ".txt": TxtReader(),
    ".md": TxtReader(),
}


class DocumentIngestor(BaseComponent):
    """Ingest common office document types into Document for indexing

    Document types:
        - pdf
        - xlsx, xls
        - docx, doc
        - pptx, ppt

    Args:
        pdf_mode: mode for pdf extraction, one of "normal", "mathpix", "ocr"
            - normal: parse pdf text
            - mathpix: parse pdf text using mathpix
            - ocr: parse pdf image using flax
        doc_parsers: list of document parsers to parse the document
        text_splitter: splitter to split the document into text nodes
        override_file_extractors: override file extractors for specific file extensions
            The default file extractors are stored in `KH_DEFAULT_FILE_EXTRACTORS`
    """

    pdf_mode: str = "normal"  # "normal", "mathpix", "ocr", "multimodal"
    doc_parsers: list[BaseDocParser] = Param(default_callback=lambda _: [])
    text_splitter: BaseSplitter = TokenSplitter.withx(
        chunk_size=1024,
        chunk_overlap=256,
        separator="\n\n",
        backup_separators=["\n", ".", " ", "\u200B"],
    )
    override_file_extractors: dict[str, Type[BaseReader]] = {}

    def _get_reader(self, input_files: list[str | Path]):
        """Get appropriate readers for the input files based on file extension"""
        file_extractors: dict[str, BaseReader] = {
            ext: reader for ext, reader in KH_DEFAULT_FILE_EXTRACTORS.items()
        }
        for ext, cls in self.override_file_extractors.items():
            file_extractors[ext] = cls()

        if self.pdf_mode == "normal":
            file_extractors[".pdf"] = PDFReader()
        elif self.pdf_mode == "ocr":
            file_extractors[".pdf"] = OCRReader()
        elif self.pdf_mode == "multimodal":
            file_extractors[".pdf"] = AdobeReader()
        else:
            file_extractors[".pdf"] = MathpixPDFReader()

        main_reader = DirectoryReader(
            input_files=input_files,
            file_extractor=file_extractors,
        )

        return main_reader

    def _normalize_source_documents(self, documents: list[Document]) -> list[Document]:
        """Normalize loader output into element-aware documents before splitting."""

        normalized = [
            annotate_document_with_element_metadata(document) for document in documents
        ]
        return ElementDocParser()(normalized)

    def _normalize_split_nodes(
        self, nodes: list[Document], source_documents: list[Document]
    ) -> list[Document]:
        source_by_element_id = {
            document.metadata["element_id"]: document
            for document in source_documents
            if document.metadata.get("element_id")
        }
        non_page_sources = [
            document
            for document in source_documents
            if document.metadata.get("element_type") != "page"
        ]

        for node in nodes:
            metadata = dict(node.metadata or {})
            source = self._resolve_split_source(
                node=node,
                metadata=metadata,
                source_by_element_id=source_by_element_id,
                non_page_sources=non_page_sources,
            )
            if source is not None:
                self._copy_element_metadata_to_chunk(metadata, source.metadata)
                source_element_id = source.metadata.get("element_id")
                if source_element_id:
                    metadata.setdefault("parent_element_id", source_element_id)
                    if metadata.get("element_id") == source_element_id:
                        metadata.pop("element_id", None)
            node.metadata = metadata
            annotate_document_with_element_metadata(node)
        return nodes

    @staticmethod
    def _resolve_split_source(
        *,
        node: Document,
        metadata: dict,
        source_by_element_id: dict[str, Document],
        non_page_sources: list[Document],
    ) -> Document | None:
        for key in ("parent_element_id", "element_id"):
            element_id = metadata.get(key)
            if element_id in source_by_element_id:
                return source_by_element_id[element_id]

        node_text = str(getattr(node, "text", "") or "")
        if node_text:
            for source in non_page_sources:
                source_text = str(getattr(source, "text", "") or "")
                if node_text in source_text:
                    return source

        if len(non_page_sources) == 1:
            return non_page_sources[0]
        return None

    @staticmethod
    def _copy_element_metadata_to_chunk(metadata: dict, source_metadata: dict) -> None:
        for key in (
            "type",
            "element_type",
            "source_id",
            "file_name",
            "page_number",
            "page_label",
            "bbox",
            "parser",
            "confidence",
            "caption",
            "ocr_text",
            "raw_pdf_text",
            "normalized_formula",
            "formula_text",
            "image_origin",
            "table_origin",
            "table_json",
            "formula_json",
            "formula_image_json",
            "layout_blocks_json",
        ):
            if source_metadata.get(key) is not None:
                metadata.setdefault(key, source_metadata[key])

    def run(self, file_paths: list[str | Path] | str | Path) -> list[Document]:
        """Ingest the file paths into Document

        Args:
            file_paths: list of file paths or a single file path

        Returns:
            list of parsed Documents
        """
        if not isinstance(file_paths, list):
            file_paths = [file_paths]

        documents = self._get_reader(input_files=file_paths)()
        print(f"Read {len(file_paths)} files into {len(documents)} documents.")
        documents = self._normalize_source_documents(documents)
        nodes = self.text_splitter(documents)
        nodes = self._normalize_split_nodes(nodes, documents)
        print(f"Transform {len(documents)} documents into {len(nodes)} nodes.")
        self.log_progress(".num_docs", num_docs=len(nodes))

        # document parsers call
        if self.doc_parsers:
            for parser in self.doc_parsers:
                nodes = parser(nodes)

        return nodes
