# Build summary: Linux-Studio-debian-amd64-0.1.0~dev5

- **Type:** dev build
- **Package:** `linux-studio_0.1.0~dev5-1_amd64.deb` (514M, installed size 2181 MB)
- **SHA-256:** `2e5c8a1e9b8ffc9bf3db84ef448a91169c5f40f5ed71bf286f7406c78b498b63`
- **Built:** 2026-11-26T15:28Z from git commit `156d1c5`
- **Editor:** Code - OSS 1.148.0, run 45640173838, sha256 `faa5cee2ad2cd9f8…`
- **Runtime:** Linux Studio runtime: Debian trixie, built 2026-11-26T15:04Z
- **Depends:** bubblewrap, python3, python3-gi, gir1.2-gtk-4.0, apparmor, xserver-xephyr, python3-xlib, xauth
- **Changes from dev4:**
  - CPU and memory limits
  - links in an in-app tab (`xdg-open` shim, link router, browser patch)
  - the "Connection refused" notice
  - Block/Remove wording
  - the Remove-data pop-up
  - Settings scrolls
  - Noto fonts (runtime 2026-11-26)
  - security review fixes F1–F7

## Checks
- **Test suites before the build:**
  - isolation 17/17, network 23/23, toolchains 12/12
  - remove-data 20/20, x11-clipboard 11/11, vsce-sign 15/15, link-router 30/30
  - proxy and toolchains unit tests OK
  - self-test 8/8
- **Clean Ubuntu 24.04 (noble) test:** **27/27 passed**.
- **lintian** (full report, counted per tag): **0 errors in Linux Studio's own packaging.** The same 4 explained warnings as dev3 and dev4.
- **Pending:** the PM's Mint test (memory limit enforced, Settings, Cline sign-in in the in-app tab, notice, wording).
