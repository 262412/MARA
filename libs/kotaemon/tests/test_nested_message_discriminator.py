from copy import deepcopy

import pytest

from kotaemon.base import LLMInterface

from .test_message_persistence_contracts import PAYLOADS


@pytest.mark.parametrize("marker", ["HumanMessage", "NotADocument", 7, None])
def test_invalid_nested_discriminator_is_not_silently_discarded(marker):
    payload = deepcopy(PAYLOADS["LLMInterface"])
    payload["messages"][0]["class_name"] = marker
    with pytest.raises(ValueError, match="class_name"):
        LLMInterface.from_dict(payload)


def test_valid_nested_discriminator_preserves_extra_fields_and_metadata():
    payload = deepcopy(PAYLOADS["LLMInterface"])
    nested = payload["messages"][0]
    nested["saved_extension"] = {"class_name": "do not remove this"}
    nested["metadata"]["class_name"] = "display metadata"
    restored = LLMInterface.from_dict(payload).to_dict()
    assert restored["messages"][0] == nested
