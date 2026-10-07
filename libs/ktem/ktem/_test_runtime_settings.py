"""Validate the active test source before TheFlow initializes global storage."""

import os

from ktem.runtime_bootstrap import _load_settings_values

globals().update(_load_settings_values(os.environ["MARA_PYTEST_SETTINGS_SOURCE"]))
