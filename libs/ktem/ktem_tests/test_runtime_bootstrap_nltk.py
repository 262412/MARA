import os


def test_ensure_llama_index_nltk_cache_creates_offline_punkt_sentinel(
    monkeypatch, tmp_path
):
    from ktem import runtime_bootstrap as module

    cache_dir = tmp_path / "llama_index" / "core" / "_static" / "nltk_cache"
    cache_dir.mkdir(parents=True)

    monkeypatch.setattr(module.sys, "path", [str(tmp_path)])
    monkeypatch.delenv("NLTK_DATA", raising=False)

    module.ensure_llama_index_nltk_cache()

    assert os.environ["NLTK_DATA"] == str(cache_dir)
    assert (cache_dir / "tokenizers" / "punkt").is_dir()
