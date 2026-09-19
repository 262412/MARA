"""Check installed writer and input ownership without importing checkout code."""

import subprocess
from pathlib import Path


def run_indexing_smoke(python: Path, cwd: Path, env: dict[str, str]) -> None:
    validation = """
import os, sys, tempfile, threading, zipfile
from pathlib import Path
from types import SimpleNamespace
assert 'PYTHONPATH' not in os.environ
from kotaemon import artifact_pipeline
from ktem.index.file import archive
for module in (artifact_pipeline, archive):
    assert Path(module.__file__).resolve().is_relative_to(Path(sys.prefix).resolve())
entered, release = threading.Event(), threading.Event()
calls = []
def produce():
    entered.set()
    assert release.wait(5)
    calls.append('written')
    yield 'progress'
pipeline = SimpleNamespace(run_embedding_in_thread=True, finish=lambda *a: calls.append('finish'))
artifact_pipeline.schedule_writer(pipeline, produce)
writer = pipeline._artifact_writer_future
try:
    assert entered.wait(5)
    assert writer.running() and not writer.cancel()
    try:
        artifact_pipeline.begin_indexing_artifacts(pipeline, {}, enabled=False)
        raise AssertionError('active writer was replaced')
    except RuntimeError:
        pass
finally:
    release.set()
    writer.thread.join(5)
    assert not writer.thread.is_alive()
artifact_pipeline.finish_indexing(pipeline, 'file', 'path')
assert calls == ['written', 'finish']
error = ValueError('owned writer failure')
def fail():
    raise error
writer = artifact_pipeline.consume_in_background(fail)
try:
    writer.result(5)
    raise AssertionError('failure lost')
except ValueError as caught:
    assert caught is error
finally:
    writer.thread.join(5)
    assert not writer.thread.is_alive()
with tempfile.TemporaryDirectory(prefix='installed-index-input-') as directory:
    root = Path(directory)
    source = root / 'source.zip'
    with zipfile.ZipFile(source, 'w') as output:
        output.writestr('input.txt', 'owned input')
    with archive.OwnedZipInputs() as owned:
        paths = owned.prepare(archive.extract_supported_zip_files, source,
            destination_parent=root/'expanded', supported_types={'.txt'})
        assert type(paths) is list and Path(paths[0]).read_text() == 'owned input'
    assert source.exists() and not Path(paths[0]).exists()
print('[wheel-smoke] installed writer wait/error, active ownership and ZIP receipts passed')
"""
    clean_env = env.copy()
    clean_env.pop("PYTHONPATH", None)
    subprocess.run(
        [str(python), "-B", "-c", validation], cwd=cwd, env=clean_env, check=True
    )
