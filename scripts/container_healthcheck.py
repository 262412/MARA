from __future__ import annotations

import os
import urllib.error
import urllib.request


def check_health(url: str, *, timeout: float = 3.0) -> bool:
    request = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return 200 <= response.status < 400
    except urllib.error.HTTPError as exc:
        return exc.code == 401
    except (OSError, urllib.error.URLError, TimeoutError):
        return False


def main() -> int:
    host = os.environ.get("MARA_HEALTHCHECK_HOST", "127.0.0.1")
    port = os.environ.get("GRADIO_SERVER_PORT", "7860")
    url = os.environ.get("MARA_HEALTHCHECK_URL", f"http://{host}:{port}/")
    return 0 if check_health(url) else 1


if __name__ == "__main__":
    raise SystemExit(main())
