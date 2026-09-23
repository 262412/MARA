"""Fresh-process isolation counterexamples; this file needs no business import."""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[1]
PROBE = r"""
import importlib.util
import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace

repository, owned, scenario = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3]
sys.path.insert(0, str(repository))
from pytest_runtime_isolation import start_process_test_runtime, TestRuntimePaths

fake_user = owned / 'fake-user'
fake_user.mkdir()
(fake_user / '.env').write_text('MARA_GUARD_CANARY=loaded\n')
os.environ.update(MARA_PYTEST_RUNTIME_PARENT=str(owned / 'sessions'),
                  MARA_DIAGNOSTIC_ISOLATION_REQUIRED='1')
for key in ('MARA_PYTEST_RUNTIME_ROOT', 'MARA_DIAGNOSTIC_CHILD',
            'MARA_PYTEST_OWNER_TOKEN', 'THEFLOW_SETTINGS_MODULE'):
    os.environ.pop(key, None)
spec = importlib.util.spec_from_file_location('guard_probe_bootstrap',
    repository / 'libs/ktem/ktem/runtime_bootstrap.py')
bootstrap = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = bootstrap
spec.loader.exec_module(bootstrap)
bootstrap.PlatformDirs = lambda **_: SimpleNamespace(user_config_dir=str(fake_user),
    user_data_dir=str(fake_user / 'data'), user_cache_dir=str(fake_user / 'cache'))
accesses = []
def observe(event, args):
    if event in ('open', 'os.mkdir', 'os.remove', 'os.rmdir', 'sqlite3.connect'):
        value = args[0]
        if isinstance(value, (str, bytes)):
            path = Path(os.fsdecode(value)).absolute()
            if path.is_relative_to(fake_user):
                accesses.append(event)

blocked, normal, runtime = False, False, None
try:
    if scenario == 'early-ktem':
        sys.modules['ktem'] = SimpleNamespace()
    elif scenario == 'early-theflow':
        sys.modules['theflow.settings'] = SimpleNamespace(settings=SimpleNamespace(_initialized=False))
    runtime = start_process_test_runtime()
    # The detector runs after the actual guard: a refusal must precede access.
    sys.addaudithook(observe)
    if scenario == 'missing-marker':
        os.environ.pop('MARA_PYTEST_RUNTIME_ROOT')
    elif scenario == 'wrong-root':
        os.environ.update(TestRuntimePaths.from_root(fake_user).environment())
    elif scenario == 'missing-owner':
        (runtime.paths.root / '.mara-pytest-owner').unlink()
    elif scenario == 'external-settings':
        os.environ['THEFLOW_SETTINGS_MODULE'] = str(fake_user / 'flowsettings.py')
    elif scenario == 'external-home':
        os.environ['HOME'] = str(fake_user)
    elif scenario in {'late-after-close', 'late-worker', 'cleanup-secondary'}:
        if scenario == 'cleanup-secondary':
            (runtime.paths.root / '.mara-pytest-owner').unlink()
            try:
                runtime.close()
            except RuntimeError:
                pass
        runtime.close()
        if scenario == 'late-worker':
            import threading
            errors = []
            def late():
                try:
                    bootstrap.load_packaged_runtime_env()
                except RuntimeError:
                    errors.append('blocked')
            worker = threading.Thread(target=late)
            worker.start()
            worker.join(5)
            assert not worker.is_alive() and errors == ['blocked']
    elif scenario == 'disabled-required-marker':
        os.environ.pop('MARA_DIAGNOSTIC_ISOLATION_REQUIRED')
    elif scenario == 'normal-child':
        import subprocess
        child = subprocess.run([sys.executable, '-B', '-c',
            'import sys; sys.path.insert(0, sys.argv[1]); '
            'from pytest_runtime_isolation import start_process_test_runtime; '
            'r=start_process_test_runtime(); print(r.paths.root); r.close()',
            str(repository)], env={k: v for k, v in os.environ.items() if k != 'PYTHONPATH'},
            capture_output=True, text=True)
        assert child.returncode == 0, child.stdout + child.stderr
        assert Path(child.stdout.strip()).is_relative_to(runtime.paths.root)
        assert not Path(child.stdout.strip()).exists()
    elif scenario == 'lost-child-environment':
        import subprocess
        environment = dict(os.environ)
        environment.pop('MARA_PYTEST_RUNTIME_ROOT')
        subprocess.run([sys.executable, '-B', '-c',
            'from pathlib import Path; import sys; Path(sys.argv[1]).write_text("bad")',
            str(fake_user / 'child-write')], env=environment, check=True)
    bootstrap.load_packaged_runtime_env()
    normal = bootstrap.get_runtime_paths().config_dir.is_relative_to(runtime.paths.root)
except RuntimeError:
    blocked = True
finally:
    if runtime and not runtime.closed:
        try:
            runtime.close()
        except RuntimeError:
            pass  # Only the deliberately missing marker; caller retains the root.
print(json.dumps({'scenario': scenario, 'blocked': blocked, 'normal': normal,
                  'outside_accesses': accesses, 'canary_loaded': 'MARA_GUARD_CANARY' in os.environ}))
"""


class ProcessIsolationContract(unittest.TestCase):
    def probe(self, scenario):
        parent = os.environ.get("MARA_ISOLATION_PROBE_PARENT")
        if not parent and os.environ.get("MARA_PYTEST_RUNTIME_ROOT"):
            parent = str(Path(os.environ["MARA_PYTEST_RUNTIME_ROOT"]) / "guard-probes")
        if not parent:
            self.fail("Set an explicit owned MARA_ISOLATION_PROBE_PARENT")
        Path(parent).mkdir(parents=True, exist_ok=True)
        root = Path(tempfile.mkdtemp(prefix="process-guard-", dir=parent))
        result = subprocess.run(
            [sys.executable, "-B", "-c", PROBE, str(REPOSITORY), str(root), scenario],
            cwd=root,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=45,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn("Exception ignored", result.stderr)
        payload = json.loads(result.stdout.strip().splitlines()[-1])
        (root / "result.json").write_text(json.dumps(payload, indent=2))
        return payload

    def test_normal_owned_configuration(self):
        for scenario in ("normal", "normal-child"):
            with self.subTest(scenario=scenario):
                result = self.probe(scenario)
                self.assertTrue(result["normal"], result)
                self.assertFalse(result["blocked"], result)
                self.assertEqual(result["outside_accesses"], [])

    def test_rejects_bypass_before_fake_user_access(self):
        for scenario in (
            "missing-marker",
            "wrong-root",
            "missing-owner",
            "external-settings",
            "external-home",
            "early-ktem",
            "early-theflow",
            "late-after-close",
            "late-worker",
            "cleanup-secondary",
            "disabled-required-marker",
            "lost-child-environment",
        ):
            with self.subTest(scenario=scenario):
                result = self.probe(scenario)
                self.assertTrue(result["blocked"], result)
                self.assertEqual(result["outside_accesses"], [], result)
                self.assertFalse(result["canary_loaded"], result)


if __name__ == "__main__":
    unittest.main()
