from kotaemon.indices.elements import DocumentElement
from kotaemon.indices.multimodal import (
    MultimodalPluginPolicy,
    NoOpMathOCRPlugin,
    NoOpOCRPlugin,
    NoOpVLMCaptionPlugin,
    recommend_multimodal_plugins,
)
from kotaemon.indices.retrieval_quality import QueryModality, QueryRoute


def _route(modality: QueryModality) -> QueryRoute:
    return QueryRoute(
        query="query",
        modality=modality,
        modality_weights={modality: 1.0},
        retrieval_hints={"boost_element_types": [modality]},
    )


def test_noop_plugins_return_empty_results_without_external_effects():
    assert NoOpOCRPlugin().extract_text(image=b"image") == ""
    assert NoOpVLMCaptionPlugin().caption_image(image=b"image") == ""
    assert NoOpMathOCRPlugin().recognize_formula(image=b"formula") == ""


def test_policy_defaults_to_disabled_even_for_matching_route_and_docs():
    docs = [DocumentElement(element_id="fig-1", element_type="figure")]

    decision = recommend_multimodal_plugins(_route("figure"), docs)

    assert not decision.run_ocr
    assert not decision.run_vlm
    assert not decision.run_math_ocr


def test_policy_recommends_vlm_and_ocr_on_demand_for_figure_docs_when_enabled():
    docs = [DocumentElement(element_id="fig-1", element_type="figure")]
    policy = MultimodalPluginPolicy(enable_ocr=True, enable_vlm=True)

    decision = recommend_multimodal_plugins(_route("figure"), docs, policy)

    assert decision.run_ocr
    assert decision.run_vlm
    assert not decision.run_math_ocr
    assert decision.candidate_element_ids == ("fig-1",)


def test_policy_recommends_math_ocr_only_for_missing_normalized_formula():
    docs = [
        DocumentElement(
            element_id="formula-1",
            element_type="formula",
            formula_image={"page": 1, "bbox": [0, 0, 10, 10]},
        ),
        DocumentElement(
            element_id="formula-2",
            element_type="formula",
            formula_image={"page": 1, "bbox": [10, 0, 20, 10]},
            normalized_formula="E = mc^2",
        ),
    ]
    policy = MultimodalPluginPolicy(enable_math_ocr=True)

    decision = recommend_multimodal_plugins(_route("formula"), docs, policy)

    assert decision.run_math_ocr
    assert not decision.run_ocr
    assert not decision.run_vlm
    assert decision.candidate_element_ids == ("formula-1",)


def test_policy_accepts_dict_docs_and_mixed_route_for_formula_images():
    docs = [
        {
            "element_id": "formula-image-1",
            "element_type": "formula_image",
            "formula_image": "image-bytes",
            "normalized_formula": None,
        }
    ]
    policy = MultimodalPluginPolicy(enable_math_ocr=True)

    decision = recommend_multimodal_plugins(_route("mixed"), docs, policy)

    assert decision.run_math_ocr
    assert decision.candidate_element_ids == ("formula-image-1",)


def test_policy_does_not_trigger_without_images_or_formulas():
    docs = [DocumentElement(element_id="text-1", element_type="text")]
    policy = MultimodalPluginPolicy(
        enable_ocr=True,
        enable_vlm=True,
        enable_math_ocr=True,
    )

    figure_decision = recommend_multimodal_plugins(_route("figure"), docs, policy)
    formula_decision = recommend_multimodal_plugins(_route("formula"), docs, policy)

    assert not figure_decision.run_ocr
    assert not figure_decision.run_vlm
    assert not figure_decision.run_math_ocr
    assert not formula_decision.run_math_ocr
