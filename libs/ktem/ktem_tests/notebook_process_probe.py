"""Owned subprocess for the real Notebook transaction barrier."""

import sys
import time
from pathlib import Path

from pytest_runtime_isolation import start_process_test_runtime


def main():
    runtime = start_process_test_runtime()
    try:
        from ktem.docqa import _runtime_notebook as notebook
        from sqlmodel import create_engine

        database, conversation_id, barrier_name = sys.argv[1:]
        barrier = Path(barrier_name)
        engine = create_engine(database)
        notebook.engine = engine
        original = notebook.add_note

        def held(*args, **kwargs):
            (barrier / "blocked").write_text("loaded inside independent Session")
            deadline = time.monotonic() + 25
            while not (barrier / "release").exists():
                if time.monotonic() > deadline:
                    raise TimeoutError("owned Notebook producer was not released")
                time.sleep(0.02)
            return original(*args, **kwargs)

        notebook.add_note = held
        notebook.add_note_to_conversation(
            conversation_id,
            user_id="owner",
            title="process",
            text="process",
            note_id="process",
        )
        engine.dispose()
    finally:
        runtime.close()


if __name__ == "__main__":
    main()
