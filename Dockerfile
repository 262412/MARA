# syntax=docker/dockerfile:1.7@sha256:a57df69d0ea827fb7266491f2813635de6f17269be881f696fbfdf2d83dda33e

FROM ghcr.io/astral-sh/uv:0.11.19@sha256:b46b03ddfcfbf8f547af7e9eaefdf8a39c8cebcba7c98858d3162bd28cf536f6 AS uv-bin
FROM ollama/ollama:0.31.2@sha256:509fdf54e23bd50d87af646cb51c0a7a203d6a83cc4d6695b3b08c5be1c62c0a AS ollama-source

FROM python:3.11.17-slim-bookworm@sha256:0a310eeecf4e1f5a0743f9a6520c90c88d089c903ca5fd283f501e3a805f5f89 AS builder-base
COPY --from=uv-bin /uv /uvx /usr/local/bin/
RUN apt-get update -qqy \
    && apt-get install -y --no-install-recommends \
        build-essential \
        cargo \
        git \
        libmagic-dev \
        libpoppler-dev \
        pkg-config \
    && rm -rf /var/lib/apt/lists/*

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/opt/mara/.venv
WORKDIR /opt/mara
RUN install -d -m 0755 /opt/mara/bin
COPY pyproject.toml uv.lock README.md LICENSE.txt NOTICE ./
COPY docker/pyproject.toml docker/uv.lock ./docker/
COPY libs ./libs
COPY vendor/nltk ./vendor/nltk
COPY scripts/check_nltk_backport.py ./scripts/check_nltk_backport.py
COPY scripts/prepare_container_nltk.py /opt/mara/bin/prepare_container_nltk.py

# Reuse v0.31.2's native libraries and rebuild its Go service with patched modules.
FROM builder-base AS ollama-builder
ARG TARGETARCH
ADD https://go.dev/dl/go1.27.1.linux-${TARGETARCH}.tar.gz /tmp/go.tar.gz
ADD --checksum=sha256:9c334ffe4dda2afce6bc448b0d5505e97a5f067db5141cac988d3edfd920bb6f \
    https://codeload.github.com/ollama/ollama/tar.gz/a6293eb5164214f15e7856268f3adddeae1026e2 /tmp/ollama.tar.gz
RUN case "$TARGETARCH" in \
        amd64) go_sha=63d339f0da5ab53635a56f2490a7984dfe12dfcff22ad749f63edaf590168445 ;; \
        arm64) go_sha=3450b45a3f9ee8568792736a5c5e70a1f2e9b36c35a8f74958c03e51d7d92bec ;; \
        *) exit 1 ;; \
    esac \
    && printf '%s  /tmp/go.tar.gz\n' "$go_sha" | sha256sum --check - \
    && tar -xzf /tmp/go.tar.gz -C /usr/local \
    && mkdir /opt/ollama-src \
    && tar -xzf /tmp/ollama.tar.gz -C /opt/ollama-src --strip-components=1
ENV PATH=/usr/local/go/bin:$PATH \
    GOTOOLCHAIN=local
WORKDIR /opt/ollama-src
COPY docker/ollama/go.mod docker/ollama/go.sum ./
RUN --mount=type=cache,target=/root/.cache/go-build \
    sha256sum go.mod go.sum > /tmp/ollama-locks.sha256 \
    && go mod download \
    && go mod verify \
    && go test -mod=readonly -timeout=3m ./api ./envconfig \
    && CGO_ENABLED=1 go build -mod=readonly -trimpath -buildmode=pie \
        -ldflags="-s -w -X github.com/ollama/ollama/version.Version=0.31.2" \
        -o /bin/ollama . \
    && sha256sum --check /tmp/ollama-locks.sha256 \
    && go version -m /bin/ollama

FROM builder-base AS lite-builder
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --project /opt/mara/docker --frozen --no-dev --no-editable \
    && /opt/mara/.venv/bin/python /opt/mara/scripts/check_nltk_backport.py \
    && NLTK_CACHE="$(echo /opt/mara/.venv/lib/python*/site-packages/llama_index/core/_static/nltk_cache)" \
    && /opt/mara/.venv/bin/python /opt/mara/bin/prepare_container_nltk.py "$NLTK_CACHE" \
    && NLTK_DATA="$NLTK_CACHE" /opt/mara/.venv/bin/python -c \
        "import nltk; nltk.download = lambda *a, **k: (_ for _ in ()).throw(RuntimeError('network download forbidden')); from llama_index.core.readers.base import BaseReader; from llama_index.core.utils import get_tokenizer; assert get_tokenizer()('MARA works offline.')"

FROM builder-base AS full-builder
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --project /opt/mara/docker --frozen --no-dev --no-editable \
    && /opt/mara/.venv/bin/python /opt/mara/scripts/check_nltk_backport.py \
    && NLTK_CACHE="$(echo /opt/mara/.venv/lib/python*/site-packages/llama_index/core/_static/nltk_cache)" \
    && /opt/mara/.venv/bin/python /opt/mara/bin/prepare_container_nltk.py "$NLTK_CACHE" \
    && NLTK_DATA="$NLTK_CACHE" /opt/mara/.venv/bin/python -c \
        "import nltk; nltk.download = lambda *a, **k: (_ for _ in ()).throw(RuntimeError('network download forbidden')); from llama_index.core.readers.base import BaseReader; from llama_index.core.utils import get_tokenizer; assert get_tokenizer()('MARA works offline.')"

