#!/usr/bin/env bash
# Downloads the Linux Studio editor build made by .github/workflows/build-editor.yml,
# checks its SHA256 checksum, and unpacks it into build-cache/editor/<version>/.
#
# Usage: scripts/fetch-editor.sh <workflow-run-id>
# Needs: gh (GitHub CLI, logged in), sha256sum, tar, jq
set -euo pipefail

RUN_ID="${1:-}"
[[ "$RUN_ID" =~ ^[0-9]+$ ]] || { echo "Usage: $0 <workflow-run-id>" >&2; exit 1; }

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

gh run download "$RUN_ID" --repo seven11ven/linux-studio --name linux-studio-editor-linux-x64 --dir "$TMP"

(cd "$TMP" && sha256sum --check --strict SHA256SUMS) || { echo "Checksum FAILED. Nothing was installed." >&2; exit 1; }

TAG="$(jq -r .vscode_tag "$TMP/build-info.json")"
[[ "$TAG" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || { echo "Bad version in build-info.json" >&2; exit 1; }

DEST="$ROOT/build-cache/editor/$TAG"
if [[ -e "$DEST" ]]; then echo "$DEST already exists. Remove it first if you want to replace it." >&2; exit 1; fi
mkdir -p "$DEST/app"
tar -xzf "$TMP"/linux-studio-editor-*.tar.gz -C "$DEST/app" --no-same-owner
cp "$TMP/build-info.json" "$TMP/SHA256SUMS" "$DEST/"

echo "Linux Studio editor $TAG verified and unpacked to $DEST"
echo "Record it with: cp '$DEST/build-info.json' '$ROOT/build/editor-version.json'"
