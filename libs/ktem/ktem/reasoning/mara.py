from __future__ import annotations

from collections import Counter
from typing import Any, Generator

from kotaemon.base import Document, RetrievedDocument

from .simple import FullQAPipeline

MARA_ABSTAIN_MESSAGE = (
    "MARA could not retrieve enough evidence to answer reliably after a retry. "
    "Select a relevant source or page, or ask with more source-specific context."
)

_TASK_KEYWORDS = {
    "study_guide": ("study guide", "study-guide"),
    "flashcards": ("flashcard", "flash card"),
    "slide_outline": ("slide outline", "deck outline", "presentation outline"),
    "mindmap": ("mind map", "mindmap"),
    "quiz": ("quiz", "questions"),
    "summary": ("summary", "summarize", "summarise", "overview"),
    "compare": ("compare", "contrast", "difference", "differences"),
    "explain": ("explain", "why", "how does"),
}
_MODALITY_KEYWORDS = {
    "table": ("table", "row", "column", "spreadsheet", "csv"),
    "figure": ("figure", "image", "diagram", "chart", "plot"),
    "formula": ("formula", "equation", "math", "latex"),
    "slide": ("slide", "deck", "presentation", "ppt", "pptx"),
}
_VALID_TASK_TYPES = {
    "qa",
    "summary",
    "compare",
    "explain",
    "study_guide",
    "quiz",
    "flashcards",
    "mindmap",
    "slide_outline",
}


def _evidence_item(doc: RetrievedDocument) -> dict[str, Any]:
    metadata = dict(getattr(doc, "metadata", {}) or {})
    return {
        "evidence_id": str(getattr(doc, "doc_id", "") or "").strip(),
        "file_id": str(metadata.get("file_id") or "").strip(),
        "file_name": str(metadata.get("file_name") or "").strip(),
        "page_label": str(metadata.get("page_label") or "").strip(),
        "element_type": str(
            metadata.get("element_type")
            or metadata.get("type")
            or metadata.get("modality")
            or "text"
        ),
        "element_id": str(metadata.get("element_id") or "").strip(),
        "bbox": metadata.get("bbox"),
        "caption": str(metadata.get("caption") or "").strip(),
        "ocr_text": str(metadata.get("ocr_text") or "").strip(),
        "table_origin": str(metadata.get("table_origin") or "").strip(),
        "formula_normalized": str(metadata.get("formula_normalized") or "").strip(),
        "slide_number": metadata.get("slide_number"),
        "retrieval_path": str(metadata.get("retrieval_path") or "").strip(),
    }


def _should_retry_retrieval(agent_mode: str | None, docs: list[RetrievedDocument]):
    return str(agent_mode or "").strip().lower() == "thorough" and not docs


def _is_thorough(agent_mode: str | None) -> bool:
    return str(agent_mode or "").strip().lower() == "thorough"


def _mara_event(mara_channel: str, payload: Any) -> Document:
    return Document(
        channel="debug",
        content={"mara_channel": mara_channel, "payload": payload},
    )


def _retrieval_trace(
    docs: list[RetrievedDocument],
    evidence_metadata: dict[str, Any],
    attempts: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "event": "tool_call",
        "tool": "source_retriever",
        "evidence_ids": evidence_metadata["evidence_ids"],
        "evidence_count": len(docs),
        "attempts": attempts,
    }


def _verify_evidence(docs: list[RetrievedDocument]) -> dict[str, Any]:
    evidence_count = len(docs)
    return {
        "result": "supported" if evidence_count else "insufficient",
        "evidence_count": evidence_count,
    }


def _excerpt(text: str, limit: int = 220) -> str:
    cleaned = " ".join(str(text or "").split())
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 1].rstrip() + "..."


def _artifact_evidence(docs: list[RetrievedDocument]) -> list[dict[str, Any]]:
    evidence: list[dict[str, Any]] = []
    for doc in docs:
        item = _evidence_item(doc)
        excerpt = _excerpt(
            str(getattr(doc, "text", "") or getattr(doc, "content", "") or "")
        )
        if not excerpt:
            continue
        evidence.append(
            {
                "evidence_id": item["evidence_id"],
                "file_id": item["file_id"],
                "file_name": item["file_name"],
                "page_label": item["page_label"],
                "excerpt": excerpt,
            }
        )
    return evidence


def _evidence_label(item: dict[str, Any]) -> str:
    label = str(item.get("file_name") or item.get("evidence_id") or "source")
    page = str(item.get("page_label") or "").strip()
    return f"{label} p.{page}" if page else label