FROM python:3.11.17-slim-bookworm@sha256:0a310eeecf4e1f5a0743f9a6520c90c88d089c903ca5fd283f501e3a805f5f89 AS runtime-base
RUN python -m pip uninstall --yes setuptools wheel pip \
    && apt-get update -qqy \
    && apt-get install -y --no-install-recommends \
        libmagic1 \
        libpcre2-8-0=10.42-1+deb12u2 \
        libpoppler-cpp0v5 \
        perl-base=5.36.0-7+deb12u4 \
        poppler-utils \
        tini \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 10001 mara \
    && useradd --uid 10001 --gid 10001 --home-dir /home/mara --no-create-home --shell /usr/sbin/nologin mara \
    && install -d -m 0750 -o 10001 -g 10001 /home/mara /var/lib/mara \
    && install -d -m 0555 -o 0 -g 0 /opt/mara /opt/mara/bin
WORKDIR /var/lib/mara
COPY --chown=0:0 --chmod=0555 scripts/container_entrypoint.py /opt/mara/bin/container-entrypoint
COPY --chown=0:0 --chmod=0444 scripts/container_healthcheck.py /opt/mara/bin/container_healthcheck.py
COPY --chown=0:0 --chmod=0444 scripts/check_nltk_backport.py /opt/mara/bin/check_nltk_backport.py
COPY --chown=0:0 --chmod=0444 vendor/nltk/base-files.json vendor/nltk/backport.json /opt/mara/vendor/nltk/
RUN chmod 0555 /opt/mara/vendor /opt/mara/vendor/nltk \
    && chmod -R a-w /opt/mara

FROM runtime-base AS runtime-full
RUN apt-get update -qqy \
    && apt-get install -y --no-install-recommends \
        ffmpeg \
        libsm6 \
        libxext6 \
        libreoffice \
        tesseract-ocr \
        tesseract-ocr-jpn \
    && rm -rf /var/lib/apt/lists/*

FROM runtime-base AS lite
COPY --from=lite-builder --chown=0:0 /opt/mara/.venv /opt/mara/.venv
RUN chmod -R a-w /opt/mara
ENV HOME=/home/mara \
    KH_APP_DATA_DIR=/var/lib/mara \
    XDG_CONFIG_HOME=/var/lib/mara/config \
    XDG_CACHE_HOME=/var/lib/mara/cache \
    XDG_DATA_HOME=/var/lib/mara/data \
    NLTK_DATA=/opt/mara/.venv/lib/python3.11/site-packages/llama_index/core/_static/nltk_cache \
    GRADIO_SERVER_NAME=0.0.0.0 \
    GRADIO_SERVER_PORT=7860 \
    MARA_AUTH_MODE=password \
    MARA_ADMIN_PASSWORD_FILE=/run/secrets/mara_admin_password \
    MARA_CONTAINER_TARGET=lite
EXPOSE 7860
USER 10001:10001
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD ["/opt/mara/.venv/bin/python", "/opt/mara/bin/container_healthcheck.py"]
ENTRYPOINT ["/usr/bin/tini", "-g", "--", "/opt/mara/bin/container-entrypoint"]

FROM runtime-full AS full
COPY --from=full-builder --chown=0:0 /opt/mara/.venv /opt/mara/.venv
RUN chmod -R a-w /opt/mara
ENV HOME=/home/mara \
    KH_APP_DATA_DIR=/var/lib/mara \
    XDG_CONFIG_HOME=/var/lib/mara/config \
    XDG_CACHE_HOME=/var/lib/mara/cache \
    XDG_DATA_HOME=/var/lib/mara/data \
    NLTK_DATA=/opt/mara/.venv/lib/python3.11/site-packages/llama_index/core/_static/nltk_cache \
    GRADIO_SERVER_NAME=0.0.0.0 \
    GRADIO_SERVER_PORT=7860 \
    MARA_AUTH_MODE=password \
    MARA_ADMIN_PASSWORD_FILE=/run/secrets/mara_admin_password \
    MARA_CONTAINER_TARGET=full
EXPOSE 7860
USER 10001:10001
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD ["/opt/mara/.venv/bin/python", "/opt/mara/bin/container_healthcheck.py"]
ENTRYPOINT ["/usr/bin/tini", "-g", "--", "/opt/mara/bin/container-entrypoint"]

FROM runtime-full AS ollama
COPY --from=full-builder --chown=0:0 /opt/mara/.venv /opt/mara/.venv
COPY --from=ollama-builder --chown=0:0 /bin/ollama /usr/bin/ollama
COPY --from=ollama-source --chown=0:0 /usr/lib/ollama /usr/lib/ollama
RUN install -d -m 0750 -o 10001 -g 10001 /var/lib/mara/ollama \
    && chmod -R a-w /opt/mara
ENV HOME=/home/mara \
    KH_APP_DATA_DIR=/var/lib/mara \
    XDG_CONFIG_HOME=/var/lib/mara/config \
    XDG_CACHE_HOME=/var/lib/mara/cache \
    XDG_DATA_HOME=/var/lib/mara/data \
    NLTK_DATA=/opt/mara/.venv/lib/python3.11/site-packages/llama_index/core/_static/nltk_cache \
    GRADIO_SERVER_NAME=0.0.0.0 \
    GRADIO_SERVER_PORT=7860 \
    MARA_AUTH_MODE=password \
    MARA_ADMIN_PASSWORD_FILE=/run/secrets/mara_admin_password \
    MARA_CONTAINER_TARGET=ollama \
    OLLAMA_HOST=127.0.0.1:11434 \
    OLLAMA_MODELS=/var/lib/mara/ollama
EXPOSE 7860
USER 10001:10001
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD ["/opt/mara/.venv/bin/python", "/opt/mara/bin/container_healthcheck.py"]
ENTRYPOINT ["/usr/bin/tini", "-g", "--", "/opt/mara/bin/container-entrypoint"]
