from __future__ import annotations

from typing import Any, cast

from ktem.index.file import FileIndex


def _index(*, private: bool, visible_ids: list[str]) -> FileIndex:
    index = cast(Any, object.__new__(FileIndex))
    index.config = {"private": private}
    index._selector_ui = None
    index.list_source_ids = lambda user_id: (
        list(visible_ids) if user_id == "server-user" else ["victim-file"]
    )
    return index


def test_private_all_selection_ignores_forged_component_user():
    index = _index(private=True, visible_ids=["own-1", "own-2"])

    resolved = index.resolve_selected_ids(
        "server-user",
        ["all", [], "victim-user"],
    )

    assert resolved == ["own-1", "own-2"]


def test_private_explicit_selection_intersects_authenticated_scope():
    index = _index(private=True, visible_ids=["own-1", "own-2"])

    resolved = index.resolve_selected_ids(
        "server-user",
        ["select", ["victim-file", "own-2", "own-2", "own-1"], "victim-user"],
    )

    assert resolved == ["own-2", "own-1"]


def test_private_legacy_selection_intersects_authenticated_scope():
    index = _index(private=True, visible_ids=["own-1"])

    assert index.resolve_selected_ids(
        "server-user", ["victim-file", "own-1"]
    ) == ["own-1"]


def test_public_selection_preserves_explicit_ids():
    index = _index(private=False, visible_ids=["public-1"])

    assert index.resolve_selected_ids(
        "server-user",
        ["select", ["public-2", "public-1"], "ignored-user"],
    ) == ["public-2", "public-1"]