def _source_ids(item: dict[str, Any]) -> list[str]:
    file_id = str(item.get("file_id") or "").strip()
    return [file_id] if file_id else []


def _topic_from_excerpt(excerpt: str) -> str:
    words = [word.strip(".,:;!?()[]{}\"'") for word in excerpt.split()]
    return next((word for word in words if word), "the source")


def _planned_artifact(artifact_type: str) -> dict[str, Any]:
    return {
        "type": artifact_type,
        "status": "planned",
        "source": "mara_reasoning",
        "cited_evidence": [],
    }


def _study_guide_artifact(evidence: list[dict[str, Any]]) -> dict[str, Any]:
    first = evidence[0]
    concepts = [_evidence_label(item) for item in evidence[:5]]
    return {
        "type": "study_guide",
        "status": "ready",
        "source": "mara_reasoning",
        "overview": first["excerpt"],
        "key_concepts": concepts,
        "glossary": [
            {"term": _evidence_label(item), "definition": item["excerpt"]}
            for item in evidence[:5]
        ],
        "key_questions": [
            f"What does {_evidence_label(item)} show about "
            f"{_topic_from_excerpt(item['excerpt'])}?"
            for item in evidence[:5]
        ],
        "cited_evidence": evidence,
    }


def _quiz_artifact(evidence: list[dict[str, Any]]) -> dict[str, Any]:
    first = evidence[0]
    question = f"Which statement is supported by {_evidence_label(first)}?"
    return {
        "type": "quiz",
        "status": "ready",
        "source": "mara_reasoning",
        "multiple_choice": [
            {
                "question": question,
                "options": [
                    first["excerpt"],
                    "The selected evidence does not support this.",
                    "More sources are required before answering.",
                ],
                "answer": first["excerpt"],
                "source_ids": _source_ids(first),
            }
        ],
        "short_answer": [
            {
                "question": f"Summarize the evidence from {_evidence_label(first)}.",
                "answer": first["excerpt"],
                "source_ids": _source_ids(first),
            }
        ],
        "answer_key": [
            {
                "question": question,
                "answer": first["excerpt"],
                "explanation": first["excerpt"],
                "source_ids": _source_ids(first),
            }
        ],
        "cited_evidence": evidence,
    }


def _flashcards_artifact(evidence: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "type": "flashcards",
        "status": "ready",
        "source": "mara_reasoning",
        "cards": [
            {
                "front": f"What is the key point from {_evidence_label(item)}?",
                "back": item["excerpt"],
                "source_ids": _source_ids(item),
            }
            for item in evidence[:10]
        ],
        "cited_evidence": evidence,
    }


def _mindmap_artifact(evidence: list[dict[str, Any]]) -> dict[str, Any]:
    nodes = [
        {
            "id": item["evidence_id"] or f"source-{index}",
            "label": _evidence_label(item),
            "summary": item["excerpt"],
            "source_ids": _source_ids(item),
        }
        for index, item in enumerate(evidence[:10], start=1)
    ]
    return {
        "type": "mindmap",
        "status": "ready",
        "source": "mara_reasoning",
        "nodes": nodes,
        "edges": [
            {"source": nodes[0]["id"], "target": node["id"]}
            for node in nodes[1:]
            if nodes
        ],
        "cited_evidence": evidence,
    }


def _slide_outline_artifact(evidence: list[dict[str, Any]]) -> dict[str, Any]:
    slides = [
        {
            "title": _evidence_label(item),
            "bullets": [item["excerpt"]],
            "source_ids": _source_ids(item),
        }
        for item in evidence[:8]
    ]
    return {
        "type": "slide_outline",
        "status": "ready",
        "source": "mara_reasoning",
        "title": "Source-grounded MARA outline",
        "sections": [{"title": "Evidence-backed narrative", "slides": slides}],
        "cited_evidence": evidence,
    }


def _build_artifact_for_pipeline(
    pipeline: Any, understanding: dict[str, Any]
) -> dict[str, Any] | None:
    artifact_type = str(getattr(pipeline, "artifact_type", "") or "").strip()
    if not artifact_type:
        task_type = str(understanding.get("task_type") or "")
        artifact_type = task_type if task_type != "qa" else ""
    if artifact_type not in {
        "study_guide",
        "quiz",
        "flashcards",
        "mindmap",
        "slide_outline",
    }:
        return None
    evidence = _artifact_evidence(list(getattr(pipeline, "_mara_last_docs", [])))
    if not evidence:
        return _planned_artifact(artifact_type)
    builders = {
        "study_guide": _study_guide_artifact,
        "quiz": _quiz_artifact,
        "flashcards": _flashcards_artifact,
        "mindmap": _mindmap_artifact,
        "slide_outline": _slide_outline_artifact,
    }
    return builders[artifact_type](evidence)


