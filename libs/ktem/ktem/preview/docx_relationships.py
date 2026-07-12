from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from docx.oxml.ns import qn

from .docx_security import (
    DocxHtmlBudget,
    DocxImageBudget,
    escaped_html_length,
    safe_hyperlink_target,
    safe_raster_data_url,
)

DOCX_NAMESPACES = {
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    "wp": "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing",
}


@dataclass(frozen=True)
class EmbeddedImage:
    alt_text: str
    data_url: str


class DocxRelationshipResolver:
    def __init__(
        self,
        relationships: Mapping[str, object],
        image_budget: DocxImageBudget,
        html_budget: DocxHtmlBudget,
    ) -> None:
        self._relationships = relationships
        self._image_budget = image_budget
        self._html_budget = html_budget

    def hyperlink_target(self, hyperlink_element) -> str:
        relationship_id = hyperlink_element.attrib.get(qn("r:id"), "")
        relationship = self._relationships.get(relationship_id)
        if relationship is None:
            return ""
        target = str(getattr(relationship, "target_ref", "") or "")
        return safe_hyperlink_target(target)

    def embedded_image(
        self,
        drawing_element,
        *,
        markup_chars: int,
    ) -> EmbeddedImage:
        alt_text = self._image_alt_text(drawing_element)
        blip = drawing_element.find(".//a:blip", DOCX_NAMESPACES)
        if blip is None:
            return EmbeddedImage(alt_text, "")
        relationship_id = blip.attrib.get(qn("r:embed"), "")
        relationship = self._relationships.get(relationship_id)
        if relationship is None or getattr(relationship, "is_external", False):
            return EmbeddedImage(alt_text, "")
        part = getattr(relationship, "target_part", None)
        content_type = str(getattr(part, "content_type", "") or "")
        blob = getattr(part, "blob", b"")
        payload = bytes(blob) if isinstance(blob, (bytes, bytearray)) else b""
        return EmbeddedImage(
            alt_text,
            safe_raster_data_url(
                content_type,
                payload,
                budget=self._image_budget,
                html_budget=self._html_budget,
                rendered_html_chars=markup_chars + escaped_html_length(alt_text),
            ),
        )

    @staticmethod
    def _image_alt_text(drawing_element) -> str:
        properties = drawing_element.find(".//wp:docPr", DOCX_NAMESPACES)
        if properties is None:
            return ""
        return str(
            properties.attrib.get("descr")
            or properties.attrib.get("title")
            or properties.attrib.get("name")
            or ""
        )
