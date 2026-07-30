from __future__ import annotations

APPROVED_ACTIONS = {
    "actions/attest-build-provenance@96278af6caaf10aea03fd8d33a09a777ca52d62f": "v3.2.0",
    "actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683": "v4.2.2",
    "actions/checkout@df4cb1c069e1874edd31b4311f1884172cec0e10": "v6.0.3",
    "actions/download-artifact@d3f86a106a0bac45b974a628896c90dbdf5c8093": "v4.3.0",
    "actions/setup-python@a26af69be951a213d495a4c3e4e4022e16d87065": "v5.6.0",
    "actions/setup-node@49933ea5288caeca8642d1e84afbd3f7d6820020": "v4.4.0",
    "actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02": "v4.6.2",
    "amannn/action-semantic-pull-request@0723387faaf9b38adef4775cd42cfd5155ed6017": "v5.5.3",
    "anothrNick/github-tag-action@4ed44965e0db8dab2b466a16da04aec3cc312fd8": "1.75.0",
    "aquasecurity/trivy-action@ed142fd0673e97e23eac54620cfb913e5ce36c25": "v0.36.0",
    "astral-sh/setup-uv@b75a909f75acd358c2196fb9a5f1299a9a8868a4": "v6.7.0",
    "buildingcash/json-to-markdown-table-action@b442169239ef35f1dc4e5c8c3d47686c081a7e65": "v1.1.0",
    "docker/build-push-action@10e90e3645eae34f1e60eeb005ba3a3d33f178e8": "v6.19.2",
    "docker/login-action@c94ce9fb468520275223c153574b00df6fe4bcc9": "v3.7.0",
    "docker/metadata-action@c299e40c65443455700f0fdfc63efafe5b349051": "v5.10.0",
    "docker/setup-buildx-action@8d2750c68a42422c14e847fe6c8ac0403b4cbd6f": "v3.12.0",
    "docker/setup-qemu-action@c7c53464625b32c7a7e944ae62b3e17d2b600130": "v3.7.0",
    "jlumbroso/free-disk-space@54081f138730dfa15788a46383842cd2f914a1be": "v1.3.1",
    "marocchino/sticky-pull-request-comment@773744901bac0e8cbb5a0dc842800d45e9b2b405": "v2.9.4",
    "softprops/action-gh-release@3bb12739c298aeb8a4eeaf626c5b8d85266b0e65": "v2.6.2",
    "wagoid/commitlint-github-action@b948419dd99f3fd78a6548d48f94e3df7f6bf3ed": "v6.2.1",
}

DEFAULT_GITHUB_RUNNER = "ubuntu-24.04"
APPROVED_WORKFLOW_JOB_RUNNERS = {
    (".github/workflows/desktop-gate2.yaml", "package-linux-22"): "ubuntu-22.04",
    (".github/workflows/desktop-gate2.yaml", "package-windows"): "windows-2022",
}

APPROVED_EXTERNAL_IMAGES = {
    "ghcr.io/astral-sh/uv:0.11.19@sha256:b46b03ddfcfbf8f547af7e9eaefdf8a39c8cebcba7c98858d3162bd28cf536f6",
    "ollama/ollama:0.31.2@sha256:509fdf54e23bd50d87af646cb51c0a7a203d6a83cc4d6695b3b08c5be1c62c0a",
    "python:3.10.20-slim-bookworm@sha256:ff7161e2b8e2a56fc6a62a6099ff8feb72f1a6dbae9860cdcb9a6c65cf4c6be9",
}

APPROVED_PRECOMMIT_REVISIONS = {
    "https://github.com/ambv/black": "ae2c0758c9e61a385df9700dc9c231bf54887041",
    "https://github.com/codespell-project/codespell": "ec0f41b9573937aebab66e3ca5b00d00a7b339fa",
    "https://github.com/myint/autoflake": "d43d8a770c0f9ef2f68b368670ab882f6ca6ea03",
    "https://github.com/pre-commit/mirrors-mypy": "4daa14b20c0f48f472528c2b5f5bca28a18a7ce0",
    "https://github.com/pre-commit/mirrors-prettier": "50c5478ed9e10bf360335449280cf2a67f4edb7a",
    "https://github.com/pre-commit/pre-commit-hooks": "3298ddab3c13dd77d6ce1fc0baf97691430d84b0",
    "https://github.com/pycqa/flake8": "82b698e09996cdde5d473e234681d8380810d7a2",
    "https://github.com/pycqa/isort": "e44834b7b294701f596c9118d6c370f86671a50d",
}

DOCKERFILE_FRONTEND = (
    "# syntax=docker/dockerfile:1.7@"
    "sha256:a57df69d0ea827fb7266491f2813635de6f17269be881f696fbfdf2d83dda33e"
)
BUILDX_VERSION = "v0.34.1"
BUILDKIT_IMAGE = (
    "moby/buildkit:v0.30.0@"
    "sha256:0168606be2315b7c807a03b3d8aa79beefdb31c98740cebdffdfeebf31190c9f"
)
GITLEAKS_IMAGE = (
    "ghcr.io/gitleaks/gitleaks:v8.24.3@"
    "sha256:e1b35e12a8c6fa8901f060459cfb6b2fc4c484d3afbe3b029733a3bbfab07055"
)
GITLEAKS_IGNORE_FINGERPRINTS = (
    "d7eee97a8fe4bdb5c8723cd19ad405e9b230bf62:libs/ktem/ktem_tests/test_sso_factory.py:generic-api-key:144",
    "c6dd01e8203aacdecd01541cac8429c596fe889a:.gitsecret/paths/mapping.cfg:generic-api-key:1",
    "5241edbc4696386af3c3bacfff648a7ee80caed7:.gitsecret/paths/mapping.cfg:generic-api-key:1",
    "026df48b2c2fac399bdfd334bb05a3a588664cda:mara-stream-debug.jsonl:generic-api-key:1",
    "026df48b2c2fac399bdfd334bb05a3a588664cda:mara-stream-debug.jsonl:generic-api-key:2",
    "026df48b2c2fac399bdfd334bb05a3a588664cda:mara-stream-debug.jsonl:generic-api-key:3",
    "026df48b2c2fac399bdfd334bb05a3a588664cda:mara-stream-debug.jsonl:generic-api-key:5",
    "026df48b2c2fac399bdfd334bb05a3a588664cda:mara-stream-debug.jsonl:generic-api-key:19714",
    "aab982ddc4ab882155fcdac89cc3de480d184069:knowledgehub/contribs/promptui/tunnel.py:mara-promptui-frp-token:100",
)
SETUP_UV_ACTION = "astral-sh/setup-uv@b75a909f75acd358c2196fb9a5f1299a9a8868a4"
SETUP_UV_VERSION = "0.11.19"
SETUP_UV_CHECKSUM = "7035608168e106375b36d0c818d537a889c51a8625fe7f8f7cad5e62b947c368"
