#!/usr/bin/env bash
# Clean-install test for the Linux Studio .deb, as required by guidelines/Linux-Packaging.md:
# install -> checks -> upgrade -> remove -> purge, in a fresh Ubuntu 24.04 (noble) system built with mmdebstrap
# (no Docker, no root: runs as "fake root" in a user namespace). Downloads the noble base system (~150 MB).
#
# Usage: tests/deb-install-test.sh path/to/linux-studio_X_amd64.deb
# AppArmor itself can't be tested in this environment (no kernel AppArmor here); the postinst skips it cleanly.
set -euo pipefail

DEB="$(realpath "${1:?Usage: $0 <package.deb>}")"
[[ -f "$DEB" ]] || { echo "No such file: $DEB" >&2; exit 2; }
T="$(mktemp -d)"
trap 'rm -rf "$T"' EXIT

echo "Making an 'upgrade' copy of the package (same files, revision +1)…"
mkdir "$T/x"
dpkg-deb -R "$DEB" "$T/x"
OLD="$(grep '^Version:' "$T/x/DEBIAN/control" | cut -d' ' -f2)"
NEW="${OLD%-*}-$(( ${OLD##*-} + 1 ))"
sed -i "s/^Version: .*/Version: $NEW/" "$T/x/DEBIAN/control"
find "$T/x" -type d -exec chmod 0755 {} +                 # this machine's default permissions are too loose for dpkg-deb
chmod 0755 "$T/x/DEBIAN/postinst" "$T/x/DEBIAN/prerm" "$T/x/DEBIAN/postrm"
chmod 1777 "$T/x/opt/linux-studio/runtime/tmp" "$T/x/opt/linux-studio/runtime/var/tmp"
dpkg-deb --root-owner-group -Zgzip -z1 --build "$T/x" "$T/upgrade.deb" >/dev/null
rm -rf "$T/x"

