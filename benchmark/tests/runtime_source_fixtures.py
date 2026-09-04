def runtime_hit():
    return {
        "evidence_id": "hit-1",
        "source_id": "file-1",
        "source_name": "doc.txt",
        "page_label": "2",
        "modality": "text",
        "element_id": "chunk-1",
        "score": 0.91,
        "text": "Revenue increased.",
        "source_backrefs": ["file-1#page:2"],
    }


def canonical_short_source_hit():
    return {
        "evidence_id": "doc#source",
        "canonical_id": "evidence:file-1:doc#source",
        "runtime_identity": "evidence:file-1:doc#source",
        "evaluation_identity": "evidence:doc:doc#source",
        "identity": {
            "source_id": "file-1",
            "kind": "evidence",
            "local_id": "doc#source",
        },
        "document_id": "doc",
        "source_id": "file-1",
        "runtime_source_id": "file-1",
        "evaluation_source_id": "doc",
        "source_aliases": ["file-1", "doc"],
        "source_name": "doc.txt",
        "modality": "text",
        "text": "Yelp",
        "source_backrefs": ["doc#source"],
        "runtime_source_backrefs": ["file-1#source"],
        "evaluation_source_backrefs": ["doc#source"],
    }
