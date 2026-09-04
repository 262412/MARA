"""Source and container entrypoint for the MARA application."""

import os


def log_startup(message: str) -> None:
    print(f"[MARA Azure startup] {message}", flush=True)


if os.getenv("WEBSITE_SITE_NAME"):
    os.environ.setdefault("KH_APP_DATA_DIR", "/home/site/mara_data")
    log_startup(
        f"Azure App Service detected; KH_APP_DATA_DIR={os.environ['KH_APP_DATA_DIR']}"
    )


from ktem.launcher import launch_app  # noqa: E402

log_startup("Launching through the policy-aware MARA launcher")
launch_app(
    host=os.getenv("GRADIO_SERVER_NAME") or "0.0.0.0",
    inbrowser=False,
)