class MaraAgentPipeline(FullQAPipeline):
    """MARA agentic wrapper around the existing DocQA retrieval stack."""

    class Config:
        allow_extra = True

    @classmethod
    def get_info(cls) -> dict:
        return {
            "id": "mara",
            "name": "MARA Agentic Multimodal QA",
            "description": (
                "Routes each DocQA request through MARA query understanding, "
                "modality-aware planning, evidence retrieval, and verification."
            ),
        }

    @classmethod
    def get_user_settings(cls) -> dict:
        settings = super().get_user_settings()
        settings["agent_mode"] = {
            "name": "MARA agent mode",
            "value": "auto",
            "component": "radio",
            "choices": [
                ("auto", "auto"),
                ("fast", "fast"),
                ("thorough", "thorough"),
            ],
            "info": "Controls MARA planning depth before answer composition.",
        }
        return settings

    @classmethod
    def prepare_pipeline_instance(cls, settings, retrievers):
        pipeline = super().prepare_pipeline_instance(settings, retrievers)
        prefix = f"reasoning.options.{cls.get_info()['id']}"
        pipeline.agent_mode = settings.get(f"{prefix}.agent_mode", "auto")
        return pipeline

    @classmethod
    def understand_query(
        cls,
        query: str,
        *,
        task_type: str | None = None,
        qa_scope: str | None = None,
        active_file_id: str | None = None,
        page_number: int | None = None,
    ) -> dict[str, Any]:
        normalized = str(query or "").lower()
        normalized_task = str(task_type or "").strip().lower()
        if normalized_task in _VALID_TASK_TYPES:
            detected_task = normalized_task
        else:
            detected_task = "qa"
            for candidate, keywords in _TASK_KEYWORDS.items():
                if any(keyword in normalized for keyword in keywords):
                    detected_task = candidate
                    break

        modalities = [
            modality
            for modality, keywords in _MODALITY_KEYWORDS.items()
            if any(keyword in normalized for keyword in keywords)
        ]
        if not modalities:
            modalities = ["text"]

        explicit_scope = str(qa_scope or "").strip().lower().replace("-", "_")
        if explicit_scope in {"page", "document", "multi_document"}:
            scope = explicit_scope
        elif page_number is not None or "page " in normalized:
            scope = "page"
        elif active_file_id:
            scope = "document"
        else:
            scope = "document"

        return {
            "task_type": detected_task,
            "modalities": modalities,
            "scope": scope,
        }

    @classmethod
    def plan_steps(
        cls, understanding: dict[str, Any], *, agent_mode: str | None = None
    ) -> list[dict[str, str]]:
        mode = str(agent_mode or "auto").strip().lower()
        task_type = str(understanding.get("task_type") or "qa")
        scope = str(understanding.get("scope") or "document").replace("_", "-")
        modalities = [
            str(modality)
            for modality in understanding.get("modalities", ["text"])
            if modality
        ]
        if not modalities:
            modalities = ["text"]

        modality_text = ", ".join(modalities)
        plan = [
            {
                "tool": "source_retriever",
                "purpose": (
                    f"Retrieve {modality_text} evidence for "
                    f"{scope}-scoped {task_type}."
                ),
            }
        ]
        if mode == "fast":
            return plan

        for modality in modalities:
            if modality == "text":
                continue
            plan.append(
                {
                    "tool": f"{modality}_inspector",
                    "purpose": (
                        f"Inspect retrieved {modality} evidence before composing "
                        "the answer."
                    ),
                }
            )
            if len(plan) >= 3:
                break

        if mode == "thorough":
            plan.append(
                {
                    "tool": "claim_verifier",
                    "purpose": (
                        "Check whether the answer is supported by retrieved evidence."
                    ),
                }
            )

        return plan[:4]

    def retrieve(
        self, message: str, history: list
    ) -> tuple[list[RetrievedDocument], list[Document]]:
        cached = getattr(self, "_mara_cached_retrieval", None)
        if cached and cached[0] == message and cached[1] == list(history):
            delattr(self, "_mara_cached_retrieval")
            docs, info = cached[2], cached[3]
            self._mara_last_docs = list(docs)
            return docs, info

        docs, info = super().retrieve(message, history)
        attempts = [{"attempt": 1, "evidence_count": len(docs), "retry_reason": ""}]
        if _should_retry_retrieval(getattr(self, "agent_mode", None), docs):
            docs, info = super().retrieve(message, history)
            attempts.append(
                {
                    "attempt": 2,
                    "evidence_count": len(docs),
                    "retry_reason": "insufficient_evidence",
                }
            )
        self._mara_retrieval_attempts = attempts
        self._mara_last_docs = list(docs)
        return docs, info

    def stream(  # type: ignore
        self, message: str, conv_id: str, history: list, **kwargs  # type: ignore
    ) -> Generator[Document, None, Document]:
        understanding = self.understand_query(
            message,
            task_type=getattr(self, "task_type", None),
            qa_scope=getattr(self, "qa_scope", None),
            active_file_id=getattr(self, "active_file_id", None),
            page_number=getattr(self, "page_number", None),
        )
        plan = self.plan_steps(
            understanding,
            agent_mode=getattr(self, "agent_mode", "auto"),
        )
        yield _mara_event(
            "agent_trace",
            {
                "event": "route",
                "task_type": understanding["task_type"],
                "modalities": understanding["modalities"],
                "scope": understanding["scope"],
                "agent_mode": getattr(self, "agent_mode", "auto") or "auto",
                "plan": plan,
            },
        )

        if _is_thorough(getattr(self, "agent_mode", None)):
            docs, info = self.retrieve(message, history)
            if not docs:
                evidence_metadata = self.build_evidence_metadata(docs, understanding)
                yield _mara_event(
                    "agent_trace",
                    _retrieval_trace(
                        docs,
                        evidence_metadata,
                        getattr(self, "_mara_retrieval_attempts", []),
                    ),
                )
                yield _mara_event(
                    "agent_trace",
                    {
                        "event": "verify",
                        "result": "insufficient",
                        "evidence_count": 0,
                        "decision": "abstain",
                    },
                )
                yield _mara_event("evidence_metadata", evidence_metadata)
                yield Document(channel="chat", content=MARA_ABSTAIN_MESSAGE)
                return Document(channel="chat", content=MARA_ABSTAIN_MESSAGE)
            self._mara_cached_retrieval = (message, list(history), docs, info)

        answer = yield from super().stream(message, conv_id, history, **kwargs)
        docs = list(getattr(self, "_mara_last_docs", []))
        evidence_metadata = self.build_evidence_metadata(docs, understanding)
        verification = _verify_evidence(docs)
        yield _mara_event(
            "agent_trace",
            _retrieval_trace(
                docs,
                evidence_metadata,
                getattr(self, "_mara_retrieval_attempts", []),
            ),
        )
        yield _mara_event(
            "agent_trace",
            {
                "event": "verify",
                "result": verification["result"],
                "evidence_count": verification["evidence_count"],
            },
        )
        yield _mara_event("evidence_metadata", evidence_metadata)

        artifact = self.build_artifact(understanding)
        if artifact is not None:
            yield _mara_event("artifact", artifact)
        return answer

    @staticmethod
    def build_evidence_metadata(
        docs: list[RetrievedDocument], understanding: dict[str, Any]
    ) -> dict[str, Any]:
        modality_counts: Counter[str] = Counter()
        page_coverage: list[str] = []
        source_ids: list[str] = []
        evidence_ids: list[str] = []
        evidence = []

        for doc in docs:
            item = _evidence_item(doc)
            evidence.append(item)
            modality = item["element_type"]
            modality_counts[modality] += 1

            page_label = item["page_label"]
            if page_label and page_label not in page_coverage:
                page_coverage.append(page_label)

            file_id = item["file_id"]
            if file_id and file_id not in source_ids:
                source_ids.append(file_id)

            evidence_id = item["evidence_id"]
            if evidence_id:
                evidence_ids.append(evidence_id)

        return {
            "requested_modalities": list(understanding.get("modalities", [])),
            "modality_counts": dict(modality_counts),
            "page_coverage": page_coverage,
            "source_ids": source_ids,
            "evidence_ids": evidence_ids,
            "evidence": evidence,
        }

    def build_artifact(self, understanding: dict[str, Any]) -> dict[str, Any] | None:
        return _build_artifact_for_pipeline(self, understanding)
