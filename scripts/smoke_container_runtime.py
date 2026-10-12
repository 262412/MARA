from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

OLLAMA_PROBE = r"""
import json
from urllib.request import urlopen

with urlopen("http://127.0.0.1:11434/api/version", timeout=5) as response:
    version = json.load(response)["version"]
if version != "0.31.2":
    raise RuntimeError(f"Unexpected Ollama version: {version!r}")
with urlopen("http://127.0.0.1:11434/api/tags", timeout=5) as response:
    models = json.load(response)["models"]
if not isinstance(models, list):
    raise RuntimeError("Unexpected Ollama model-list response")
print(json.dumps({"version": version, "model_count": len(models)}))
"""

PCRE2_PROBE = r"""
import ctypes as c
import hashlib
import json
from pathlib import Path
import resource
import subprocess

resource.setrlimit(resource.RLIMIT_CPU, (5, 5))
resource.setrlimit(resource.RLIMIT_AS, (256 * 1024 * 1024,) * 2)
resource.setrlimit(resource.RLIMIT_CORE, (0, 0))

def command(*args, input=None):
    return subprocess.run(args, input=input, text=True, capture_output=True,
                          check=True, timeout=5).stdout

def validate_dpkg_verification(output, configuration):
    if not output:
        return
    assert {"path-exclude /usr/share/doc/*", "path-include /usr/share/doc/*/copyright"} <= set(configuration.splitlines()), configuration
    # Only these three files are excluded by the fixed Debian slim base.
    permitted = {("missing", "/usr/share/doc/libpcre2-8-0/" + name)
                 for name in ("README.Debian", "changelog.Debian.gz", "changelog.gz")}
    assert all(tuple(line.split()) in permitted for line in output.splitlines()), output

fields = command("dpkg-query", "-W", "-f=${Version}\n${Architecture}\n${Status}\n"
                 "${source:Package}\n${source:Version}\n", "libpcre2-8-0").splitlines()
assert fields == ["10.42-1+deb12u2", "amd64", "install ok installed",
                  "pcre2", "10.42-1+deb12u2"], fields
files = command("dpkg-query", "-L", "libpcre2-8-0").splitlines()
library = next(Path(p).resolve() for p in files
               if "/libpcre2-8.so." in p and not Path(p).is_symlink())
owner = command("dpkg-query", "-S", str(library)).strip()
assert owner.startswith("libpcre2-8-0:amd64: "), owner
digest = hashlib.sha256(library.read_bytes()).hexdigest()
# Debian's signed Bookworm amd64 u2 package, verified before the runtime pin.
assert digest == "092bc945140e65c691c7c717d71083111f46813f31a76dd848bf82e91450778b", digest
lib = c.CDLL("libpcre2-8.so.0")
mapped = sorted({line.split()[-1] for line in Path("/proc/self/maps").read_text().splitlines()
                 if "/libpcre2-8.so." in line})
assert mapped and all(Path(p).resolve() == library for p in mapped), mapped
pointer, size, unsigned, integer = c.c_void_p, c.c_size_t, c.c_uint32, c.c_int
match_args = [pointer, c.c_char_p, size, size, unsigned, pointer, pointer]
signatures = {
    "compile": (pointer, [c.c_char_p, size, unsigned, c.POINTER(integer), c.POINTER(size), pointer]),
    "code_free": (None, [pointer]),
    "match_data_create_from_pattern": (pointer, [pointer, pointer]),
    "match_data_free": (None, [pointer]),
    "match": (integer, match_args),
    "dfa_match": (integer, match_args + [c.POINTER(integer), size]),
    "jit_compile": (integer, [pointer, unsigned]),
    "jit_match": (integer, match_args),
    "match_context_create": (pointer, [pointer]),
    "match_context_free": (None, [pointer]),
    "jit_stack_create": (pointer, [size, size, pointer]),
    "jit_stack_assign": (None, [pointer, pointer, pointer]),
    "jit_stack_free": (None, [pointer]),
    "pattern_convert": (integer, [c.c_char_p, size, unsigned, c.POINTER(pointer), c.POINTER(size), pointer]),
    "converted_pattern_free": (None, [pointer]),
}
api = {}
for name, (result, arguments) in signatures.items():
    function = getattr(lib, "pcre2_" + name + "_8")
    function.restype, function.argtypes = result, arguments
    api[name] = function

def compile_pattern(pattern):
    error, offset = integer(), size()
    code = api["compile"](pattern, len(pattern), 0, c.byref(error), c.byref(offset), None)
    assert code, (error.value, offset.value)
    data = api["match_data_create_from_pattern"](code, None)
    assert data
    return code, data

checks = {}
# Upstream 1dcd0cf4 / CVE-2026-89161: fast JIT reuses copied-subject match data.
code, data = compile_pattern(b"abc")
assert api["jit_compile"](code, 1) == 0
assert api["match"](code, b"abc", 3, 0, 0x4000, data, None) == 1
assert api["jit_match"](code, b"abcz", 4, 0, 0, data, None) == 1
api["match_data_free"](data)
api["code_free"](code)
checks["CVE-2026-89161"] = "copied-subject reuse and free passed"

# Upstream c932e704 / CVE-2026-86145: bounded recursive DFA workspace reuse.
pattern = b"(*LIMIT_HEAP=4)(?=(?=(?=(?=(?=(?=(?=(?=a))(?R)))))))."
code, data = compile_pattern(pattern)
workspace = (integer * 1000)()
result = api["dfa_match"](code, b"a", 1, 0, 0, data, None, workspace, len(workspace))
assert result == -63, result  # PCRE2_ERROR_HEAPLIMIT
api["match_data_free"](data)
api["code_free"](code)
checks["CVE-2026-86145"] = result

# Upstream 2b403829 / CVE-2026-103111, with its expansion made explicit.
pattern = b"((?(DEFINE)" + rb"()\g{-1}" * 1400 + b").{1}(?R)|)"
code, data = compile_pattern(pattern)
assert api["jit_compile"](code, 1) == 0
context = api["match_context_create"](None)
stack = api["jit_stack_create"](32768, 192 * 1024, None)
assert context and stack
api["jit_stack_assign"](context, None, stack)
result = api["jit_match"](code, b"AAAAAA", 6, 0, 0, data, context)
assert result == -46, result  # PCRE2_ERROR_JIT_STACKLIMIT
api["match_data_free"](data)
api["match_context_free"](context)
api["jit_stack_free"](stack)
api["code_free"](code)
checks["CVE-2026-103111"] = result

# A small converter check is not the 32-bit overflow regression for CVE-2026-89157.
converted, length = pointer(), size()
pattern = b"notes/*.md"
assert api["pattern_convert"](pattern, len(pattern), 0x10, c.byref(converted), c.byref(length), None) == 0
assert b"notes" in c.string_at(converted, length.value)
api["converted_pattern_free"](converted)
checks["converter_smoke"] = "passed; 32-bit overflow not exercised on amd64"
assert command("grep", "-Po", r"(?<=item:)[0-9]+", input="item:42\nskip\n") == "42\n"
checks["grep_P"] = "passed"
links = command("ldd", "/usr/bin/grep")
grep_library = next(line.split("=>", 1)[1].split()[0] for line in links.splitlines()
                    if line.lstrip().startswith("libpcre2-8.so.0 "))
assert Path(grep_library).resolve() == library, links
verification = command("dpkg", "--verify", "libpcre2-8-0")
validate_dpkg_verification(verification, Path("/etc/dpkg/dpkg.cfg.d/docker").read_text())
checks["dpkg_verify"] = verification
packages = command("dpkg-query", "-W", "-f=${binary:Package}\t${Version}\t${Architecture}\t${db:Status-Abbrev}\n")
print(json.dumps({"package_fields": fields, "library": str(library), "library_owner": owner,
                  "library_sha256": digest, "loaded_library_paths": mapped,
                  "grep_links": links, "checks": checks,
                  "word_size": c.sizeof(size) * 8, "installed_packages": packages}))
"""


