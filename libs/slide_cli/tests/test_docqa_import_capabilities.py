from types import SimpleNamespace

from slide_cli.docqa_import_capabilities import (
    normalize_supported_extensions,
    select_file_index_config,
)


def test_persisted_file_index_config_wins_over_the_default_definition():
    settings = SimpleNamespace(
        KH_INDICES=[
            {
                "index_type": "ktem.index.file.FileIndex",
                "config": {"supported_file_types": ".txt, .md"},
            }
        ]
    )
    rows = [
        SimpleNamespace(
            index_type="ktem.index.file.FileIndex",
            config={"supported_file_types": ".pdf, .docx"},
        )
    ]

    assert select_file_index_config(settings, rows) == {
        "supported_file_types": ".pdf, .docx"
    }
    assert select_file_index_config(settings, []) == {
        "supported_file_types": ".txt, .md"
    }


def test_supported_extensions_are_stable_deduplicated_and_safe():
    assert normalize_supported_extensions(
        ".PDF, .md, .pdf, ../secret, *, .tar.gz, .csv"
    ) == [".pdf", ".md", ".csv"]
