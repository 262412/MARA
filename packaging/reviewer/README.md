# MARA reviewer package for Windows x64

1. Extract the entire ZIP to a writable folder with at least 8 GB free space.
   Keep that folder in place after installation.
2. Double-click `Install.cmd`. It installs Python 3.10.19 into `runtime/python`,
   creates an independent environment, and installs the pinned dependencies and
   the included MARA wheels. First installation requires internet access to
   GitHub and PyPI. You do not need an existing Python, Git, Visual Studio, or CUDA.
3. After installation succeeds, double-click `Start.cmd`. The Web UI opens at
   <http://127.0.0.1:7860>. Keep the terminal open while using MARA.
4. Configure your generation and embedding providers in the Web UI. A chat API
   key alone does not supply an embedding model. Use credentials and models you
   have access to; this bundle includes no keys or model weights. API usage may
   be billed by your provider. External APIs receive the data required for their
   configured operation; select local endpoints for a local model deployment.
5. Upload `samples/reviewer-note.txt`, index it, select it as the question source,
   and ask: **What is the project review marker?** The document states
   **ORCHID-7429**. Inspect the answer citation and the route/retrieval/verification
   status. Also ask **Who is the project manager?** and inspect whether the
   response acknowledges the missing evidence. These are review prompts, not
   precomputed answers or claims that every model will answer correctly.

The default package includes the MARA Web UI and CLI runtime. It does not install
the optional in-process `llama-cpp-python` backend. Visual, graph, and other
optional routes still require their documented backend configuration. This
installation package does not claim to reproduce the paper's v0.0.40 benchmark
environment or model outputs. `manifest.json` records its exact source commit,
base `main` commit, tool versions, and included-file checksums.

## Commands and data

- `MARA.cmd --help` exposes the usual MARA commands in this package's environment.
- `MARA.cmd app doctor --json` reports application and provider readiness.
- `MARA.cmd docqa --help` shows document indexing and query commands.
- `Start.cmd -Port 7861` selects a different local port.
- `Start.cmd -NoBrowser` starts the server without opening a browser.
- Close the server terminal or press Ctrl+C to stop it.

Configuration, credentials you enter, document indices, and uploads stay under
`runtime/app`. The isolated configuration file is
`runtime/app/config/flowsettings.py`; the environment template is in the same
directory. Existing MARA installations and their databases are not migrated or
changed. Existing settings are preserved when `Install.cmd` is run again.
If you move this folder after installation, create a fresh extraction and
installation at the destination; a Python virtual environment is not portable.

Logs are saved under `runtime/logs`. If installation fails, keep the log and
rerun `Install.cmd` after resolving connectivity or disk-space problems. A failed
installation does not write a new success marker. The installer verifies file
hashes and stops on failed commands. It never disables TLS verification and does
not alter system PATH, the Windows registry, or persistent execution policy.
The CMD launchers permit their own PowerShell script for that process only.
Help pages are read from bundled files; remote help and release-note downloads are
disabled for this package so they cannot hold up local UI startup.

Distribution license: Apache-2.0; see `LICENSE.txt` and `NOTICE`. The bundled uv
executable's license files are in `tools/licenses`. Third-party Python packages
retain their licenses in their installed distribution metadata.
