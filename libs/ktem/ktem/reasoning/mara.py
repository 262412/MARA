from __future__ import annotations

from contextlib import contextmanager
from types import SimpleNamespace
from typing import Any, Generator

from ktem.docqa.claim_filtering import clean_answer_text
from ktem.docqa.execution import RouteExecutionResult, execute_controller_turn
from ktem.docqa.graph_index import graph_answer_from_evidence

from kotaemon.base import Document, RetrievedDocument

from .mara_artifacts import build_artifact_for_pipeline
from .mara_controller import planner_trace_payload
from .mara_element_answer import element_evidence_answer
from .mara_evidence import build_mara_evidence_metadata
from .mara_query_planning import plan_steps as build_mara_plan_steps
from .mara_query_planning import understand_query as understand_mara_query
from .mara_query_planning import with_selected_source_context
from .mara_retrieval_query import messages_share_retrieval_cache_key, retrieval_query
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
ANSWER_FORMAT_REQUIREMENTS = (
    "\n\nAnswer formatting requirements:\n"
    "- Start with the direct final answer in the first sentence, then add "
    "supporting calculation or evidence only if needed.\n"
    "- For financial calculation questions, state the final numeric result or "
    "yes/no conclusion first, include the formula inputs, and avoid extra "
    "tables unless the question asks for a table.\n"
    "- Return the final answer as Markdown, not raw HTML.\n"
    "- Put a blank line between paragraphs, headings, lists, formulas, tables, "
    "and code blocks.\n"
    "- Render mathematical formulas as LaTeX: use $...$ for inline formulas "
    "and $$...$$ on separate lines for display formulas. Do not use backticks "
    "for mathematical variables or equations.\n"
    "- Render requested summaries, comparisons, and tabular answers as Markdown "
    "tables with a header row and separator row. Put a blank line before and "
    "after each table, and never write pipe-delimited table rows inline inside "
    "a paragraph.\n"
    "- Render code as fenced Markdown code blocks with triple backticks, such "
    "as ```python, when a language tag is clear.\n"
)

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
    controller_mode = str(getattr(pipeline, "controller_mode", "") or "").strip()
    return SimpleNamespace(
        prompt=message,
        controller_mode=controller_mode or "llm",
        route_policy=getattr(pipeline, "route_policy", None) or "auto",
        allowed_routes=list(getattr(pipeline, "allowed_routes", None) or []),
        verification_mode=getattr(pipeline, "verification_mode", None) or "light",
        verification_domain=getattr(pipeline, "verification_domain", None) or "",
        active_file_id=getattr(pipeline, "active_file_id", "") or "",
        active_file_name=getattr(pipeline, "active_file_name", "") or "",
        page_number=getattr(pipeline, "page_number", None),
        selected_text=getattr(pipeline, "selected_text", "") or "",
        selected_file_ids=list(getattr(pipeline, "selected_file_ids", None) or []),
        graph_context=getattr(pipeline, "graph_context", None) or {},
    )


def _with_available_modalities(
    understanding: dict[str, Any],
    pipeline: Any,
) -> dict[str, Any]:
    available_modalities = [
        str(modality)
        for modality in understanding.get("available_modalities", [])
        if modality
    ]
    if (
        _page_image_route_available(pipeline)
        and "page_image" not in available_modalities
    ):
        available_modalities.append("page_image")
    if not available_modalities:
        return understanding
    updated = dict(understanding)
    updated["available_modalities"] = available_modalities
    return updated


def _page_image_route_available(pipeline: Any) -> bool:
    allowed_routes = [
        str(route).strip()
        for route in getattr(pipeline, "allowed_routes", None) or []
        if str(route).strip()
    ]
    if allowed_routes and not any(
        route in {"doc_page_image", "hybrid"} for route in allowed_routes
    ):
        return False
    return bool(
        getattr(pipeline, "visual_retriever_backend", None)
        or getattr(pipeline, "visual_retriever", None)
        or getattr(pipeline, "page_image_index_records", None)
    )


@contextmanager
def _text_only_answering_pipeline(pipeline: Any) -> Generator[None, None, None]:
    answering_pipeline = getattr(pipeline, "answering_pipeline", None)
    target = _answering_pipeline_multimodal_target(answering_pipeline)
    if target is None:
        yield
        return

    original_use_multimodal = target.use_multimodal
    target.use_multimodal = False
    try:
        yield
    finally:
        target.use_multimodal = original_use_multimodal


def _answering_pipeline_multimodal_target(answering_pipeline: Any) -> Any | None:
    original_obj = getattr(answering_pipeline, "ff_original_obj", None)
    if original_obj is not None and hasattr(original_obj, "use_multimodal"):
        return original_obj
    if hasattr(answering_pipeline, "use_multimodal"):
        return answering_pipeline
    return None


