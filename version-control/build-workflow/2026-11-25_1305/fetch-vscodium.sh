#!/usr/bin/env bash
# Downloads the VSCodium build made by .github/workflows/build-vscodium.yml,
# checks its SHA256 checksum, and unpacks it into build-cache/vscodium/<version>/.
#
# Usage: scripts/fetch-vscodium.sh <workflow-run-id>
# Needs: gh (GitHub CLI, logged in), sha256sum, tar, jq
set -euo pipefail

RUN_ID="${1:-}"
[[ "$RUN_ID" =~ ^[0-9]+$ ]] || { echo "Usage: $0 <workflow-run-id>" >&2; exit 1; }

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

gh run download "$RUN_ID" --repo seven11ven/linux-studio --name vscodium-linux-x64 --dir "$TMP"

(cd "$TMP" && sha256sum --check --strict SHA256SUMS) || { echo "Checksum FAILED. Nothing was installed." >&2; exit 1; }

TAG="$(jq -r .vscode_tag "$TMP/build-info.json")"
[[ "$TAG" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || { echo "Bad version in build-info.json" >&2; exit 1; }

DEST="$ROOT/build-cache/vscodium/$TAG"
if [[ -e "$DEST" ]]; then echo "$DEST already exists. Remove it first if you want to replace it." >&2; exit 1; fi
mkdir -p "$DEST/app"
tar -xzf "$TMP"/vscodium-*.tar.gz -C "$DEST/app" --no-same-owner
cp "$TMP/build-info.json" "$TMP/SHA256SUMS" "$DEST/"

echo "VSCodium $TAG verified and unpacked to $DEST"
echo "Record it with: cp '$DEST/build-info.json' '$ROOT/build/vscodium-version.json'"
