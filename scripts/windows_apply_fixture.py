"""Test-only startup guard for installed console scripts on an owned CI account."""

import atexit
import getpass
import json
import os
import sys
from pathlib import Path


def hosted_scope():
    if not (
        sys.platform == "win32"
        and os.environ.get("GITHUB_ACTIONS") == "true"
        and os.environ.get("RUNNER_ENVIRONMENT") == "github-hosted"
        and os.environ.get("RUNNER_OS") == "Windows"
        and os.environ.get("GITHUB_REPOSITORY") == "262412/MARA"
        and getpass.getuser().lower() == "runneradmin"
    ):
        raise RuntimeError("Default-path apply requires the disposable hosted account")
    from platformdirs import PlatformDirs
    from platformdirs.windows import get_win_folder

    known = Path(get_win_folder("CSIDL_LOCAL_APPDATA"))
    root = known / "Cinnamon" / "MARA"
    dirs = PlatformDirs(appname="MARA", appauthor="Cinnamon")
    actual = [
        Path(dirs.user_config_dir),
        Path(dirs.user_data_dir),
        Path(dirs.user_cache_dir),
    ]
    if (
        not known.is_absolute()
        or known != known.resolve()
        or known.parents[1].name.lower() != "runneradmin"
        or root != root.resolve()
        or any(not path.resolve().is_relative_to(root) for path in actual)
    ):
        raise RuntimeError("Known Folder is outside the explicitly owned MARA scope")
    return root, {"known_folder": str(known), "paths": [str(p) for p in actual]}


def activate_console_guard():
    if os.environ.get("MARA_CI_DEFAULT_APPLY_CHILD") != "1":
        return
    root, _ = hosted_scope()
    authorization = json.loads(
        (root / "authorization.json").read_text(encoding="utf-8")
    )
    if (
        authorization["root"] != str(root)
        or authorization["sha"] != os.environ["GITHUB_SHA"]
        or os.environ.get("MARA_DIAGNOSTIC_EVIDENCE_DIR") != str(root)
    ):
        raise RuntimeError("Console child scope differs from its authorization")
    from pytest_runtime_isolation import start_process_test_runtime

    runtime = start_process_test_runtime()
    receipt = root / f"console-guard-{os.getpid()}.json"
    state = {"pid": os.getpid(), "guard_before_business_import": True, "closed": False}
    receipt.write_text(json.dumps(state))

    def close():
        runtime.close()
        state["closed"] = not runtime.paths.root.exists()
        receipt.write_text(json.dumps(state))

    atexit.register(close)
