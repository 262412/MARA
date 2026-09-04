from __future__ import annotations

import builtins

import pytest

from kotaemon.loaders.utils.adobe import request_adobe_service


def test_adobe_provider_missing_dependency_has_safe_actionable_diagnostic(monkeypatch):
    real_import = builtins.__import__

    def block_adobe(name, *args, **kwargs):
        if name == "adobe" or name.startswith("adobe."):
            raise ImportError("blocked for dependency diagnostic")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", block_adobe)

    with pytest.raises(ImportError) as error:
        request_adobe_service("unused.pdf")

    message = str(error.value)
    assert "not compatible with the current MARA runtime" in message
    assert "built-in PDF reader" in message
    assert "bump-and-unfreeze-requirements" not in message