def _run(
    *command: str, check: bool = True, timeout: float | None = None
) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        command,
        text=True,
        capture_output=True,
        check=False,
        timeout=timeout,
    )
    if check and completed.returncode:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise RuntimeError(f"{' '.join(command)} failed: {detail}")
    return completed


def _inspect(image: str) -> None:
    user = _run(
        "docker", "image", "inspect", image, "--format", "{{.Config.User}}"
    ).stdout.strip()
    if user != "10001:10001":
        raise RuntimeError(f"Container image user is {user!r}, expected 10001:10001")
    healthcheck = _run(
        "docker",
        "image",
        "inspect",
        image,
        "--format",
        "{{json .Config.Healthcheck}}",
    ).stdout.strip()
    if healthcheck in {"", "null", "<no value>"}:
        raise RuntimeError("Container image has no healthcheck")


def _wait_for_health(container: str, timeout: float = 180.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        state = _run(
            "docker",
            "inspect",
            container,
            "--format",
            "{{.State.Status}} {{if .State.Health}}{{.State.Health.Status}}{{end}}",
        ).stdout.strip()
        if state == "running healthy":
            return
        if not state.startswith("running"):
            break
        time.sleep(2)
    logs = _run("docker", "logs", container, check=False)
    detail = (logs.stdout + logs.stderr).strip()
    raise RuntimeError(f"Container did not become healthy: {detail}")


def _check_runtime(container: str, target: str) -> None:
    _run(
        "docker",
        "exec",
        container,
        "sh",
        "-ec",
        (
            'test -w "$KH_APP_DATA_DIR"; '
            'probe="$KH_APP_DATA_DIR/.runtime-smoke"; '
            'touch "$probe"; rm "$probe"; test ! -w /opt/mara'
        ),
    )
    processes = _run("docker", "top", container, "-eo", "pid,args").stdout
    has_ollama = "ollama serve" in processes
    if has_ollama != (target == "ollama"):
        raise RuntimeError(
            f"Unexpected Ollama process state for {target}: running={has_ollama}"
        )
    if target == "ollama":
        _run(
            "docker",
            "exec",
            container,
            "/opt/mara/.venv/bin/python",
            "-I",
            "-c",
            OLLAMA_PROBE,
            timeout=15,
        )


def _check_pcre2(container: str, image: str, target: str, evidence_dir: Path) -> None:
    evidence_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        suffix: evidence_dir / f"{target}.pcre2.{suffix}"
        for suffix in ("stdout", "stderr", "json")
    }
    if any(path.exists() for path in paths.values()):
        raise FileExistsError("Use a new evidence directory for each smoke attempt")
    started = datetime.now(timezone.utc).isoformat()
    try:
        result = _run(
            "docker",
            "exec",
            container,
            "/opt/mara/.venv/bin/python",
            "-I",
            "-c",
            PCRE2_PROBE,
            check=False,
            timeout=30,
        )
    except subprocess.TimeoutExpired as exc:
        for stream, partial in (("stdout", exc.stdout), ("stderr", exc.stderr)):
            with paths[stream].open("xb") as output:
                output.write(partial or b"")
        raise
    for stream, content in (("stdout", result.stdout), ("stderr", result.stderr)):
        with paths[stream].open("x", encoding="utf-8") as output:
            output.write(content)
    if result.returncode:
        raise RuntimeError(f"PCRE2 runtime probe failed: {result.stderr}")
    record = {
        "image": image,
        "image_id": _run(
            "docker", "image", "inspect", image, "--format", "{{.Id}}"
        ).stdout.strip(),
        "target": target,
        "started_at": started,
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "probe_sha256": hashlib.sha256(PCRE2_PROBE.encode()).hexdigest(),
        "probe": json.loads(result.stdout),
    }
    with paths["json"].open("x", encoding="utf-8") as output:
        json.dump(record, output, indent=2)
    print(f"PCRE2 runtime probe passed: {target}, {record['image_id']}")


