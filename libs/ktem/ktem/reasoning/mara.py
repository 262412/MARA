from __future__ import annotations

from types import SimpleNamespace
from typing import Any, Generator

from ktem.docqa.execution import RouteExecutionResult, execute_controller_turn
from ktem.docqa.graph_index import graph_answer_from_evidence

from kotaemon.base import Document, RetrievedDocument

from .mara_artifacts import build_artifact_for_pipeline
from .mara_controller import planner_trace_payload
from .mara_evidence import build_mara_evidence_metadata
from .mara_route_retrieval import route_retrieval_metadata
from .simple import FullQAPipeline

MARA_ABSTAIN_MESSAGE = (
    "MARA could not retrieve enough evidence to answer reliably after a retry. "
    "Select a relevant source or page, or ask with more source-specific context."
)
MARA_DIRECT_MESSAGE = (
    "MARA is ready to answer questions about your selected documents. "
    "Ask a source-specific question to retrieve evidence."
)
MARA_PLANNER_ABSTAIN_MESSAGE = (
    "MARA could not identify a safe document-grounded route for this question. "
    "Select relevant sources or ask a source-specific question."
)
MARA_VISUAL_EVIDENCE_ONLY_MESSAGE = (
    "MARA found visual page evidence, but no VLM backend is configured. "
    "Use the cited page evidence or configure a visual generator for a grounded "
    "visual answer."
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
_ROUTE_POLICY_ALIASES = {
    "direct": "direct",
    "doc": "doc_text",
    "document": "doc_text",
    "text": "doc_text",
    "visual": "doc_page_image",
    "page_image": "doc_page_image",
    "page-image": "doc_page_image",
    "element": "doc_element",
    "graph": "graph_global",
    "hybrid": "hybrid",
    "abstain": "abstain",
}


def _should_retry_retrieval(agent_mode: str | None, docs: list[RetrievedDocument]):
    return str(agent_mode or "").strip().lower() == "thorough" and not docs


def _mara_event(mara_channel: str, payload: Any) -> Document:
    return Document(
        channel="debug",
        content={"mara_channel": mara_channel, "payload": payload},
    )


def _route_trace_payload(
    understanding: dict[str, Any],
    agent_mode: str | None,
    plan: list[dict[str, str]],
) -> dict[str, Any]:
    return {
        "event": "route",
        "task_type": understanding["task_type"],
        "modalities": understanding["modalities"],
        "scope": understanding["scope"],
        "agent_mode": agent_mode or "auto",
        "plan": plan,
    }


def _planner_route(planner_payload: dict[str, Any]) -> str:
    decision = planner_payload.get("decision")
    if not isinstance(decision, dict):
        return ""
    return str(decision.get("route") or "").strip()


def _effective_route(pipeline: Any, planner_payload: dict[str, Any]) -> str:
    policy = str(getattr(pipeline, "route_policy", "") or "").strip().lower()
    policy = policy.replace("-", "_")
    if policy and policy != "auto":
        return _ROUTE_POLICY_ALIASES.get(policy, policy)
    planner_route = _planner_route(planner_payload)
    return _ROUTE_POLICY_ALIASES.get(planner_route, planner_route)


def _controller_execution_request(
    pipeline: Any,
    message: str,
) -> SimpleNamespace:
    return SimpleNamespace(
        prompt=message,
        controller_mode="llm",
        route_policy=getattr(pipeline, "route_policy", None) or "auto",
        allowed_routes=list(getattr(pipeline, "allowed_routes", None) or []),
        verification_mode=getattr(pipeline, "verification_mode", None) or "light",
        active_file_id=getattr(pipeline, "active_file_id", "") or "",
        active_file_name=getattr(pipeline, "active_file_name", "") or "",
        page_number=getattr(pipeline, "page_number", None),
        selected_text=getattr(pipeline, "selected_text", "") or "",
        selected_file_ids=list(getattr(pipeline, "selected_file_ids", None) or []),
        graph_context=getattr(pipeline, "graph_context", None) or {},
    )


def _collect_text_rag_generation(
    pipeline: Any,
    message: str,
    conv_id: str,
    history: list,
    kwargs: dict[str, Any],
) -> tuple[str, list[Document]]:
    events: list[Document] = []
    answer = ""
    stream = super(MaraAgentPipeline, pipeline).stream(
        message, conv_id, history, **kwargs
    )
    while True:
        try:
            event = next(stream)
        except StopIteration as stop:
            returned = stop.value
            break
        events.append(event)
        if isinstance(event, Document) and event.channel == "chat":
            answer += "" if event.content is None else str(event.content)
    if not answer and isinstance(returned, Document) and returned.channel == "chat":
        answer = "" if returned.content is None else str(returned.content)
    return answer, events


def _execution_trace_events(
    execution: RouteExecutionResult,
) -> Generator[Document, None, None]:
    for item in execution.controller_trace:
        stage = item.get("stage")
        if stage == "planner":
            continue
        payload = dict(item)
        payload["event"] = str(stage or "controller")
        payload["route"] = execution.controller_decision.route
        yield _mara_event("agent_trace", payload)


def _route_execution_events(
    execution: RouteExecutionResult,
    generation_events: list[Document],
    artifact: Any,
) -> Generator[Document, None, Document]:
    for event in _execution_trace_events(execution):
        yield event
    yield _mara_event("evidence_metadata", execution.evidence_bundle.metadata)
    visible_answer = _visible_execution_answer(execution)
    if execution.guardrail_decision.action == "return":
        if generation_events:
            for event in generation_events:
                yield event
        else:
            yield Document(channel="chat", content=visible_answer)
        if artifact is not None:
            yield _mara_event("artifact", artifact)
        return Document(channel="chat", content=visible_answer)
    yield Document(channel="chat", content=MARA_ABSTAIN_MESSAGE)
    return Document(channel="chat", content=MARA_ABSTAIN_MESSAGE)


def _visual_evidence_only_answer(bundle: Any) -> str:
    pages = [
        f"{item.get('source_name') or item.get('source_id')} page {item.get('page_label')}"
        for item in bundle.items
        if item.get("modality") == "page_image"
    ]
    if not pages:
        return MARA_VISUAL_EVIDENCE_ONLY_MESSAGE
    preview = "; ".join(str(page) for page in pages[:3])
    return f"{MARA_VISUAL_EVIDENCE_ONLY_MESSAGE} Evidence: {preview}."


def _visual_generator_answer(generator: Any, request: Any, bundle: Any) -> str:
    if hasattr(generator, "generate"):
        return str(generator.generate(request, bundle))
    if callable(generator):
        return str(generator(request, bundle))
    raise ValueError("Configured visual generator must be callable or expose generate.")


def _visible_execution_answer(execution: RouteExecutionResult) -> str:
    route = execution.controller_decision.route
    if route == "direct_answer":
        return MARA_DIRECT_MESSAGE
    if route == "abstain":
        return MARA_PLANNER_ABSTAIN_MESSAGE
    return execution.answer


def _element_evidence_answer(bundle: Any) -> str:
    excerpts = []
    for item in bundle.items:
        if str(item.get("modality") or "") in {"", "text", "page_image", "graph"}:
            continue
        text = str(item.get("text") or item.get("caption") or "").strip()
        if text:
            excerpts.append(text.rstrip(".") + ".")
        if len(excerpts) >= 3:
            break
    return " ".join(excerpts)


class MaraAgentPipeline(FullQAPipeline):
    """MARA agentic wrapper around the existing DocQA retrieval stack."""

    build_evidence_metadata = staticmethod(build_mara_evidence_metadata)

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
            "question": query,
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

    def execute_controller_route(
        self,
        message: str,
        conv_id: str,
        history: list,
        understanding: dict[str, Any],
        planner_payload: dict[str, Any],
        kwargs: dict[str, Any],
    ) -> tuple[RouteExecutionResult, list[Document], Any]:
        generation_events: list[Document] = []
        generated_answer = ""

        def retrieve(_request: Any, _decision: Any) -> dict[str, Any]:
            return route_retrieval_metadata(
                self,
                _decision.route,
                message,
                history,
                understanding,
                text_retrieve=lambda: self.retrieve(message, history),
                metadata_builder=self.build_evidence_metadata,
            )

        def generate(_request: Any, _decision: Any, _bundle: Any) -> str:
            nonlocal generated_answer
            if _decision.route == "page_image_rag":
                vlm_generator = getattr(self, "vlm_generator", None)
                if vlm_generator is None:
                    _bundle.metadata["generation_backend"] = "evidence_only_without_vlm"
                    generated_answer = _visual_evidence_only_answer(_bundle)
                    return generated_answer
                _bundle.metadata["generation_backend"] = str(
                    getattr(vlm_generator, "name", "visual_generator")
                )
                generated_answer = _visual_generator_answer(
                    vlm_generator, _request, _bundle
                )
                return generated_answer
            if _decision.route == "graph_rag":
                _bundle.metadata["generation_backend"] = "local_graph_summary"
                generated_answer = graph_answer_from_evidence(_bundle.items)
                return generated_answer
            if _decision.route == "element_rag":
                _bundle.metadata["generation_backend"] = "local_element_evidence"
                generated_answer = _element_evidence_answer(_bundle)
                return generated_answer
            answer, events = _collect_text_rag_generation(
                self, message, conv_id, history, kwargs
            )
            generation_events.extend(events)
            generated_answer = answer
            return answer

        rewrite_generator = getattr(self, "rewrite_generator", None)
        rewrite = rewrite_generator if callable(rewrite_generator) else None

        execution = execute_controller_turn(
            _controller_execution_request(self, message),
            retrieve=retrieve,
            generate=generate,
            rewrite=rewrite,
            agent_trace=[planner_payload],
        )
        if generation_events and execution.answer != generated_answer:
            generation_events = []
        artifact = (
            self.build_artifact(understanding)
            if execution.guardrail_decision.action == "return"
            else None
        )
        return execution, generation_events, artifact

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
            _route_trace_payload(
                understanding,
                getattr(self, "agent_mode", "auto"),
                plan,
            ),
        )
        planner_payload = planner_trace_payload(
            understanding,
            planner=getattr(self, "planner", None),
            planner_model=getattr(self, "planner_model", None),
            question=message,
            allowed_routes=getattr(self, "allowed_routes", None),
        )
        yield _mara_event("agent_trace", planner_payload)
        effective_route = _effective_route(self, planner_payload)
        if effective_route in {
            "direct",
            "doc_text",
            "doc_page_image",
            "doc_element",
            "graph_global",
            "hybrid",
            "abstain",
        }:
            execution, generation_events, artifact = self.execute_controller_route(
                message,
                conv_id,
                history,
                understanding,
                planner_payload,
                kwargs,
            )
            return (
                yield from _route_execution_events(
                    execution,
                    generation_events,
                    artifact,
                )
            )

        return (yield from super().stream(message, conv_id, history, **kwargs))

    def build_artifact(self, understanding: dict[str, Any]) -> dict[str, Any] | None:
        return build_artifact_for_pipeline(self, understanding)
