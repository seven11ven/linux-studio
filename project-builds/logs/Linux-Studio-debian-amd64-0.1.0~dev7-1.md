# Build summary: Linux-Studio-debian-amd64-0.1.0~dev7

- **Type:** dev build
- **Package:** `linux-studio_0.1.0~dev7-1_amd64.deb` (514M, installed size 2181 MB)
- **SHA-256:** `e2bd89794d71de1891009c11e0563c44e14d7779f0fb70114c1f2666acb45ca0`
- **Built:** 2026-11-27T03:40Z from git commit `ee3ec07` (with uncommitted changes)
- **Editor:** Code - OSS 1.148.0, run 45640173838, sha256 `faa5cee2ad2cd9f8…`
- **Runtime:** Linux Studio runtime: Debian trixie, built 2026-11-27T03:31Z
- **Depends:** bubblewrap, python3, python3-gi, gir1.2-gtk-4.0, apparmor, xserver-xephyr, python3-xlib, xauth
- **Changes from dev6-2:** the dev6 security review fixes D6-1 to D6-8.
  - **Full screen:** the exit gives the page no click, the user's F11 choice is followed, and full screen that starts after the page lost focus is ended.
  - **Launcher:** clears its internal variables at start.
  - **PATH:** set up through `/etc/linux-studio/path.sh`, also in `bash -lc`, and never with an empty entry.
  - **Repo:** the stray VS Code files are removed.

## Checks
- **Test suites:**
  - isolation 21/21, including the new `bash -lc`, empty-PATH and decoy `SELFTEST_DIR` checks
  - network 23/23, toolchains 13/13, remove-data 20/20
  - x11-clipboard 11/11 (a first run failed 3 timing-sensitive checks right after the runtime rebuild; it passed 11/11 alone and in the full rerun)
  - vsce-sign 15/15, link-router 32/32, proxy unit OK
- **Package contents:** contains the reviewed full-screen logic and `etc/linux-studio/path.sh`.
- **Clean Ubuntu 24.04 (noble) test:** **27/27 passed**.
- **lintian:** **0 errors in Linux Studio's own packaging**, and the same 4 explained warnings.
- **Pending:** a quick PM re-check on Mint: video full screen, plus a toolchain in the terminal if wanted.
