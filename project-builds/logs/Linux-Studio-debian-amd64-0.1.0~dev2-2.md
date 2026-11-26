# Build summary: Linux-Studio-debian-amd64-0.1.0~dev2 (revision 2)

- **Type:** dev build
- **Package:** `linux-studio_0.1.0~dev2-2_amd64.deb` (448M, installed size 2048 MB)
- **SHA-256:** `57cdf04744c4029b953bba3d3eb9ce6a9f5e5d14ec0d45f363fd2a0476434497`
- **Built:** 2026-11-26T07:21Z from git commit `f467450` (with uncommitted changes)
- **Editor:** Code - OSS 1.148.0, run 45640173838, sha256 `faa5cee2ad2cd9f8…`
- **Runtime:** Linux Studio runtime: Debian trixie, built 2026-11-25T22:36Z
- **Depends:** bubblewrap, python3, python3-gi, gir1.2-gtk-4.0, apparmor, xserver-xephyr, python3-xlib, xauth
- **Changes from revision 1 (packaging only):** absolute `/usr/bin/linux-studio` link, Linux Studio's `#!` Python helpers marked executable, changelog lines wrapped.
  These are the three lintian findings in Linux Studio's own packaging. Revision 1 is kept, as the guidelines require.

## Checks
- **Clean Ubuntu 24.04 (noble) test** (`tests/deb-install-test.sh`): **27/27 passed**. That covers install with dependencies, `/usr/bin` link, bwrap copy and AppArmor
  profile, desktop file, X11 parts and paste-only default, root-owned files, upgrade, the bubblewrap trigger, remove and purge. User data survives every step.
- **lintian** (full report counted per tag, nothing silenced, no overrides). It reports errors, which is expected for this kind of package:

  **In Linux Studio's own packaging: 0 errors, 3 warnings, all explained:**
  - `command-with-path-in-maintainer-script /usr/bin/bwrap`: postinst checks that exact file exists before copying it. The full path is the point.
  - `maintainer-script-empty postrm`: postrm only checks its argument (it rejects unknown ones, as the packaging guideline requires). dpkg removes the files.
  - `no-manual-page`: there's no man page yet; `linux-studio --help` covers it. Planned before a release build.

  **By design:**
  - `dir-or-file-in-opt` ×64,384: Debian reserves `/opt` for software installed outside the package system. Linux Studio deliberately installs
    its private editor and runtime there, the same as Chrome, VS Code and other app vendors do.
  - `non-standard-dir-perm` ×2: the runtime's `tmp` folders are 1777 (sticky), like every Linux `/tmp`.

  **Inside the bundled Debian runtime and the editor (unchanged upstream files, used only inside the sandbox).** Examples:
  - `package-installs-python-pycache-dir`, `missing-dep-for-interpreter`, `custom-library-search-path`, `embedded-library`,
    `unstripped-binary-or-object`, `shared-library-is-executable` and `script-not-executable` ×220
  - Debian service files and dpkg internals that never run in the sandbox
  - `privacy-breach-*`: links to web images in bundled documentation and HTML. These are never loaded by Linux Studio, and the sandbox has no direct internet anyway.

  These are kept unmodified on purpose, because changing upstream files would make the runtime harder to verify against Debian.
- **Not yet run:** the PM's real machine test (Linux Mint, X11): `--self-test` and the editor in its private window.
