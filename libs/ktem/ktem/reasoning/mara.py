from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Generator

from ktem.docqa.claim_filtering import clean_answer_text
from ktem.docqa.execution import RouteExecutionResult, execute_controller_turn
from ktem.docqa.graph_index import graph_answer_from_evidence

from kotaemon.base import Document, RetrievedDocument

from .mara_answer_type_contract import (
    answer_type_consistency,
    message_with_answer_type_contract,
    request_answer_type,
)
from .mara_artifacts import build_artifact_for_pipeline
from .mara_controller import planner_trace_payload
from .mara_controller_request import (
    controller_execution_request as _controller_execution_request,
)
from .mara_controller_request import (
    controller_routing_message as _controller_routing_message,
)
from .mara_element_answer import element_evidence_answer
from .mara_evidence import build_mara_evidence_metadata
from .mara_finance_answering import (
    ensure_finance_numeric_trace,
    route_finance_numeric_answer,
)
from .mara_generation_context import cache_generation_context
from .mara_query_planning import plan_steps as build_mara_plan_steps
from .mara_query_planning import understand_query as understand_mara_query
from .mara_query_planning import with_selected_source_context
from .mara_ragtruth_answering import route_ragtruth_answer
from .mara_retrieval_query import messages_share_retrieval_cache_key, retrieval_query
from .mara_route_probe import (
    controller_latency_budget,
    controller_route_probe,
    dataset_family,
    page_image_route_available,
)
from .mara_route_retrieval import controller_text_retrieve, route_retrieval_metadata
from .mara_visual_answering import route_visual_answer as _route_visual_answer
from .mara_visual_gate import hybrid_should_use_visual_generator
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
        page_image_route_available(pipeline)
        and "page_image" not in available_modalities
    ):
        available_modalities.append("page_image")
    if not available_modalities:
        return understanding
    updated = dict(understanding)
    updated["available_modalities"] = available_modalities
    return updated


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


def _visible_execution_answer(execution: RouteExecutionResult) -> str:
    route = execution.controller_decision.route
    if route == "direct_answer":
        return MARA_DIRECT_MESSAGE
    if route == "abstain":
        return MARA_PLANNER_ABSTAIN_MESSAGE
    return execution.answer


def _generate_controller_route_answer(
    pipeline: Any,
    request: Any,
    decision: Any,
    bundle: Any,
    *,
    message: str,
    conv_id: str,
    history: list,
    kwargs: dict[str, Any],
) -> tuple[str, list[Document]]:
    ragtruth_answer = route_ragtruth_answer(pipeline, request, bundle)
    if ragtruth_answer is not None:
        return ragtruth_answer, []
    if decision.route == "page_image_rag":
        visual_answer = _route_visual_answer(
            pipeline,
            request,
            bundle,
            evidence_only_fallback=True,
        )
        assert visual_answer is not None
        return visual_answer, []
    finance_answer = route_finance_numeric_answer(request, decision, bundle)
    if finance_answer is not None:
        return finance_answer, []
    if decision.route == "hybrid_rag" and hybrid_should_use_visual_generator(
        request, decision, bundle
    ):
        visual_answer = _route_visual_answer(
            pipeline,
            request,
            bundle,
            evidence_only_fallback=False,
        )
        if visual_answer is not None:
            return visual_answer, []
    if decision.route == "graph_rag":
        bundle.metadata["generation_backend"] = "local_graph_summary"
        return graph_answer_from_evidence(bundle.items), []
    if decision.route == "element_rag":
        bundle.metadata["generation_backend"] = "local_element_evidence"
        return element_evidence_answer(bundle, message), []
    cache_generation_context(pipeline, message, history, bundle)
    generation_message = message_with_answer_type_contract(message, request)
    answer, events = _collect_text_rag_generation(
        pipeline,
        generation_message,
        conv_id,
        history,
        kwargs,
    )
    answer_type = request_answer_type(request)
    consistent, reason = answer_type_consistency(answer_type, answer)
    bundle.metadata["generation_answer_type_contract"] = {
        "answer_type": answer_type,
        "consistent": consistent,
        "reason": reason,
        "status": "passed" if consistent else "failed",
    }
    return answer, events


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
        pipeline.retrieval_candidate_kwargs = {
            "top_k": 30,
            "do_extend": True,
            "dense_top_k": 50,
            "sparse_top_k": 50,
            "rerank_top_k": 80,
            "rrf_k": 60,
        }
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
        retry_disabled = bool(
            getattr(self, "_mara_disable_nested_retrieval_retry", False)
        )
        if not retry_disabled and _should_retry_retrieval(
            getattr(self, "agent_mode", None), docs
        ):
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
        *,
        routing_message: str | None = None,
    ) -> tuple[RouteExecutionResult, list[Document], Any]:
        generation_events: list[Document] = []
        generated_answer = ""
        retrieval_message = str(routing_message or message)

        def retrieve(_request: Any, _decision: Any) -> dict[str, Any]:
            query = str(getattr(_request, "retrieval_query", "") or retrieval_message)
            return route_retrieval_metadata(
                self,
                _decision.route,
                query,
                history,
                understanding,
                text_retrieve=lambda: controller_text_retrieve(
                    self,
                    query,
                    history,
                ),
                metadata_builder=self.build_evidence_metadata,
            )

        def generate(_request: Any, _decision: Any, _bundle: Any) -> str:
            nonlocal generated_answer
            answer, events = _generate_controller_route_answer(
                self,
                _request,
                _decision,
                _bundle,
                message=message,
                conv_id=conv_id,
                history=history,
                kwargs=kwargs,
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
        ensure_finance_numeric_trace(
            _controller_execution_request(self, message),
            execution.evidence_bundle,
        )
        if generation_events and execution.answer != generated_answer:
            generation_events = []
        artifact = None
        if execution.guardrail_decision.action == "return":
            artifact = self.build_artifact(understanding)
        return execution, generation_events, artifact

    def stream(  # type: ignore
        self, message: str, conv_id: str, history: list, **kwargs  # type: ignore
    ) -> Generator[Document, None, Document]:
        routing_message = _controller_routing_message(self, message)
        understanding = self.understand_query(
            routing_message,
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
        route_probe = controller_route_probe(
            self, routing_message, history, understanding
        )
        latency_budget = controller_latency_budget(self)
        planner_payload = planner_trace_payload(
            understanding,
            planner=getattr(self, "planner", None),
            planner_model=getattr(self, "planner_model", None),
            question=routing_message,
            allowed_routes=getattr(self, "allowed_routes", None),
            route_probe=route_probe,
            dataset_family=dataset_family(self),
            latency_budget=latency_budget,
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
                routing_message=routing_message,
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
        or getattr(pipeline, "dataset_family", None)
        or ""
    ).strip()
