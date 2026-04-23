import sys
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
KOTAEMON_ROOT = PACKAGE_ROOT.parents[1] / "kotaemon"

if str(PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT))
if str(KOTAEMON_ROOT) not in sys.path:
    sys.path.insert(0, str(KOTAEMON_ROOT))

for module_name in list(sys.modules):
    if module_name == "kotaemon" or module_name.startswith("kotaemon."):
        del sys.modules[module_name]