def _collect_text_rag_generation(
    pipeline: Any,
    message: str,
    conv_id: str,
    history: list,
    kwargs: dict[str, Any],
) -> tuple[str, list[Document]]:
    events: list[Document] = []
    answer = ""
    generation_message = _message_with_answer_format_requirements(message)
    generation_kwargs = dict(kwargs)
    generation_kwargs["enable_claim_verification"] = False
    with _text_only_answering_pipeline(pipeline):
        stream = super(MaraAgentPipeline, pipeline).stream(
            generation_message, conv_id, history, **generation_kwargs
        )
        while True:
            try:
                event = next(stream)
            except StopIteration as stop:
                returned = stop.value
                break
            events.append(event)
            if isinstance(event, Document) and event.channel == "chat":
                if event.content is None:
                    answer = ""
                else:
                    answer += str(event.content)
    if not answer and isinstance(returned, Document) and returned.channel == "chat":
        answer = "" if returned.content is None else str(returned.content)
    return clean_answer_text(answer), events


def _message_with_answer_format_requirements(message: str) -> str:
    prompt = str(message or "").rstrip()
    if "Benchmark prompt contract:" in prompt:
        return prompt
    if "Return the final answer as Markdown" in prompt:
        return prompt
    return prompt + ANSWER_FORMAT_REQUIREMENTS


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
    yield _mara_event("execution", execution.as_dict())
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


def _bundle_has_page_image_evidence(bundle: Any) -> bool:
    return any(
        isinstance(item, dict) and str(item.get("modality") or "") == "page_image"
        for item in getattr(bundle, "items", []) or []
    )


def _route_visual_answer(
    pipeline: Any,
    request: Any,
    bundle: Any,
    *,
    evidence_only_fallback: bool,
) -> str | None:
    vlm_generator = getattr(pipeline, "vlm_generator", None)
    if vlm_generator is None:
        if not evidence_only_fallback:
            return None
        bundle.metadata["generation_backend"] = "evidence_only_without_vlm"
        return _visual_evidence_only_answer(bundle)
    bundle.metadata["generation_backend"] = str(
        getattr(vlm_generator, "name", "visual_generator")
    )
    return _visual_generator_answer(vlm_generator, request, bundle)


def _visible_execution_answer(execution: RouteExecutionResult) -> str:
    route = execution.controller_decision.route
    if route == "direct_answer":
        return MARA_DIRECT_MESSAGE
    if route == "abstain":
        return MARA_PLANNER_ABSTAIN_MESSAGE
    return execution.answer


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
        return understand_mara_query(
            query,
            task_type=task_type,
            qa_scope=qa_scope,
            active_file_id=active_file_id,
            page_number=page_number,
        )

    @classmethod
    def plan_steps(
        cls, understanding: dict[str, Any], *, agent_mode: str | None = None
    ) -> list[dict[str, str]]:
        return build_mara_plan_steps(understanding, agent_mode=agent_mode)

    def retrieve(
        self, message: str, history: list
    ) -> tuple[list[RetrievedDocument], list[Document]]:
        cached = getattr(self, "_mara_cached_retrieval", None)
        if (
            cached
            and messages_share_retrieval_cache_key(cached[0], message)
            and cached[1] == list(history)
        ):
            delattr(self, "_mara_cached_retrieval")
            docs, info = cached[2], cached[3]
            self._mara_last_docs = list(docs)
            return docs, info

        docs, info = super().retrieve(
            retrieval_query(message, domain=_retrieval_domain(self)),
            history,
        )
        attempts = [{"attempt": 1, "evidence_count": len(docs), "retry_reason": ""}]
        if _should_retry_retrieval(getattr(self, "agent_mode", None), docs):
            docs, info = super().retrieve(
                retrieval_query(message, domain=_retrieval_domain(self)),
                history,
            )
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
                visual_answer = _route_visual_answer(
                    self,
                    _request,
                    _bundle,
                    evidence_only_fallback=True,
                )
                assert visual_answer is not None
                generated_answer = visual_answer
                return generated_answer
            if _decision.route == "hybrid_rag" and _bundle_has_page_image_evidence(
                _bundle
            ):
                visual_answer = _route_visual_answer(
                    self,
                    _request,
                    _bundle,
                    evidence_only_fallback=False,
                )
                if visual_answer is not None:
                    generated_answer = visual_answer
                    return generated_answer
            if _decision.route == "graph_rag":
                _bundle.metadata["generation_backend"] = "local_graph_summary"
                generated_answer = graph_answer_from_evidence(_bundle.items)
                return generated_answer
            if _decision.route == "element_rag":
                _bundle.metadata["generation_backend"] = "local_element_evidence"
                generated_answer = element_evidence_answer(_bundle, message)
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
        understanding = _with_available_modalities(understanding, self)
        understanding = with_selected_source_context(understanding, self)
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


def _retrieval_domain(pipeline: Any) -> str:
    return str(
        getattr(pipeline, "retrieval_domain", None)
        or getattr(pipeline, "verification_domain", None)
        or ""
    ).strip()
