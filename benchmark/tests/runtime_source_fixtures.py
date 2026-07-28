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
        "canonical_id": "evidence:doc:doc#source",
        "identity": {
            "source_id": "doc",
            "kind": "evidence",
            "local_id": "doc#source",
        },
        "document_id": "doc",
        "source_id": "doc",
        "runtime_source_id": "file-1",
        "source_aliases": ["file-1"],
        "source_name": "doc.txt",
        "modality": "text",
        "text": "Yelp",
        "source_backrefs": ["doc#source"],
    }