cat > "$T/checks.sh" <<'EOF'
#!/bin/sh
# Runs inside the fresh Ubuntu system.
pass=0; fail=0
t() { if sh -c "$2" >/dev/null 2>&1; then echo "PASS  $1"; pass=$((pass+1)); else echo "FAIL  $1"; fail=$((fail+1)); fi; }
export DEBIAN_FRONTEND=noninteractive
apt-get install -y -q /tmp/pkg.deb >/tmp/install.log 2>&1 || { echo "FAIL  apt install"; tail -20 /tmp/install.log; exit 1; }
echo "PASS  apt install of the package (with all dependencies from Ubuntu)"; pass=$((pass+1))
t "Command on PATH: /usr/bin/linux-studio -> /opt launcher" '[ "$(readlink -f /usr/bin/linux-studio)" = /opt/linux-studio/share/launcher/linux-studio ] && [ -x /usr/bin/linux-studio ]'
t "Linux Studio's own bwrap copy created by postinst" 'cmp -s /usr/bin/bwrap /opt/linux-studio/libexec/bwrap && [ -x /opt/linux-studio/libexec/bwrap ]'
t "AppArmor profile installed (only for the bwrap copy)" 'grep -q "profile linux-studio-bwrap /opt/linux-studio/libexec/bwrap" /etc/apparmor.d/io.github.seven11ven.linuxstudio'
t "AppArmor profile is valid (apparmor_parser syntax check)" 'apparmor_parser -Q -K /etc/apparmor.d/io.github.seven11ven.linuxstudio'
t "AppArmor: everything inside runs with capabilities denied" 'grep -q "px /\*\* -> linux-studio-bwrap//&linux-studio-unpriv" /etc/apparmor.d/io.github.seven11ven.linuxstudio && grep -q "audit deny capability" /etc/apparmor.d/io.github.seven11ven.linuxstudio'
t "Runtime /tmp keeps its sticky bit" '[ "$(stat -c %a /opt/linux-studio/runtime/tmp)" = 1777 ]'
t "Desktop file Exec/TryExec point to a shipped file" 'grep -q "^Exec=/usr/bin/linux-studio$" /usr/share/applications/io.github.seven11ven.linuxstudio.desktop && [ -x /usr/bin/linux-studio ]'
t "Icon file matches Icon= name" '[ -f /usr/share/icons/hicolor/scalable/apps/io.github.seven11ven.linuxstudio.svg ]'
t "Editor and runtime present" '[ -x /opt/linux-studio/editor/linux-studio-editor ] && [ -x /opt/linux-studio/runtime/usr/bin/bash ]'
t "No setuid/setgid files shipped" '[ -z "$(find /opt/linux-studio -perm /6000 -type f)" ]'
t "linux-studio --help works" '/usr/bin/linux-studio --help | grep -q "linux-studio --toolchains"'
t "All package files owned by root" '[ -z "$(dpkg -L linux-studio | xargs -d "\n" stat -c "%U" 2>/dev/null | grep -v "^root$")" ]'
# A user's data, which must survive upgrade, remove and purge.
mkdir -p /home/tester/.config/linux-studio /home/tester/.local/share/linux-studio/home
echo keep > /home/tester/.config/linux-studio/config; echo keep > /home/tester/.local/share/linux-studio/home/notes.txt
# Upgrade
apt-get install -y -q /tmp/upgrade.deb >/tmp/upgrade.log 2>&1 && echo "PASS  Upgrade to the next revision" && pass=$((pass+1)) || { echo "FAIL  Upgrade"; tail -5 /tmp/upgrade.log; fail=$((fail+1)); }
t "bwrap copy still present after upgrade" '[ -x /opt/linux-studio/libexec/bwrap ]'
t "User data survives upgrade" '[ "$(cat /home/tester/.config/linux-studio/config)" = keep ]'
# Trigger: Ubuntu updates bubblewrap -> copy refreshed
cp /opt/linux-studio/libexec/bwrap /tmp/old-bwrap; echo "x" >> /opt/linux-studio/libexec/bwrap
apt-get install -y -q --reinstall bubblewrap >/dev/null 2>&1
t "bubblewrap update re-copies bwrap (dpkg trigger)" 'cmp -s /usr/bin/bwrap /opt/linux-studio/libexec/bwrap'
# Remove
apt-get remove -y -q linux-studio >/tmp/remove.log 2>&1 && echo "PASS  Remove" && pass=$((pass+1)) || { echo "FAIL  Remove"; tail -5 /tmp/remove.log; fail=$((fail+1)); }
t "bwrap copy deleted on remove" '[ ! -e /opt/linux-studio/libexec/bwrap ]'
t "Nothing left in /opt/linux-studio after remove" '[ ! -e /opt/linux-studio ] || [ -z "$(find /opt/linux-studio -mindepth 1 -not -type d)" ]'
t "User data survives remove" '[ "$(cat /home/tester/.local/share/linux-studio/home/notes.txt)" = keep ]'
# Purge
apt-get purge -y -q linux-studio >/tmp/purge.log 2>&1 && echo "PASS  Purge" && pass=$((pass+1)) || { echo "FAIL  Purge"; tail -5 /tmp/purge.log; fail=$((fail+1)); }
t "AppArmor profile gone after purge" '[ ! -e /etc/apparmor.d/io.github.seven11ven.linuxstudio ]'
t "/opt/linux-studio gone after purge" '[ ! -e /opt/linux-studio ]'
t "User data survives purge" '[ "$(cat /home/tester/.config/linux-studio/config)" = keep ]'
echo; echo "$pass passed, $fail failed"
[ "$fail" = 0 ]
EOF
chmod +x "$T/checks.sh"

echo "Building a fresh Ubuntu 24.04 system and running the checks (several minutes)…"
mmdebstrap --mode=unshare --variant=apt --components=main,universe \
  --keyring=/usr/share/keyrings/ubuntu-archive-keyring.gpg \
  --customize-hook='mkdir -p "$1/tmp/t"' --customize-hook="copy-in '$DEB' /tmp" --customize-hook="sync-in '$T' /tmp/t" \
  --customize-hook='mv "$1"/tmp/*.deb "$1"/tmp/pkg.deb 2>/dev/null; cp "$1"/tmp/t/upgrade.deb "$1"/tmp/upgrade.deb; cp "$1"/tmp/t/checks.sh "$1"/tmp/checks.sh' \
  --customize-hook='chroot "$1" sh /tmp/checks.sh | tee "$1"/tmp/result.txt' \
  --customize-hook='grep -q " 0 failed" "$1"/tmp/result.txt' \
  noble "$T/noble.tar" \
  "deb http://archive.ubuntu.com/ubuntu noble main universe" \
  "deb http://archive.ubuntu.com/ubuntu noble-updates main universe" \
  "deb http://security.ubuntu.com/ubuntu noble-security main universe" 2>&1 | grep -E "^(PASS|FAIL|[0-9]+ passed)|E: " || true