def smoke(
    image: str,
    target: str,
    secret_file: Path,
    evidence_dir: Path = Path("container-evidence"),
) -> None:
    if not secret_file.is_file():
        raise RuntimeError(f"Password secret is not a regular file: {secret_file}")
    _inspect(image)
    suffix = uuid.uuid4().hex[:12]
    container = f"mara-smoke-{target}-{suffix}"
    volume = f"mara-smoke-data-{target}-{suffix}"
    _run("docker", "volume", "create", volume)
    try:
        _run(
            "docker",
            "run",
            "--detach",
            "--name",
            container,
            "--network",
            "host",
            "--env",
            "GRADIO_SERVER_NAME=127.0.0.1",
            "--env",
            "MARA_QDRANT_URL=" + os.environ["MARA_QDRANT_URL"],
            "--env",
            "MARA_QDRANT_API_KEY=" + os.environ["MARA_QDRANT_API_KEY"],
            "--mount",
            (
                f"type=bind,src={secret_file.resolve()},"
                "dst=/run/secrets/mara_admin_password,readonly"
            ),
            "--mount",
            f"type=volume,src={volume},dst=/var/lib/mara",
            image,
        )
        _wait_for_health(container)
        _check_runtime(container, target)
        _check_pcre2(container, image, target, evidence_dir)
    finally:
        _run("docker", "rm", "--force", container, check=False)
        _run("docker", "volume", "rm", volume, check=False)


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke a built MARA container target.")
    parser.add_argument("--image", required=True)
    parser.add_argument("--target", choices=("lite", "full", "ollama"), required=True)
    parser.add_argument("--secret-file", type=Path, required=True)
    parser.add_argument("--evidence-dir", type=Path, default=Path("container-evidence"))
    args = parser.parse_args()
    smoke(args.image, args.target, args.secret_file, args.evidence_dir)
    print(f"Container runtime smoke passed: {args.target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
