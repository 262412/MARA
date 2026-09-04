import json

from click.testing import CliRunner
from slide_cli.docqa_cli import docqa


class _FileRecord:
    def __init__(self, file_id: str, name: str) -> None:
        self.file_id = file_id
        self.name = name

    def as_dict(self) -> dict:
        return {"file_id": self.file_id, "name": self.name}


class _Runtime:
    def __init__(self) -> None:
        self.records = [
            _FileRecord("file-1", "alpha.pptx"),
            _FileRecord("file-2", "beta.pptx"),
        ]
        self.delete_calls: list[list[str]] = []

    def delete_files(self, refs: list[str]) -> list[_FileRecord]:
        self.delete_calls.append(refs)
        matches = [
            record
            for ref in refs
            for record in self.records
            if ref in {record.file_id, record.name}
        ]
        deleted_ids = {record.file_id for record in matches}
        self.records = [
            record for record in self.records if record.file_id not in deleted_ids
        ]
        return matches


def test_docqa_delete_preserves_multi_file_json_behavior(monkeypatch) -> None:
    runtime = _Runtime()
    monkeypatch.setattr("slide_cli.docqa_cli.create_docqa_runtime", lambda: runtime)

    result = CliRunner().invoke(
        docqa,
        ["delete", "file-1", "beta.pptx", "--json"],
    )

    assert result.exit_code == 0, result.output
    payload, _offset = json.JSONDecoder().raw_decode(result.output.lstrip())
    assert payload == [
        {"file_id": "file-1", "name": "alpha.pptx"},
        {"file_id": "file-2", "name": "beta.pptx"},
    ]
    assert runtime.delete_calls == [["file-1", "beta.pptx"]]
    assert runtime.records == []
