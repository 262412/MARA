from __future__ import annotations

import unittest
from typing import Any

from sidecar.generate_contracts import (
    GENERATED_CONTRACT_PATH,
    _schema_type,
    generate_typescript_contracts,
)


class GeneratedContractsTest(unittest.TestCase):
    def test_boolean_additional_properties_keeps_dictionary_value_types(self) -> None:
        cases: list[tuple[dict[str, Any], str]] = [
            (
                {"type": "object", "additionalProperties": True},
                "Record<string, unknown>",
            ),
            (
                {"type": "object", "additionalProperties": False},
                "Record<string, never>",
            ),
            (
                {"type": "object", "additionalProperties": {"type": "string"}},
                "Record<string, string>",
            ),
        ]
        for schema, expected in cases:
            with self.subTest(schema=schema):
                self.assertEqual(_schema_type(schema), expected)

    def test_checked_in_types_match_the_fastapi_openapi_schema(self) -> None:
        self.assertEqual(
            GENERATED_CONTRACT_PATH.read_text(encoding="utf-8"),
            generate_typescript_contracts(),
        )


if __name__ == "__main__":
    unittest.main()
