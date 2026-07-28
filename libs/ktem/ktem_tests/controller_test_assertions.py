def assert_graph_bundle_contract(payload):
    bundle = payload["evidence_bundle"]
    assert bundle["route"] == "graph_global"
    assert bundle["metadata"]["modality_counts"] == {"graph": 1}
    assert bundle["metadata"]["page_coverage"] == ["1"]
    assert bundle["items"][0]["evidence_id"] == "doc-1"
    assert bundle["items"][0]["modality"] == "graph"
    assert bundle["items"][0]["evidence_level"] == "graph"
    assert payload["backend_metadata"] == {"graph_backend": "local_graph_index"}
