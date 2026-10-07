import shutil

import pytest

from .chroma_test_runtime import owned_chroma_stores


def test_closing_owned_chroma_keeps_other_system_alive(tmp_path):
    owned = tmp_path / "owned"
    other = tmp_path / "other"
    with owned_chroma_stores(other) as create_other:
        control = create_other()
        control.add(embeddings=[[0.1, 0.2]], ids=["control"])
        with owned_chroma_stores(owned) as create_owned:
            first = create_owned()
            first.add(embeddings=[[0.3, 0.4]], ids=["owned"])
            second = create_owned()
            assert second._collection.count() == 1

        assert owned.resolve().is_relative_to(tmp_path.resolve())
        shutil.rmtree(owned)
        assert not owned.exists()
        assert control._collection.count() == 1
        control.add(embeddings=[[0.5, 0.6]], ids=["still-open"])
        assert control._collection.count() == 2


def test_chroma_fixture_refuses_to_take_over_an_existing_system(tmp_path):
    with owned_chroma_stores(tmp_path) as original:
        control = original(path=tmp_path / "existing")
        control.add(embeddings=[[0.1, 0.2]], ids=["control"])
        with owned_chroma_stores(tmp_path) as competing:
            with pytest.raises(ValueError, match="already owned"):
                competing(path=tmp_path / "existing")
            with pytest.raises(ValueError, match="inside its owned"):
                competing(path=tmp_path.parent / "outside")
        assert control._collection.count() == 1
