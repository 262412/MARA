"""Windows generation fixture; the HTTP reader still fails closed natively."""

import json
from pathlib import Path
from uuid import uuid4


class NativeProducer:
    def __init__(self, root, file_id, suffix):
        self.directory = Path(root) / "downloads" / file_id / uuid4().hex
        self.directory.mkdir(parents=True)
        self.output_path = self.directory / ("download-" + self.directory.name + suffix)

    def open_temporary(self):
        return self.output_path.open("w+b")

    def publish(self, *, context=None):
        (self.directory / ".ready").write_text(json.dumps(context), encoding="utf-8")
        return self.output_path

    def cleanup(self):
        pass
