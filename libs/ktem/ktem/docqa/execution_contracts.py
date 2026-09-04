from __future__ import annotations

DIRECT_ANSWER_MESSAGE = (
    "MARA can answer general questions, but document-specific answers require "
    "retrieved evidence."
)
ABSTAIN_MESSAGE = (
    "MARA could not retrieve enough evidence to answer reliably. Select a "
    "relevant source or page, or ask with more source-specific context."
)
RAGTRUTH_EMPTY_ANSWER = '{"hallucination list": []}'
ENGINE_TERMINAL_STATE_CONTRACT = "engine_terminal_state.v1"

CANONICAL_ROUTES = {
    "direct": "direct_answer",
    "doc_text": "text_rag",
    "doc_page_image": "page_image_rag",
    "doc_element": "element_rag",
    "graph_global": "graph_rag",
    "hybrid": "hybrid_rag",
    "abstain": "abstain",
}
