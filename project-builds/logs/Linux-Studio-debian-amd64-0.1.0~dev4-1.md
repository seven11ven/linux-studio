# Build summary: Linux-Studio-debian-amd64-0.1.0~dev4

- **Type:** dev build
- **Package:** `linux-studio_0.1.0~dev4-1_amd64.deb` (448M, installed size 2048 MB)
- **SHA-256:** `49d23119ff66cb5fb34160700390454d1080c98c6dd7f5d95c6f65059db13741`
- **Built:** 2026-11-26T14:05Z from git commit `207124c` (with uncommitted changes)
- **Editor:** Code - OSS 1.148.0, run 45640173838, sha256 `faa5cee2ad2cd9f8…`
- **Runtime:** Linux Studio runtime: Debian trixie, built 2026-11-25T22:36Z
- **Depends:** bubblewrap, python3, python3-gi, gir1.2-gtk-4.0, apparmor, xserver-xephyr, python3-xlib, xauth
- **Changes from dev3:**
  - Extension signature checker (`@vscode/vsce-sign` replacement, pinned Open VSX key).
  - Settings: Extension signatures (Check / Don't check), Largest extension to check, and Your data (Remove my Linux Studio data).
  - `--remove-my-data`.
  - The approval pop-up stays on top without taking focus, and its lock restarts on input.
  - Flatter corners.
  - Security review fixes.

## Checks
- **Package contents:** the checker is in place at `opt/linux-studio/editor/resources/app/node_modules/@vscode/vsce-sign/` (`index.js` and `package.json`).
- **Clean Ubuntu 24.04 (noble) test:** **27/27 passed** (install, upgrade, bubblewrap trigger, remove, purge; user data kept throughout).
- **lintian** (full report, counted per tag, nothing silenced): **0 errors in Linux Studio's own packaging.** The same 4 explained warnings as dev3:
  `command-with-path-in-maintainer-script`, `maintainer-script-empty`, `no-manual-page`, `initial-upload-closes-no-bugs`.
  Everything else is `/opt` by design, or in unchanged upstream runtime and editor files.
- **Test suites before the build:**
  - proxy and toolchains unit tests OK
  - isolation 17/17, network 23/23, toolchains 12/12
  - remove-data 20/20, x11-clipboard 11/11, vsce-sign 15/15
- **Real editor install** (test sandbox): genuine signature → Success; wrong key → refused, nothing installed; Don't check → installed without the check.
- **Pending:** the PM's Mint test (Settings sections, pop-up on top, extension install, Remove my data refusing while open).
