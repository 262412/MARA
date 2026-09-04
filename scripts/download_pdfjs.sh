#!/usr/bin/env bash

set -euo pipefail

# Maintainer-only refresh utility. Normal installation and startup use the
# verified archive already packaged in ktem and never call this script.
readonly PDFJS_VERSION="6.1.200"
readonly PDFJS_ARCHIVE="pdfjs-${PDFJS_VERSION}-dist.zip"
readonly PDFJS_SHA256="9e1584d768ed099aa4be27ea423f89a038c2005f1ee417ea4f35ba4591ec1846"
readonly PDFJS_URL="https://github.com/mozilla/pdf.js/releases/download/v6.1.200/pdfjs-6.1.200-dist.zip"

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
destination="${1:-${repo_root}/libs/ktem/ktem/assets/vendor/pdfjs/${PDFJS_ARCHIVE}}"
mkdir -p "$(dirname "${destination}")"
temporary_archive="$(mktemp "${destination}.XXXXXX")"
trap 'rm -f "${temporary_archive}"' EXIT

curl --fail --location --show-error --silent \
    "${PDFJS_URL}" \
    --output "${temporary_archive}"
printf '%s  %s\n' "${PDFJS_SHA256}" "${temporary_archive}" | sha256sum --check --status
mv "${temporary_archive}" "${destination}"
trap - EXIT

printf 'Verified PDF.js %s at %s\n' "${PDFJS_VERSION}" "${destination}"
