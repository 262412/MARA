from __future__ import annotations

import unittest

from sidecar.generate_contracts import (
    GENERATED_CONTRACT_PATH,
    generate_typescript_contracts,
)


class GeneratedContractsTest(unittest.TestCase):
    def test_checked_in_types_match_the_fastapi_openapi_schema(self) -> None:
        self.assertEqual(
            GENERATED_CONTRACT_PATH.read_text(encoding="utf-8"),
            generate_typescript_contracts(),
        )


if __name__ == "__main__":
    unittest.main()
