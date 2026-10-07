"""External index deletion mechanics, independent of file lifecycle ownership."""

from __future__ import annotations

from typing import Any, Callable


def delete_store_batch(
    stage: str,
    store: Any,
    target_ids: tuple[str, ...],
    *,
    delete_docstore: Callable[[Any, tuple[str, ...]], None],
) -> None:
    if stage == "docstore":
        delete_docstore(store, target_ids)
    else:
        store.delete(list(target_ids))


def delete_store_individually(
    stage: str,
    store: Any,
    target_ids: tuple[str, ...],
    file_id: str,
    *,
    delete_docstore: Callable[[Any, tuple[str, ...]], None],
    is_missing_error: Callable[[Exception], bool],
    stage_error: Callable[[str, str, Exception], Exception],
) -> None:
    for target_id in target_ids:
        try:
            if stage == "docstore":
                delete_docstore(store, (target_id,))
            else:
                store.delete([target_id])
        except Exception as exc:
            if is_missing_error(exc):
                continue
            raise stage_error(stage, file_id, exc) from exc


def delete_docstore_entries(store: Any, target_ids: tuple[str, ...]) -> None:
    try:
        store.delete(list(target_ids), refresh_indices=False)
    except TypeError as exc:
        if "refresh_indices" not in str(exc):
            raise
        store.delete(list(target_ids))


def refresh_docstore_index(
    store: Any,
    file_id: str,
    *,
    stage_error: Callable[[str, str, Exception], Exception],
) -> None:
    create_fts_index = getattr(store, "create_fts_index", None)
    if create_fts_index is None:
        return
    try:
        create_fts_index(
            "text",
            tokenizer_name="en_stem",
            replace=True,
        )
    except Exception as exc:
        raise stage_error("docstore", file_id, exc) from exc
