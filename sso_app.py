"""Compatibility wrapper for the package-owned MARA SSO application."""

import os

from ktem.sso import create_sso_app

app = create_sso_app(host=os.getenv("GRADIO_SERVER_NAME"))
