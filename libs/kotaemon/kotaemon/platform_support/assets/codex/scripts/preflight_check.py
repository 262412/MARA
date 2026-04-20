#!/usr/bin/env python3
from __future__ import annotations

import os
import shutil


def main() -> int:
    required = ["OPENAI_API_KEY", "DEEPSEEK_API_KEY"]
    present = [name for name in required if os.getenv(name)]
    kotaemon_path = shutil.which("kotaemon")
    if kotaemon_path:
        print(f"Detected kotaemon CLI: {kotaemon_path}")
    else:
        print(
            "kotaemon CLI not found. Install it with 'pip install kotaemon-app' "
            "or 'uv tool install kotaemon-app', then run 'kotaemon app init' "
            "and 'kotaemon app doctor'."
        )
    print(f"Detected keys: {', '.join(present) if present else 'none'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
