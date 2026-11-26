# Build summary: Linux-Studio-debian-amd64-0.1.0~dev3

- **Type:** dev build
- **Package:** `linux-studio_0.1.0~dev3-1_amd64.deb` (448M, installed size 2048 MB)
- **SHA-256:** `7a6f44c03139e7ea2fe35c3e2fdcb1747faf9a6872fc7c2e6a74d18c96bcf53f`
- **Built:** 2026-11-26T08:09Z from git commit `988c21b` (with uncommitted changes)
- **Editor:** Code - OSS 1.148.0, run 45640173838, sha256 `faa5cee2ad2cd9f8…`
- **Runtime:** Linux Studio runtime: Debian trixie, built 2026-11-25T22:36Z
- **Depends:** bubblewrap, python3, python3-gi, gir1.2-gtk-4.0, apparmor, xserver-xephyr, python3-xlib, xauth
- **Changes from dev2-2:**
  - In the private X11 window, the editor's own minimise, maximise and close buttons are hidden, leaving only the desktop's.
  - Every Linux Studio window shows the LS icon.
  - The private display window is labelled `linux-studio-editor`, the menu entry's `StartupWMClass`.

## Checks
- **Clean Ubuntu 24.04 (noble) test:** **27/27 passed** (install, upgrade, bubblewrap trigger, remove, purge; user data kept throughout).
- **Test X11 desktop:** the main window reports class `linux-studio-editor` with the LS icon (32, 64 and 128 px). The Settings window shows the LS icon when the icon is installed.
  The editor shows no window buttons of its own, and its layout buttons remain.
- **lintian** (full report, counted per tag, nothing silenced): **0 errors in Linux Studio's own packaging.** It reports these warnings:
  - `command-with-path-in-maintainer-script`
  - `maintainer-script-empty postrm`
  - `no-manual-page`
  - `initial-upload-closes-no-bugs`: a Debian-archive rule that a first upload closes a bug report. It doesn't apply to a package not uploaded to Debian.

  The first three are explained in the dev2-2 log. Everything else is either `/opt` by design or in unchanged upstream runtime and editor files, as in dev2-2.
