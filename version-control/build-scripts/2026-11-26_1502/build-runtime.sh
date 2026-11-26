#!/usr/bin/env bash
# Builds Linux Studio's private mini-Linux ("runtime"): a small Debian 13 (trixie) system
# containing the tools the editor and its terminal need. The sandbox uses it as its "/",
# so nothing from your real system's /usr or /etc is visible inside Linux Studio.
#
# Usage: scripts/build-runtime.sh
# Output: build-cache/runtime/<YYYY-MM-DD>/rootfs/   (ignored by git, ~1 GB)
#         build/runtime-manifest.txt                  (tracked: every package and version)
# Needs (no root): mmdebstrap, uidmap (newuidmap/newgidmap), debian-archive-keyring, an /etc/subuid entry for your user, tar
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SUITE=trixie
MIRROR=http://deb.debian.org/debian
DEST="$ROOT/build-cache/runtime/$(date -u +%Y-%m-%d)"

PACKAGES=(
  # shell and basic tools
  bash coreutils procps less git ca-certificates curl iproute2 gpgv xz-utils bubblewrap
  # private X11 display (Phase 6): keeps the editor filling the Linux Studio window; xdpyinfo for --self-test
  matchbox-window-manager x11-utils
  # languages and build tools
  python3 python3-pip python3-venv nodejs npm gcc g++ clang make cmake
  # fonts
  fonts-dejavu-core
  # libraries the editor (Electron) needs; confirmed with ldd after building
  libgtk-3-0t64 libnss3 libasound2t64 libgbm1 libxkbfile1 libsecret-1-0 libxss1 libdrm2
  libxshmfence1 libatk-bridge2.0-0t64 libcups2t64 libx11-xcb1 libxcomposite1 libxdamage1
  libxrandr2 libxkbcommon0 libdbus-1-3 libxtst6
)

for tool in mmdebstrap newuidmap tar; do
  command -v "$tool" >/dev/null || { echo "Missing: $tool (install: sudo apt-get install -y mmdebstrap uidmap)" >&2; exit 1; }
done
# Debian's signing keys are needed so every package is verified as genuine. Never skip this check.
KEYRING=/usr/share/keyrings/debian-archive-keyring.gpg
[[ -f "$KEYRING" ]] || { echo "Missing Debian signing keys ($KEYRING). Install: sudo apt-get install -y debian-archive-keyring" >&2; exit 1; }
if [[ -e "$DEST" ]]; then echo "$DEST already exists. Move it to version-control/runtime/ first." >&2; exit 1; fi

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
IFS=,; INCLUDE="${PACKAGES[*]}"; unset IFS

mmdebstrap --mode=unshare --variant=minbase --include="$INCLUDE" --keyring="$KEYRING" \
  --customize-hook="copy-in '$ROOT/src/runtime/overlay/etc/linux-studio' /etc" \
  --customize-hook='echo ". /etc/linux-studio/bashrc" >> "$1/etc/bash.bashrc"' \
  --customize-hook=': > "$1/etc/machine-id"; : > "$1/etc/hostname"; rm -f "$1"/etc/*-' \
  --customize-hook='mkdir -p "$1/home/user" "$1/project-folder" "$1/app" "$1/run/user" "$1/toolchains"' \
  --customize-hook='chroot "$1" dpkg-query -W -f="\${Package} \${Version}\n" > "$1/etc/linux-studio/manifest.txt"' \
  --customize-hook='rm -rf "$1"/var/cache/apt/archives/*.deb "$1"/var/lib/apt/lists/*' \
  "$SUITE" "$TMP/rootfs.tar" "$MIRROR"

mkdir -p "$DEST/rootfs"
# Device files can't be created without root and aren't needed (the sandbox makes its own /dev).
tar -xf "$TMP/rootfs.tar" -C "$DEST/rootfs" --no-same-owner --exclude='./dev/*'

mkdir -p "$ROOT/build"
{ echo "# Linux Studio runtime: Debian $SUITE, built $(date -u +%Y-%m-%dT%H:%MZ)"; cat "$DEST/rootfs/etc/linux-studio/manifest.txt"; } > "$ROOT/build/runtime-manifest.txt"
echo "Runtime built: $DEST/rootfs ($(du -sh "$DEST/rootfs" | cut -f1)); manifest: build/runtime-manifest.txt"
