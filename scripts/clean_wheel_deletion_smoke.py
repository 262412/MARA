"""Exercise the installed store boundary and original deletion facade."""

import subprocess
from pathlib import Path


def run_deletion_smoke(python: Path, cwd: Path, env: dict[str, str]) -> None:
    validation = """
import os, sys
from pathlib import Path
from types import SimpleNamespace
assert 'PYTHONPATH' not in os.environ
def offline(event, args):
    if event in ('socket.connect', 'socket.getaddrinfo'):
        raise RuntimeError('Installed deletion smoke attempted network access')
sys.addaudithook(offline)
import ktem.index.file
before = set(sys.modules)
from ktem.index.file import index_store_cleanup
assert set(sys.modules) - before == {'ktem.index.file.index_store_cleanup'}
from ktem.index.file import deletion
for module in (index_store_cleanup, deletion):
    assert Path(module.__file__).resolve().is_relative_to(Path(sys.prefix).resolve())
assert deletion.DeletionResult.__module__ == 'ktem.index.file.deletion'
assert deletion.DeletionError.__module__ == 'ktem.index.file.deletion'
calls = []
def delete(ids, **kwargs):
    calls.append((ids, kwargs))
    if len(ids) > 1 or ids == ['missing']:
        raise KeyError('missing')
def refresh(*args, **kwargs):
    calls.append((args, kwargs))
store = SimpleNamespace(delete=delete, create_fts_index=refresh)
coordinator = deletion.DeletionCoordinator(engine=None, source_table=None,
    index_table=None, vector_store=None, doc_store=None, file_storage_path=None)
coordinator._delete_store('docstore', store, ('missing', 'kept'), 'file')
assert calls == [(['missing', 'kept'], {'refresh_indices': False}),
    (['missing'], {'refresh_indices': False}), (['kept'], {'refresh_indices': False}),
    (('text',), {'tokenizer_name': 'en_stem', 'replace': True})]
calls.clear()
index_store_cleanup.delete_docstore_entries(
    SimpleNamespace(delete=lambda ids: calls.append(ids)), ('z', 'a', 'z'))
assert calls == [['z', 'a', 'z']]
print('[wheel-smoke] installed deletion facade, store cleanup and legacy signature passed')
"""
    clean_env = env.copy()
    clean_env.pop("PYTHONPATH", None)
    subprocess.run(
        [str(python), "-B", "-c", validation], cwd=cwd, env=clean_env, check=True
    )
