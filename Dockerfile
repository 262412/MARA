# Lite version
FROM python:3.10-slim AS lite

# Common dependencies
RUN apt-get update -qqy && \
    apt-get install -y --no-install-recommends \
        ssh \
        git \
        gcc \
        g++ \
        poppler-utils \
        libpoppler-dev \
        unzip \
        curl \
        cargo \
        && \
    apt-get autoremove && apt-get clean && rm -rf /var/lib/apt/lists/*

# Setup args
ARG TARGETPLATFORM
ARG TARGETARCH

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONIOENCODING=UTF-8
ENV TARGETARCH=${TARGETARCH}

# Create working directory
WORKDIR /app

# Install uv dependencies
RUN pip install --no-cache-dir "uv"

# Copy only the application inputs required by the image
COPY pyproject.toml uv.lock README.md LICENSE.txt NOTICE /app/
COPY libs /app/libs
COPY docs /app/docs
COPY app.py flowsettings.py sso_app.py sso_app_demo.py settings.yaml.example /app/
COPY .env.example /app/.env.example
COPY launch.sh /app/launch.sh

# Install pip packages
RUN --mount=type=ssh  \
    --mount=type=cache,target=/root/.cache/uv  \
    uv sync --frozen --no-cache \
    && uv pip install --python .venv "pdfservices-sdk@git+https://github.com/niallcm/pdfservices-python-sdk.git@bump-and-unfreeze-requirements"

ENV KH_APP_DATA_DIR="/app/ktem_app_data"
RUN .venv/bin/python -m ktem.assets.pdfjs_assets

RUN --mount=type=ssh  \
    --mount=type=cache,target=/root/.cache/uv  \
    if [ "$TARGETARCH" = "amd64" ]; then uv pip install --python .venv "graphrag<=0.3.6" future; fi

ENTRYPOINT ["sh", "/app/launch.sh"]

# Full version
FROM lite AS full

# Additional dependencies for full version
RUN apt-get update -qqy && \
    apt-get install -y --no-install-recommends \
        tesseract-ocr \
        tesseract-ocr-jpn \
        libsm6 \
        libxext6 \
        libreoffice \
        ffmpeg \
        libmagic-dev \
        && \
    apt-get autoremove && apt-get clean && rm -rf /var/lib/apt/lists/*

# Install torch and torchvision for unstructured
RUN --mount=type=ssh  \
    --mount=type=cache,target=/root/.cache/uv  \
    uv pip install --python .venv torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu

# Install additional pip packages
RUN --mount=type=ssh  \
    --mount=type=cache,target=/root/.cache/uv  \
    uv pip install --python .venv "libs/kotaemon[adv]" \
    && uv pip install --python .venv unstructured[all-docs]

# Install legacy GraphRAG dependencies only when explicitly requested
ARG INSTALL_LEGACY_GRAPHRAG=false
RUN --mount=type=ssh  \
    --mount=type=cache,target=/root/.cache/uv  \
    if [ "$INSTALL_LEGACY_GRAPHRAG" = "true" ]; then \
        uv pip install --python .venv aioboto3 nano-vectordb ollama xxhash "lightrag-hku<=1.3.0"; \
    fi

RUN --mount=type=ssh  \
    --mount=type=cache,target=/root/.cache/uv  \
    uv pip install --python .venv "docling<=2.5.2"

# Download NLTK data from LlamaIndex
RUN /app/.venv/bin/python -c "from llama_index.core.readers.base import BaseReader"

ENTRYPOINT ["sh", "/app/launch.sh"]

# Ollama-bundled version
FROM full AS ollama

# Install ollama
RUN curl -fsSL https://ollama.com/install.sh | sh

# RUN nohup bash -c "ollama serve &" && sleep 4 && ollama pull qwen2.5:7b
RUN nohup bash -c "ollama serve &" && sleep 4 && ollama pull nomic-embed-text

ENTRYPOINT ["sh", "/app/launch.sh"]
