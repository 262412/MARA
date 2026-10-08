# Running MARA with Docker

Docker is an optional deployment of the Web/CLI runtime. It is separate from the
Electron desktop application.

## Build

From the repository root:

```shell
docker build --target full -t mara:full .
```

| Target   | Included capabilities                                                         |
| -------- | ----------------------------------------------------------------------------- |
| `lite`   | Locked baseline Web/DocQA runtime                                             |
| `full`   | Adds operating-system tools including LibreOffice, Tesseract, and FFmpeg      |
| `ollama` | Adds a pinned Ollama runtime to `full`; the image build does not pull a model |

The [Dockerfile](../../Dockerfile) uses the container lock under
[Docker dependencies](../../docker/pyproject.toml).
These are Linux containers.

## Start with persistent data and password authentication

The image runs as UID/GID `10001:10001`, binds inside the container on port 7860,
and uses `/var/lib/mara` as its writable application-data root. Use a named
volume to retain documents, indexes, and settings.

The following example is for **Bash on Linux/macOS or WSL**. It is not a
PowerShell script. Choose an administrator password satisfying the current
password policy.

```bash
docker volume create mara-data

MARA_SECRET_DIR="$(mktemp -d "${XDG_RUNTIME_DIR:-/tmp}/mara-secret.XXXXXX")"
MARA_SECRET_FILE="$MARA_SECRET_DIR/admin-password"
trap 'rm -f "$MARA_SECRET_FILE"; rmdir "$MARA_SECRET_DIR"' EXIT
install -m 0600 /dev/null "$MARA_SECRET_FILE"
read -rsp 'MARA admin password: ' MARA_ADMIN_PASSWORD
printf '\n'
printf '%s\n' "$MARA_ADMIN_PASSWORD" >"$MARA_SECRET_FILE"
unset MARA_ADMIN_PASSWORD
chmod 0444 "$MARA_SECRET_FILE"

docker run --rm -it \
  --name mara-web \
  -e MARA_AUTH_MODE=password \
  --mount type=bind,src="$MARA_SECRET_FILE",dst=/run/secrets/mara_admin_password,readonly \
  --mount type=volume,src=mara-data,dst=/var/lib/mara \
  -p 127.0.0.1:7860:7860 \
  mara:full
```

Open [http://127.0.0.1:7860](http://127.0.0.1:7860) and sign in with the
administrator account (`admin` by default) and the supplied password. Configure
chat and embedding providers in resources, then import a small document.
Stopping/removing the container does not remove the named volume.

The password file must be readable by container UID 10001. The example uses a
temporary directory outside the build context and a read-only file mount.
On shared hosts, prefer a Docker/Kubernetes secret provisioned for UID 10001
with mode `0440`. Container and host file-sharing permissions may require
different provisioning on Docker Desktop.

Model configuration can also be supplied through an external environment file
with `--env-file`. Use only the model/provider settings you need; keep the
password-file authentication settings from the launch command. Do not copy
credentials into the image. Once provider entries exist in the database,
update their saved settings through resources.

For intentional network deployment, configure access controls and TLS at the
deployment boundary before changing the host port binding. SSO deployments use
`MARA_AUTH_MODE=sso` and their configured Google/Keycloak environment instead of
the password-file flow.

## Inspect and stop

From another terminal:

```shell
docker logs mara-web
docker exec mara-web /opt/mara/.venv/bin/MARA app doctor
docker stop mara-web
```

Back up the volume with the application stopped. The source checkout's
`ktem_app_data/` and a container's named volume are separate unless explicitly
configured otherwise.

## Dependency boundaries

The `full` target adds system document tools; it does not inject every optional
Python reader after lock resolution. Legacy Microsoft GraphRAG and Adobe PDF
Services have dependency conflicts with the locked runtime and are not
preinstalled. The local lightweight graph route and built-in PDF reader remain
available.

The Ollama target includes the runtime but requires an explicitly selected model
to be pulled after deployment. Its persistent model directory is
`/var/lib/mara/ollama`. Check the backend's available memory and model readiness
before expecting local inference to work.

Build and publication remain subject to the repository's existing security,
supply-chain, and release gates. These instructions describe the checked-in
configuration; this README update did not build or test a new container image.
