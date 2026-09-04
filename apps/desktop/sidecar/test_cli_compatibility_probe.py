from __future__ import annotations

import unittest

from .cli_compatibility_probe import validate_cli_records


class CliCompatibilityProbeTest(unittest.TestCase):
    def test_validates_names_without_retaining_cli_paths(self) -> None:
        names = validate_cli_records(
            [
                {
                    "file_id": "file-1",
                    "name": "gate3-cli-compat.txt",
                    "path": "/private/runner/path.txt",
                }
            ],
            expected_name="gate3-cli-compat.txt",
        )

        self.assertEqual(names, ["gate3-cli-compat.txt"])

    def test_rejects_missing_and_remaining_records(self) -> None:
        with self.assertRaisesRegex(ValueError, "missing"):
            validate_cli_records([], expected_name="missing.txt")
        with self.assertRaisesRegex(ValueError, "still reports"):
            validate_cli_records([{"name": "remaining.txt"}], expect_empty=True)

    def test_rejects_a_non_record_payload(self) -> None:
        with self.assertRaisesRegex(ValueError, "record list"):
            validate_cli_records({"files": []})


if __name__ == "__main__":
    unittest.main()
