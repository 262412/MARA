# Reviewer installation bundle

The Windows x64 ZIP contains built MARA wheels, a checksum-verified uv 0.11.19
bootstrap executable, a hashed runtime lock, prebuilt wheels for dependencies
without compatible Windows wheels, and `Install.cmd` / `Start.cmd` launchers.
Python 3.10.19 and the remaining pinned binary dependencies are downloaded on
first installation. There is no dependency on a published MARA PyPI package.

The source baseline for this work is `main` at
`dfcca9987fa4f4d3c5e4da303217c32692032b65`. The runtime change adds the optional
`MARA_APP_HOME` environment variable for isolated config, data, and cache paths.
An unset variable retains the existing platform paths; Desktop paths keep their
existing precedence. Command names, options, and document QA behavior are unchanged.
The help page now uses its bundled Markdown when user documentation is absent,
reads the correct release-note cache filename, and applies connection/read timeouts
to optional remote help requests. The reviewer launcher sets
`MARA_ALLOW_REMOTE_HELP=False` to keep UI startup independent of remote documentation.

Build and validate locally before publishing. The existing release-containment
workflow settings are unchanged. This procedure does not upload files or move tags.
The bundle manifest must identify the actual source commit used for its wheels.

## Maintainer build

Use a separate standalone checkout and an external build directory. Do not
synchronize the shared development environment or build inside a linked worktree's
canonical environment. The builder needs 64-bit Python 3.10, uv 0.11.19,
`build==1.2.2.post1`, `setuptools==80.9.0`, `wheel==0.45.1`,
`setuptools-git-versioning==2.1.0`, `pip==25.3`, `tomli==2.2.1`, and `packaging`.

1. Export and prebuild the locked dependencies:

   ```powershell
   python scripts/prepare_reviewer_dependencies.py --output-dir D:/MARA-build
   ```

2. Build each of `libs/kotaemon`, `libs/ktem`, `libs/slide_cli`, and `.` with
   `python -m build --no-isolation --wheel`. Place their wheels respectively in
   `D:/MARA-build/wheels/kotaemon`, `ktem`, `mara-research-cli`, and `mara-app`.
   Build from the same committed checkout that exported the lock.

3. Download the official bootstrap wheel:

   ```powershell
   python -m pip download --no-deps --only-binary :all: --dest D:/MARA-build/downloads uv==0.11.19
   ```

4. Run the bundle assembler with the complete SHA returned by `git rev-parse HEAD`:

   ```powershell
   python scripts/build_reviewer_bundle.py --dist-root D:/MARA-build/wheels --requirements D:/MARA-build/runtime-requirements.txt --uv-wheel D:/MARA-build/downloads/uv-0.11.19-py3-none-win_amd64.whl --output-dir D:/MARA-build/output --source-commit FULL_SOURCE_SHA --base-main-commit dfcca9987fa4f4d3c5e4da303217c32692032b65
   ```

The assembler checks the official uv wheel SHA-256 and includes its license files.
It replaces only the corresponding locked hashes for prebuilt third-party wheels;
a mismatched version is rejected. The resulting ZIP has an external `.sha256`
sidecar and an internal manifest covering its included files. These checks detect
corruption; the ZIP checksum should be distributed through the trusted release page.

## Acceptance

Extract the final ZIP into a new folder. Run `Install.cmd` without an existing
Python on PATH and confirm that it creates `runtime/installed.json`. Check that
`MARA.cmd --help` and `MARA.cmd app doctor --json` execute inside the bundle's
environment. Start the Web UI with `Start.cmd`, verify HTTP 200 and the served UI,
and inspect `runtime/logs` for exceptions. Re-running installation must preserve
configuration and documents. A failed installation must not leave a success marker.

The supplied text fixture supports a real indexing and question-answering check
after a chat and embedding provider is configured. Record installation/UI checks
separately from actual model-backed QA. Missing API credentials do not establish
answer-quality success, and a mocked provider test is only a protocol/runtime test.
Visual routes and local model backends need their own configuration and validation.

Keep `v0.0.40` as the historical benchmark anchor. A bundle based on current `main`
must not be described as the exact application build that produced those results.
