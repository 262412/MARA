"""Observe real indexing producers; only model gates are controllable."""

from importlib import import_module
from pathlib import Path
from typing import Any


class IndexingLifetimeObserver:
    def __init__(self, patch):
        from kotaemon import artifact_pipeline

        self.writers: list[Any] = []
        self.model = import_module("libs.ktem.ktem_tests.chat_submission_model_fixture")
        original = artifact_pipeline.consume_in_background

        def observe(factory):
            writer = original(factory)
            self.writers.append(writer)
            return writer

        patch.setattr(artifact_pipeline, "consume_in_background", observe)

    def snapshot(self):
        from theflow.settings import settings

        root = Path(settings.KH_ZIP_INPUT_DIR)
        return {
            "inputs": sorted(path.name for path in root.iterdir())
            if root.exists()
            else [],
            "writers": [
                {
                    "done": writer.done(),
                    "alive": writer.thread.is_alive(),
                    "cancelled": writer.cancelled(),
                }
                for writer in self.writers
            ],
            "embedding_started": self.model.embedding_started.is_set(),
        }

    def release(self):
        self.model.embedding_release.set()

    def close(self):
        self.release()
        for writer in self.writers:
            writer.wait_until_stopped()
