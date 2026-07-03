class ExternalEvaluatorEngine:
    def __init__(self, engine_name, config):
        self.engine_name = engine_name
        self.config = config

    @staticmethod
    def run_example(_bundle, example):
        return {
            "example_id": example.example_id,
            "document_id": example.document_id,
            "question": example.question,
            "gold_answers": example.answers,
            "gold_pages": example.evidence_pages,
            "gold_sources": example.evidence_sources,
            "predicted_answer": "Revenue rose.",
            "predicted_pages": [1],
            "predicted_sources": ["doc#page:1"],
            "predicted_element_ids": [],
            "retrieved_hits": [],
        }

    @staticmethod
    def document_reports():
        return []
