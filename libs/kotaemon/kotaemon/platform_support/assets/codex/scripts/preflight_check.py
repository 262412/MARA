#!/usr/bin/env python3
from __future__ import annotations

import os
import shutil


def main() -> int:
    required = ["OPENAI_API_KEY", "DEEPSEEK_API_KEY"]
    present = [name for name in required if os.getenv(name)]
    mara_path = shutil.which("MARA")
    if mara_path:
        print(f"Detected MARA CLI: {mara_path}")
    else:
        print(
            "MARA CLI not found. Install it with 'pip install slide-cli' "
            "or 'uv tool install slide-cli', then run 'MARA doctor'."
        )
    print(f"Detected keys: {', '.join(present) if present else 'none'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
