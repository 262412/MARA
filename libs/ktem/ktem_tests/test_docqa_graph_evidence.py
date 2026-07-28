from ktem.docqa._runtime_models import DocQARequest
from ktem.docqa.evidence import build_evidence_bundle


def test_hybrid_bundle_includes_graph_evidence_when_available():
    request = DocQARequest(
        prompt="Compare text with graph themes.",
        route_policy="hybrid",
    )
    metadata = {
        "evidence": [
            {
                "evidence_id": "text-1",
                "file_id": "file-1",
                "file_name": "report.pdf",
                "page_label": "2",
                "text": "Revenue text evidence.",
            }
        ],
        "graph_evidence": [
            {
                "id": "community-1",
                "label": "Revenue System",
                "summary": "Revenue connects report sections.",
                "source_backrefs": ["file-1#page:2"],
            }
        ],
    }

    bundle = build_evidence_bundle("hybrid", request, metadata)

    assert [item["modality"] for item in bundle.items] == ["text", "graph"]
    assert bundle.items[1]["evidence_id"] == "graph:community-1"
    assert bundle.metadata["modality_counts"] == {"graph": 1, "text": 1}


def test_graph_route_builds_graph_level_evidence_with_source_backrefs():
    request = DocQARequest(
        prompt="Compare themes across sources.",
        route_policy="graph",
        graph_context={
            "graph": {
                "nodes": [
                    {
                        "id": "theme-1",
                        "label": "Revenue",
                        "summary": "Revenue links report A and report B.",
                        "source_ids": ["file-a", "file-b"],
                    }
                ]
            }
        },
    )

    bundle = build_evidence_bundle("graph_global", request, {})

    assert {item["source_id"] for item in bundle.items} == {"file-a", "file-b"}
    assert [item["source_backrefs"] for item in bundle.items] == [
        ["file-a"],
        ["file-b"],
    ]
    assert all(item["evidence_id"] == "graph:theme-1" for item in bundle.items)
    assert all(item["source_name"] == "Revenue" for item in bundle.items)
    assert all(item["modality"] == "graph" for item in bundle.items)
    assert all(
        item["text"] == "Revenue links report A and report B." for item in bundle.items
    )
    assert all(item["evidence_level"] == "graph" for item in bundle.items)
    assert all(item["metadata"] == {"route": "graph_global"} for item in bundle.items)
    assert all(item["normalized_text_hash"] for item in bundle.items)
    assert bundle.metadata["schema_version"] == "evidence_bundle.v2"


def test_graph_evidence_uses_page_level_backrefs_when_available():
    bundle = build_evidence_bundle(
        "graph_global",
        DocQARequest(prompt="Compare themes."),
        {
            "graph_evidence": [
                {
                    "id": "theme-1",
                    "label": "Revenue",
                    "summary": "Revenue links report A and report B.",
                    "source_ids": ["file-a", "file-b"],
                    "support_pages": {"file-a": ["2"], "file-b": ["5", "6"]},
                }
            ]
        },
    )

    assert [item["source_backrefs"] for item in bundle.items] == [
        ["file-a#page:2"],
        ["file-b#page:5"],
        ["file-b#page:6"],
    ]
