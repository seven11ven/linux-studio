#!/usr/bin/env bash
# Downloads the Studio Browser's extensions that Debian doesn't package (NoScript, ClearURLs, Bitwarden)
# from Mozilla's add-on site, at exact pinned versions, and refuses any file whose SHA-256 doesn't match.
# uBlock Origin comes from Debian inside the runtime (scripts/build-runtime.sh), so it isn't fetched here.
#
# Every file is also signed by Mozilla; the browser checks that signature again when it loads the extension.
# To update one: get the new version's file URL and sha256 from
#   https://addons.mozilla.org/api/v5/addons/addon/<slug>/   (current_version.file.url and .hash)
# check its code and licence again (guidelines/Implementation.md), then change its line below.
#
# Usage: scripts/fetch-browser-extensions.sh
# Output: build-cache/browser-extensions/<extension id>.xpi   (ignored by git), plus SHA256SUMS
# Needs: curl, sha256sum
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DEST="$ROOT/build-cache/browser-extensions"

# id | file URL | sha256 | name, version, licence
EXTENSIONS=(
  "{73a6fe31-595d-460b-a920-fcc0f8843232}|https://addons.mozilla.org/firefox/downloads/file/5293695/noscript-13.6.39.xpi|15ca1a362027eaabe60940d3cac7f371dae1587fe4a30e3c7e1c01ae9e2f073e|NoScript 13.6.39, GPL-2.0"
  "{74145f27-f039-47ce-a470-a662b129930a}|https://addons.mozilla.org/firefox/downloads/file/5286652/clearurls-1.28.0.xpi|693601ba1f21c6940374f76acc2dd4bd3201869b0fe10ab1b927b593ee2508d1|ClearURLs 1.28.0, LGPL-3.0"
  "{446900e4-71c2-419f-a6a7-df9c091e268b}|https://addons.mozilla.org/firefox/downloads/file/5278513/bitwarden_password_manager-2026.11.0.xpi|607d6433d9de151a4c51135ad9e70882460d0e0493a9b585f15a9848d5f10b97|Bitwarden 2026.11.0, Bitwarden License (not open source; PM-approved exception)"
)

for tool in curl sha256sum; do command -v "$tool" >/dev/null || { echo "Missing: $tool" >&2; exit 1; }; done

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
: > "$TMP/SHA256SUMS"

for entry in "${EXTENSIONS[@]}"; do
  IFS='|' read -r id url sum label <<<"$entry"
  [[ "$id" =~ ^\{[0-9a-f-]{36}\}$ && "$url" == https://addons.mozilla.org/* && "$sum" =~ ^[0-9a-f]{64}$ ]] \
    || { echo "Bad entry for $label" >&2; exit 1; }
  curl --fail --silent --show-error --location --proto '=https' --tlsv1.2 --max-filesize 64000000 \
       -o "$TMP/$id.xpi" "$url"
  if ! echo "$sum  $TMP/$id.xpi" | sha256sum --check --strict --status; then
    echo "Checksum FAILED for $label. Nothing was installed." >&2; exit 1
  fi
  echo "$sum  $id.xpi" >> "$TMP/SHA256SUMS"
  echo "Verified: $label"
done

mkdir -p "$DEST"
chmod 644 "$TMP"/*.xpi "$TMP/SHA256SUMS"
mv -f "$TMP"/*.xpi "$TMP/SHA256SUMS" "$DEST/"
echo "Studio Browser extensions are in $DEST"
