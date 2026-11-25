#!/usr/bin/env bash
# Replaces every Microsoft telemetry collector address in the VS Code source tree
# (including installed node_modules) with 0.0.0.0, an address that goes nowhere.
# Run it AFTER installing packages and BEFORE building, so the build packs the cleaned
# files and computes its own file fingerprints (checksums).
#
# Same idea as VSCodium's undo_telemetry.sh, extended to Application Insights addresses.
# Telemetry keys inside extensions are left in place: they are compiled into the extension
# code and removing them could crash those extensions. With no address to send to, they are inert.
#
# Usage:
#   scripts/neutralise-telemetry.sh <vscode-source-folder>          clean the source
#   scripts/neutralise-telemetry.sh --check <built-app-folder>      verify a finished build (exit 1 if any remain)
# Needs: grep, sed
set -euo pipefail

HOSTS='[a-z0-9.-]+\.data\.microsoft\.com|dc(-int)?\.services\.visualstudio\.com|[a-z0-9.-]+\.applicationinsights\.(io|azure\.com)'

if [[ "${1:-}" == "--check" ]]; then
  DIR="${2:-}"; [[ -d "$DIR" ]] || { echo "Usage: $0 --check <folder>" >&2; exit 1; }
  # -a: also search inside binary archives such as node_modules.asar
  if grep -rlaE "//($HOSTS)" "$DIR"; then echo "ERROR: telemetry addresses found (listed above)" >&2; exit 1; fi
  echo "Check passed: no telemetry addresses in $DIR"
  exit 0
fi

DIR="${1:-}"
[[ -f "$DIR/product.json" ]] || { echo "Usage: $0 <vscode source folder containing product.json>" >&2; exit 1; }

# -I: text files only, so compiled binaries are never edited.
mapfile -t FILES < <(grep -rlIE --exclude-dir=.git "//($HOSTS)" "$DIR" || true)
echo "Files with telemetry addresses: ${#FILES[@]}"
for f in "${FILES[@]}"; do
  sed -i -E "s#//($HOSTS)#//0.0.0.0#g" "$f"
  echo "  neutralised: ${f#"$DIR"/}"
done

if grep -rqIE --exclude-dir=.git "//($HOSTS)" "$DIR"; then
  echo "ERROR: telemetry addresses still present" >&2
  exit 1
fi
echo "Done: no telemetry addresses remain in the source."
