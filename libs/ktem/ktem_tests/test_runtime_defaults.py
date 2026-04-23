from ktem.runtime_defaults import build_kotaemon_settings


def test_runtime_defaults_use_local_multilingual_reranker_by_default(tmp_path):
    settings = build_kotaemon_settings(
        base_dir=tmp_path,
        app_data_dir=tmp_path / "app-data",
    )

    assert settings["KH_RERANKINGS"]["local"]["default"] is True
    assert settings["KH_RERANKINGS"]["local"]["spec"] == {
        "__type__": "kotaemon.rerankings.LocalMultilingualReranking"
    }
    assert settings["KH_RERANKINGS"]["cohere"]["default"] is False
