import zipfile
from pathlib import Path
from types import SimpleNamespace

import pytest
from ktem.docqa import _runtime_indexing as runtime
from ktem.index.file import archive as archive_module
from ktem.index.file._indexing_service import FileIndexingService

from kotaemon.base import Document


def archive(path, member="report.txt"):
    with zipfile.ZipFile(path, "w") as output:
        output.writestr(member, "owned input")
    return str(path)


def index_and_service(tmp_path, stream, **kwargs):
    index = SimpleNamespace(
        id=7,
        config={"supported_file_types": ".zip,.txt"},
        get_indexing_pipeline=lambda *a: SimpleNamespace(stream=stream),
    )
    service = FileIndexingService(
        index=index,
        supported_file_types=[".txt", ".zip"],
        zip_input_dir=tmp_path / "zip",
        engine=None,
        demo_mode=False,
        notify=lambda *a: None,
        **kwargs,
    )
    return index, service


@pytest.mark.parametrize("consumer", ["runtime", "web"])
def test_internal_zip_lives_until_stream_exit_then_only_owned_root_is_removed(
    tmp_path, consumer
):
    source = archive(tmp_path / "input.zip")
    retained = tmp_path / "zip" / "other-task"
    retained.mkdir(parents=True)
    (retained / "keep.txt").write_text("borrowed")
    observed = []

    def stream(paths, **kwargs):
        path = Path(paths[0])
        assert path.read_text() == "owned input"
        observed.append(path)
        try:
            yield Document("read", channel="debug")
        finally:
            assert path.exists()
        return ["file"], [None], []

    index, web = index_and_service(tmp_path, stream)
    if consumer == "runtime":
        runtime.index_paths(
            index,
            [source],
            reindex=False,
            settings={},
            load_settings=lambda u: {},
            resolve_user_id=lambda u: u,
            user_id="owner",
            zip_input_dir=tmp_path / "zip",
        )
    else:
        list(web.index([source], [], reindex=False, settings={}, user_id="owner"))
    assert observed and not observed[0].exists()
    assert list((tmp_path / "zip").iterdir()) == [retained]
    assert Path(source).exists()
    assert (retained / "keep.txt").read_text() == "borrowed"


@pytest.mark.parametrize("consumer", ["runtime", "web"])
def test_second_invalid_zip_releases_first_owned_extraction(tmp_path, consumer):
    paths = [
        archive(tmp_path / "good.zip"),
        archive(tmp_path / "bad.zip", "../bad.txt"),
    ]
    index, web = index_and_service(
        tmp_path, lambda *a, **kw: pytest.fail("must not index")
    )
    if consumer == "runtime":
        with pytest.raises(ValueError, match="validate-member"):
            runtime.index_paths(
                index,
                paths,
                reindex=False,
                settings={},
                load_settings=lambda u: {},
                resolve_user_id=lambda u: u,
                user_id="owner",
                zip_input_dir=tmp_path / "zip",
            )
    else:
        assert list(
            web.index(paths, [], reindex=False, settings={}, user_id="owner")
        ) == [("", "")]
    assert list((tmp_path / "zip").iterdir()) == []
    assert all(Path(path).exists() for path in paths)


def test_custom_extractor_has_no_implicit_cleanup_receipt(tmp_path):
    borrowed = tmp_path / "borrowed.txt"
    borrowed.write_text("shared cache")
    source = archive(tmp_path / "input.zip")

    def stream(paths, **kwargs):
        assert paths == [str(borrowed)]
        yield Document("read", channel="debug")
        return ["file"], [None], []

    _, web = index_and_service(
        tmp_path, stream, archive_extractor=lambda *a, **kw: [str(borrowed)]
    )
    list(web.index([source], [], reindex=False, settings={}, user_id="owner"))
    assert borrowed.read_text() == "shared cache"


def test_validation_failure_and_cross_thread_close_release_owned_inputs(tmp_path):
    import threading

    source = archive(tmp_path / "input.zip")
    _, web = index_and_service(tmp_path, lambda *a, **kw: pytest.fail("no indexing"))
    web.validate_files = lambda paths: ["rejected"]
    updates = web.index([source], [], reindex=False, settings={}, user_id="owner")
    assert next(updates) == ("", "")
    assert list((tmp_path / "zip").iterdir())
    closer = threading.Thread(target=updates.close)
    closer.start()
    closer.join(5)
    assert not closer.is_alive()
    assert list((tmp_path / "zip").iterdir()) == []


@pytest.mark.parametrize(
    "primary", [None, ValueError("parse failed"), KeyboardInterrupt("cancel")]
)
def test_cleanup_failure_is_locatable_and_preserves_primary(
    tmp_path, monkeypatch, caplog, primary
):
    source = archive(tmp_path / "input.zip")
    created = []

    def refuse(path):
        raise OSError("held owned input")

    expected = type(primary) if primary is not None else OSError
    with monkeypatch.context() as patch:
        patch.setattr(archive_module.shutil, "rmtree", refuse)
        with pytest.raises(expected) as caught:
            with archive_module.OwnedZipInputs() as owned:
                paths = owned.prepare(
                    archive_module.extract_supported_zip_files,
                    source,
                    destination_parent=tmp_path / "zip",
                    supported_types={".txt"},
                )
                created.append(Path(paths[0]).parent)
                if primary is not None:
                    raise primary
        if primary is not None:
            assert caught.value is primary
    assert "ZIP input cleanup failed" in caplog.text
    assert str(created[0]) in caplog.text
    assert created[0].exists()
    archive_module.shutil.rmtree(created[0])


def test_cleanup_refuses_replaced_directory_identity(tmp_path):
    source = archive(tmp_path / "input.zip")
    moved = tmp_path / "moved-owned-root"
    with pytest.raises(OSError, match="Refusing changed ZIP input"):
        with archive_module.OwnedZipInputs() as owned:
            paths = owned.prepare(
                archive_module.extract_supported_zip_files,
                source,
                destination_parent=tmp_path / "zip",
                supported_types={".txt"},
            )
            root = Path(paths[0]).parent
            root.rename(moved)
            root.mkdir()
            (root / "keep.txt").write_text("different owner")
    assert (root / "keep.txt").read_text() == "different owner"
    assert (moved / "report.txt").read_text() == "owned input"


def test_two_thread_preparations_have_distinct_receipts(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    source = archive(tmp_path / "shared.zip")
    ready = Barrier(2, timeout=5)
    paths = []

    def run():
        with archive_module.OwnedZipInputs() as owned:
            extracted = owned.prepare(
                archive_module.extract_supported_zip_files,
                source,
                destination_parent=tmp_path / "zip",
                supported_types={".txt"},
            )
            paths.append(Path(extracted[0]))
            try:
                ready.wait()
                assert all(path.exists() for path in paths)
                ready.wait()
            except BaseException:
                ready.abort()
                raise

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(run) for _ in range(2)]
        for future in futures:
            future.result(10)
    assert paths[0] != paths[1]
    assert not any(path.exists() for path in paths)
    assert Path(source).exists()
