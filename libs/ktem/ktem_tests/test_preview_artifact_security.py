from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import cast

import pytest
from ktem_tests.preview_test_utils import write_text_pdf


def _publisher() -> Callable[..., Path]:
    import ktem.preview.service as service_module

    return cast(Callable[..., Path], getattr(service_module, "publish_validated_pdf"))


def test_publish_rejects_directory_symlink_below_trusted_root(tmp_path):
    from ktem.preview.errors import PreviewConversionError

    publish_validated_pdf = _publisher()

    canonical = write_text_pdf(tmp_path / "canonical.pdf", ["canonical"])
    trusted_root = tmp_path / "visible"
    outside = tmp_path / "outside"
    trusted_root.mkdir()
    outside.mkdir()
    (trusted_root / "redirect").symlink_to(outside, target_is_directory=True)

    with pytest.raises(PreviewConversionError, match="symlink"):
        publish_validated_pdf(canonical, trusted_root, Path("redirect") / "entry.pdf")

    assert not (outside / "entry.pdf").exists()


def test_publish_rejects_leaf_symlink_without_touching_victim(tmp_path):
    from ktem.preview.errors import PreviewConversionError

    publish_validated_pdf = _publisher()

    canonical = write_text_pdf(tmp_path / "canonical.pdf", ["canonical"])
    trusted_root = tmp_path / "visible"
    trusted_root.mkdir()
    victim = tmp_path / "victim.txt"
    victim.write_text("do not overwrite", encoding="utf-8")
    (trusted_root / "entry.pdf").symlink_to(victim)

    with pytest.raises(PreviewConversionError, match="symlink"):
        publish_validated_pdf(canonical, trusted_root, "entry.pdf")

    assert victim.read_text(encoding="utf-8") == "do not overwrite"


@pytest.mark.parametrize("entry", [Path("../escape.pdf"), Path("/tmp/escape.pdf")])
def test_publish_rejects_entries_outside_trusted_root(tmp_path, entry):
    from ktem.preview.errors import PreviewConversionError

    publish_validated_pdf = _publisher()

    canonical = write_text_pdf(tmp_path / "canonical.pdf", ["canonical"])
    trusted_root = tmp_path / "visible"

    with pytest.raises(PreviewConversionError, match="trusted cache root"):
        publish_validated_pdf(canonical, trusted_root, entry)


def test_valid_same_name_poison_is_replaced_with_canonical_artifact(tmp_path):
    publish_validated_pdf = _publisher()

    canonical = write_text_pdf(tmp_path / "canonical" / "entry.pdf", ["canonical"])
    trusted_root = tmp_path / "visible"
    poison = write_text_pdf(trusted_root / "entry.pdf", ["attacker content"])
    poison_bytes = poison.read_bytes()

    published = publish_validated_pdf(canonical, trusted_root, "entry.pdf")

    assert published == trusted_root.absolute() / "entry.pdf"
    assert published.read_bytes() == canonical.read_bytes()
    assert published.read_bytes() != poison_bytes
