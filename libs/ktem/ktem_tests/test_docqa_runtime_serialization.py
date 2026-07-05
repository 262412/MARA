import json

from ktem.docqa._runtime_utils import _serialize_value


def test_runtime_serializer_normalizes_pypdf_indirect_objects():
    from pypdf.generic import DictionaryObject, IndirectObject, NameObject, NumberObject

    value = {
        "root": DictionaryObject({NameObject("/Count"): NumberObject(1)}),
        "ref": IndirectObject(4, 0, None),
    }

    serialized = _serialize_value(value)

    assert serialized == {"root": {"/Count": 1}, "ref": "IndirectObject(4, 0)"}
    json.dumps(serialized, sort_keys=True)
