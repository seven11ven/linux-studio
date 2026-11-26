#!/usr/bin/env bash
# Builds the Linux Studio .deb package (Debian / Ubuntu, amd64).
#
# Usage: scripts/build-deb.sh --type dev|release --version 0.1.0~dev1 [--revision 1]
# Needs: dpkg-deb, fakeroot not required (uses --root-owner-group), the verified editor build in
#        build-cache/editor/<tag>/app (scripts/fetch-editor.sh) and the runtime in build-cache/runtime/<date>/rootfs.
# Output: project-builds/<dev|release>-builds/Linux-Studio-debian-amd64-<version>/linux-studio_<version>-<rev>_amd64.deb
#         project-builds/logs/<build folder>.md   (build summary)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TYPE=""; VERSION=""; REVISION=1
while (( $# )); do
  case "$1" in
    --type) TYPE="${2:-}"; shift ;;
    --version) VERSION="${2:-}"; shift ;;
    --revision) REVISION="${2:-}"; shift ;;
    *) echo "Unknown option: $1" >&2; exit 2 ;;
  esac
  shift
done
[[ "$TYPE" == dev || "$TYPE" == release ]] || { echo "Choose --type dev or --type release" >&2; exit 2; }
[[ "$VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+(~[a-z]+[0-9]+)?$ ]] || { echo "Version must look like 0.1.0 or 0.1.0~dev1" >&2; exit 2; }
[[ "$REVISION" =~ ^[1-9][0-9]*$ ]] || { echo "Revision must be a positive number" >&2; exit 2; }
if [[ "$TYPE" == release && "$VERSION" == *~* ]]; then echo "Release builds can't have a ~ pre-release version" >&2; exit 2; fi

PKG=linux-studio
APPID=io.github.seven11ven.linuxstudio
FULLVER="$VERSION-$REVISION"
EDITOR_TAG="$(jq -r .vscode_tag "$ROOT/build/editor-version.json")"
EDITOR="$ROOT/build-cache/editor/$EDITOR_TAG/app"
RUNTIME="$(ls -d "$ROOT"/build-cache/runtime/*/rootfs 2>/dev/null | sort | tail -1)"
[[ -x "$EDITOR/linux-studio-editor" ]] || { echo "Editor build missing at $EDITOR (run scripts/fetch-editor.sh)" >&2; exit 1; }
[[ -n "$RUNTIME" && -x "$RUNTIME/usr/bin/bash" ]] || { echo "Runtime missing (run scripts/build-runtime.sh)" >&2; exit 1; }
"$ROOT/scripts/neutralise-telemetry.sh" --check "$EDITOR" >/dev/null || { echo "Editor build failed the telemetry check" >&2; exit 1; }

NAME="Linux-Studio-debian-amd64-$VERSION"
OUTDIR="$ROOT/project-builds/$TYPE-builds/$NAME"
DEB="$OUTDIR/${PKG}_${FULLVER}_amd64.deb"
[[ ! -e "$DEB" ]] || { echo "$DEB already exists. Old builds are never overwritten; use a new --revision." >&2; exit 1; }

STAGE="$(mktemp -d)"
trap 'chmod -R u+w "$STAGE" 2>/dev/null; rm -rf "$STAGE"' EXIT
P="$STAGE/pkg"
OPT="$P/opt/linux-studio"
mkdir -p "$OPT/libexec" "$P/usr/bin" "$P/usr/share/applications" "$P/usr/share/icons/hicolor/scalable/apps" \
         "$P/etc/apparmor.d" "$P/usr/share/doc/$PKG" "$P/DEBIAN"

# The runtime was unpacked as you, so a few system files (like /etc/shadow) are owner-unreadable; allow reading.
chmod -R u+rX "$RUNTIME"
echo "Copying editor and runtime (about 2 GB)…"
cp -a "$EDITOR" "$OPT/editor"
cp -a "$RUNTIME" "$OPT/runtime"
# Nothing in the sandbox needs setuid/setgid programs; remove those bits.
find "$OPT/runtime" "$OPT/editor" -type f -perm /6000 -exec chmod ug-s {} +
# Read access for everyone (installed files are owned by root).
chmod -R u+rwX,go+rX,go-w "$OPT"

echo "Copying Linux Studio's own files…"
mkdir -p "$OPT/share"
for d in launcher network toolchains first-run common editor runtime display settings; do
  cp -a "$ROOT/src/$d" "$OPT/share/$d"
done
find "$OPT/share" -name '__pycache__' -prune -exec rm -rf {} +
chmod 0755 "$OPT/share/launcher/linux-studio"
ln -s ../../opt/linux-studio/share/launcher/linux-studio "$P/usr/bin/linux-studio"

sed "s/@WMCLASS@/linux-studio-editor/" "$ROOT/packaging/deb/files/$APPID.desktop" > "$P/usr/share/applications/$APPID.desktop"
cp "$ROOT/packaging/deb/files/$APPID.svg" "$P/usr/share/icons/hicolor/scalable/apps/$APPID.svg"
cp "$ROOT/packaging/deb/files/$APPID.apparmor" "$P/etc/apparmor.d/$APPID"
chmod 0644 "$P/usr/share/applications/$APPID.desktop" "$P/usr/share/icons/hicolor/scalable/apps/$APPID.svg" "$P/etc/apparmor.d/$APPID"

# Licences and notes
cp "$EDITOR/resources/app/LICENSE.txt" "$P/usr/share/doc/$PKG/LICENSE.code-oss.txt" 2>/dev/null || true
cat > "$P/usr/share/doc/$PKG/README" <<EOF
Linux Studio $VERSION ($TYPE build)
Private, sandboxed code editor. Source: https://github.com/seven11ven/linux-studio
Editor: Code - OSS $EDITOR_TAG (MIT licence). Runtime: Debian 13 packages (see runtime-manifest.txt).
Check the sandbox on this computer:  linux-studio --self-test
EOF
cp "$ROOT/build/runtime-manifest.txt" "$P/usr/share/doc/$PKG/runtime-manifest.txt"
printf '%s (%s) unstable; urgency=medium\n\n  * %s build of Linux Studio %s. Full history: project-changelog/ in the source repository.\n\n -- seven11ven <seven11ven@users.noreply.github.com>  %s\n' \
  "$PKG" "$FULLVER" "${TYPE^}" "$VERSION" "$(date -u -R)" | gzip -9n > "$P/usr/share/doc/$PKG/changelog.Debian.gz"
cat > "$P/usr/share/doc/$PKG/copyright" <<EOF
Format: https://www.debian.org/doc/packaging-manuals/copyright-format/1.0/
Upstream-Name: Linux Studio
Source: https://github.com/seven11ven/linux-studio

Files: *
Copyright: 2026 seven11ven
License: none-chosen-yet
 The Linux Studio project has not chosen a licence yet (development build).

Files: opt/linux-studio/editor/*
Copyright: Microsoft Corporation and contributors (Code - OSS)
License: MIT
 See /usr/share/doc/$PKG/LICENSE.code-oss.txt

Files: opt/linux-studio/runtime/*
Copyright: The Debian project and upstream authors
License: various-free
 Debian 13 "main" packages, all free software under the Debian Free Software
 Guidelines. Each package's licence is in opt/linux-studio/runtime/usr/share/doc/.
EOF

# Maintainer scripts and control
install -m 0755 "$ROOT/packaging/deb/debian/postinst" "$ROOT/packaging/deb/debian/prerm" "$ROOT/packaging/deb/debian/postrm" "$P/DEBIAN/"
install -m 0644 "$ROOT/packaging/deb/debian/triggers" "$P/DEBIAN/triggers"
echo "/etc/apparmor.d/$APPID" > "$P/DEBIAN/conffiles"
SIZE_KB="$(du -sk --exclude=DEBIAN "$P" | cut -f1)"
cat > "$P/DEBIAN/control" <<EOF
Package: $PKG
Version: $FULLVER
Section: devel
Priority: optional
Architecture: amd64
Maintainer: seven11ven <seven11ven@users.noreply.github.com>
Installed-Size: $SIZE_KB
Depends: bubblewrap, python3, python3-gi, gir1.2-gtk-4.0, apparmor, xserver-xephyr, python3-xlib, xauth
Homepage: https://github.com/seven11ven/linux-studio
Description: private, sandboxed code editor
 Linux Studio is a code editor (built from Code - OSS) that runs in a sandbox.
 It can only see one project folder, reaches only websites you approve, and
 shows a fake computer name and user to extensions. Python, Node.js, C/C++,
 Git and a shell are bundled; more toolchains can be added from official
 publishers with verified downloads.
EOF

# Safety checks before packing
if find "$P" \( -name '.git' -o -name '.env' -o -name '.env.*' -o -name '*.pem' -o -name '*.key' -o -name 'id_rsa*' \
     -o -name 'id_ed25519*' -o -name 'id_ecdsa*' -o -name '*.p12' -o -name '*.pfx' -o -name 'credentials*' \) \
     -not -path "$P/opt/linux-studio/runtime/*" | grep -q .; then
  echo "Refusing to build: found .git, .env or key files in the package" >&2; exit 1
fi

# Standard permissions for everything shipped (this machine's default folder permissions are non-standard):
# folders 0755, files readable by everyone, nothing writable by group/others; executable bits are kept.
find "$P" -type d -exec chmod 0755 {} +
find "$P" -type f -exec chmod u+rw,go+r,go-w {} +
chmod 1777 "$OPT/runtime/tmp" "$OPT/runtime/var/tmp"   # keep the usual sticky /tmp folders (review #8)
chmod 0755 "$P/DEBIAN" "$P/DEBIAN/postinst" "$P/DEBIAN/prerm" "$P/DEBIAN/postrm"
chmod 0644 "$P/DEBIAN/control" "$P/DEBIAN/triggers" "$P/DEBIAN/conffiles"

mkdir -p "$OUTDIR" "$ROOT/project-builds/logs"
echo "Packing (xz, this takes several minutes)…"
dpkg-deb --root-owner-group -Zxz --build "$P" "$DEB" >/dev/null
SHA="$(sha256sum "$DEB" | cut -d' ' -f1)"
( cd "$OUTDIR" && sha256sum "$(basename "$DEB")" > SHA256SUMS )

LOG="$ROOT/project-builds/logs/$NAME.md"
{
  echo "# Build summary: $NAME"
  echo
  echo "- **Type:** $TYPE build"
  echo "- **Package:** \`$(basename "$DEB")\` ($(du -h "$DEB" | cut -f1), installed size $((SIZE_KB / 1024)) MB)"
  echo "- **SHA-256:** \`$SHA\`"
  echo "- **Built:** $(date -u +%Y-%m-%dT%H:%MZ) from git commit \`$(git -C "$ROOT" rev-parse --short HEAD)\`$(git -C "$ROOT" diff --quiet || echo ' (with uncommitted changes)')"
  echo "- **Editor:** Code - OSS $EDITOR_TAG, run $(jq -r .run_id "$ROOT/build/editor-version.json"), sha256 \`$(jq -r .sha256 "$ROOT/build/editor-version.json" | cut -c1-16)…\`"
  echo "- **Runtime:** $(head -1 "$ROOT/build/runtime-manifest.txt" | sed 's/^# //')"
  echo "- **Depends:** bubblewrap, python3, python3-gi, gir1.2-gtk-4.0, apparmor, xserver-xephyr, python3-xlib, xauth"
} > "$LOG"
echo "Built: $DEB"
echo "Summary: $LOG"
