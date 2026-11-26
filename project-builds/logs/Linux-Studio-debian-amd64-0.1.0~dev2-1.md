# Build summary: Linux-Studio-debian-amd64-0.1.0~dev2

- **Type:** dev build
- **Package:** `linux-studio_0.1.0~dev2-1_amd64.deb` (448M, installed size 2048 MB)
- **SHA-256:** `290bf1e677450f29961d168e98bca7bc8ef94f86ca14f1cd4875ed5559001688`
- **Built:** 2026-11-26T06:24Z from git commit `f467450` (with uncommitted changes)
- **Editor:** Code - OSS 1.148.0, run 45640173838, sha256 `faa5cee2ad2cd9f8…`
- **Runtime:** Linux Studio runtime: Debian trixie, built 2026-11-25T22:36Z
- **Depends:** bubblewrap, python3, python3-gi, gir1.2-gtk-4.0, apparmor, xserver-xephyr, python3-xlib, xauth

## Checks
- **Clean Ubuntu 24.04 (noble) test** (`tests/deb-install-test.sh`): **27/27 passed**, including the new checks: Xephyr, python3-xlib, the bridge and the
  Settings window are installed, and `--get-clipboard` defaults to paste-only.
- **lintian:** 3 minor issues found in Linux Studio's own packaging (a relative `/usr/bin` link, Python helpers not marked executable, a long
  changelog line). **Superseded by dev2-2**, which fixes them. Kept, as the guidelines require.
