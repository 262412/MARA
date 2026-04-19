#!/usr/bin/env python3
from __future__ import annotations

import os


def main() -> int:
    required = ["OPENAI_API_KEY", "DEEPSEEK_API_KEY"]
    present = [name for name in required if os.getenv(name)]
    print(f"Detected keys: {', '.join(present) if present else 'none'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
