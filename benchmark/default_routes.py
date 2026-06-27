from __future__ import annotations

from typing import Any

CONTROLLER_AUTO_ALLOWED_ROUTES = (
    "doc_text hybrid doc_page_image doc_element graph_global".split()
)


def _phase2_route(route: dict[str, Any]) -> dict[str, Any]:
    return {
        **route,
        "benchmark_prompt_policy": "gold_answer_v1",
        "benchmark_no_think": True,
    }


DEFAULT_MARA_ROUTES: list[dict[str, Any]] = [
    _phase2_route(
        {
            "route_id": "direct_answer",
            "route_name": "Direct answer",
            "engine": "benchmark_direct_answer",
            "scope": "multi_document",
            "reasoning_type": "mara",
            "controller_mode": "llm",
            "route_policy": "direct",
            "allowed_routes": ["direct"],
            "verification_mode": "light",
            "planner_backend": "heuristic_local",
            "generator_backend": "local_direct",
            "benchmark_role": "diagnostic",
            "docqa_citation_mode": "inline",
        }
    ),
    _phase2_route(
        {
            "route_id": "text_rag",
            "route_name": "Text RAG",
            "engine": "docqa_runtime",
            "scope": "multi_document",
            "reasoning_type": "mara",
            "controller_mode": "llm",
            "route_policy": "doc",
            "allowed_routes": ["doc_text"],
            "verification_mode": "light",
            "text_retriever_backend": "docqa_text",
            "planner_backend": "heuristic_local",
            "generator_backend": "local_docqa_generator",
            "benchmark_role": "qa_quality",
            "docqa_citation_mode": "inline",
        }
    ),
    _phase2_route(
        {
            "route_id": "page_image_rag_smoke",
            "route_name": "Page-image RAG smoke",
            "engine": "docqa_runtime",
            "scope": "multi_document",
            "reasoning_type": "mara",
            "controller_mode": "llm",
            "route_policy": "visual",
            "allowed_routes": ["doc_page_image"],
            "verification_mode": "light",
            "visual_retriever_backend": "local_late_interaction",
            "visual_backend_type": "deterministic_smoke",
            "planner_backend": "heuristic_local",
            "generator_backend": "evidence_only_without_vlm",
            "implementation_stage": "deterministic_page_image_smoke",
            "benchmark_role": "diagnostic",
            "docqa_citation_mode": "inline",
        }
    ),
    _phase2_route(
        {
            "route_id": "page_image_rag_vlm",
            "route_name": "Page-image RAG VLM",
            "engine": "docqa_runtime",
            "scope": "multi_document",
            "reasoning_type": "mara",
            "controller_mode": "llm",
            "route_policy": "visual",
            "allowed_routes": ["doc_page_image"],
            "verification_mode": "light",
            "visual_retriever_backend": "local_late_interaction",
            "visual_backend_type": "deterministic_smoke",
            "planner_backend": "heuristic_local",
            "generator_backend": "evidence_only_without_vlm",
            "backend_status": "not_configured",
            "requires_backend_config": True,
            "missing_backends": ["colpali", "visual_generator"],
            "implementation_stage": "requires_configured_visual_backends",
            "benchmark_role": "diagnostic",
            "docqa_citation_mode": "inline",
        }
    ),
    _phase2_route(
        {
            "route_id": "element_rag",
            "route_name": "Element RAG",
            "engine": "docqa_runtime",
            "scope": "multi_document",
            "reasoning_type": "mara",
            "controller_mode": "llm",
            "route_policy": "element",
            "allowed_routes": ["doc_element"],
            "verification_mode": "light",
            "text_retriever_backend": "docqa_element_metadata",
            "planner_backend": "heuristic_local",
            "generator_backend": "local_docqa_generator",
            "implementation_stage": "prototype_element_metadata_index",
            "benchmark_role": "prototype",
            "docqa_citation_mode": "inline",
        }
    ),
    _phase2_route(
        {
            "route_id": "graph_rag_local",
            "route_name": "GraphRAG local",
            "engine": "docqa_runtime",
            "scope": "multi_document",
            "reasoning_type": "mara",
            "controller_mode": "llm",
            "route_policy": "graph",
            "allowed_routes": ["graph_global"],
            "verification_mode": "light",
            "graph_backend": "local_graph_index",
            "graph_mode": "local",
            "planner_backend": "heuristic_local",
            "generator_backend": "local_graph_summary",
            "implementation_stage": "prototype_lightweight_graph_selector",
            "benchmark_role": "prototype",
            "docqa_citation_mode": "inline",
        }
    ),
    _phase2_route(
        {
            "route_id": "graph_rag_global",
            "route_name": "GraphRAG global",
            "engine": "docqa_runtime",
            "scope": "multi_document",
            "reasoning_type": "mara",
            "task_type": "summary",
            "controller_mode": "llm",
            "route_policy": "graph",
            "allowed_routes": ["graph_global"],
            "verification_mode": "light",
            "graph_backend": "local_graph_index",
            "graph_mode": "global",
            "planner_backend": "heuristic_local",
            "generator_backend": "local_graph_summary",
            "implementation_stage": "prototype_lightweight_graph_selector",
            "benchmark_role": "prototype",
            "docqa_citation_mode": "inline",
        }
    ),
    _phase2_route(
        {
            "route_id": "hybrid_rag",
            "route_name": "Hybrid RAG",
            "engine": "docqa_runtime",
            "scope": "multi_document",
            "reasoning_type": "mara",
            "controller_mode": "llm",
            "route_policy": "hybrid",
            "allowed_routes": ["hybrid"],
            "verification_mode": "light",
            "text_retriever_backend": "docqa_text",
            "visual_retriever_backend": "local_late_interaction",
            "visual_backend_type": "deterministic_smoke",
            "planner_backend": "heuristic_local",
            "generator_backend": "local_docqa_generator",
            "benchmark_role": "qa_quality",
            "docqa_citation_mode": "inline",
        }
    ),
    _phase2_route(
        {
            "route_id": "controller_auto",
            "route_name": "Controller auto",
            "engine": "docqa_runtime",
            "scope": "multi_document",
            "reasoning_type": "mara",
            "controller_mode": "llm",
            "route_policy": "auto",
            "allowed_routes": list(CONTROLLER_AUTO_ALLOWED_ROUTES),
            "verification_mode": "light",
            "text_retriever_backend": "docqa_text",
            "visual_retriever_backend": "local_late_interaction",
            "visual_backend_type": "deterministic_smoke",
            "graph_backend": "local_global_graph",
            "planner_backend": "heuristic_local",
            "generator_backend": "local_docqa_generator",
            "route_timeout_seconds": 90.0,
            "benchmark_role": "qa_quality",
            "docqa_citation_mode": "inline",
        }
    ),
    _phase2_route(
        {
            "route_id": "crag_guarded",
            "route_name": "CRAG guarded",
            "engine": "docqa_runtime",
            "scope": "multi_document",
            "reasoning_type": "mara",
            "agent_mode": "thorough",
            "controller_mode": "llm",
            "route_policy": "auto",
            "allowed_routes": list(CONTROLLER_AUTO_ALLOWED_ROUTES),
            "verification_mode": "strict",
            "text_retriever_backend": "docqa_text",
            "visual_retriever_backend": "local_late_interaction",
            "visual_backend_type": "deterministic_smoke",
            "graph_backend": "local_global_graph",
            "planner_backend": "heuristic_local",
            "generator_backend": "local_docqa_generator",
            "route_timeout_seconds": 90.0,
            "benchmark_role": "qa_quality",
            "docqa_citation_mode": "inline",
        }
    ),
]
