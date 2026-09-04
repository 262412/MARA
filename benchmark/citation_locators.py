from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ktem.docqa.evidence_identity import EvidenceIdentity, identity_of


@dataclass(frozen=True, slots=True)
class CitationLocator:
    kind: str
    source_id: str = ""
    page_label: str = ""
    evidence_identity: str = ""
    span: str = ""

    @classmethod
    def from_mapping(cls, value: dict[str, Any]) -> CitationLocator:
        evidence_identity = str(value.get("evidence_id") or "").strip()
        kind = str(value.get("kind") or "").strip().lower()
        if not kind:
            kind = _kind_from_identity(evidence_identity)
        if not kind:
            kind = "page" if value.get("page_label") or value.get("page") else "source"
        return cls(
            kind=kind,
            source_id=str(value.get("source_id") or "").strip(),
            page_label=str(value.get("page_label") or value.get("page") or "").strip(),
            evidence_identity=evidence_identity,
            span=str(value.get("span") or "").strip(),
        )

    def as_dict(self) -> dict[str, str]:
        return {
            key: value
            for key, value in {
                "kind": self.kind,
                "evidence_id": self.evidence_identity,
                "source_id": self.source_id,
                "page_label": self.page_label,
                "span": self.span,
            }.items()
            if value
        }

    def page_evidence_record(self) -> dict[str, Any]:
        if self.kind not in {"page", "source"}:
            raise ValueError("Only page/source citations have locator-only records.")
        local_id = self.page_label or "source"
        identity = EvidenceIdentity(self.source_id, self.kind, local_id)
        return {
            "canonical_id": identity.key,
            "identity": identity.as_dict(),
            "source_id": self.source_id,
            "page_label": self.page_label,
            "evidence_level": self.kind,
            "modality": "page" if self.kind == "page" else "source",
            "source_backrefs": [
                (
                    f"{self.source_id}#page:{self.page_label}"
                    if self.page_label
                    else f"{self.source_id}#source"
                )
            ],
        }


def citation_kind_for_item(item: dict[str, Any]) -> str:
    return identity_of(item).kind


def _kind_from_identity(value: str) -> str:
    prefix = str(value or "").split(":", 1)[0].strip().lower()
    return prefix if prefix in {"cell", "span", "element", "chunk", "evidence"} else ""
