# Build summary: Linux-Studio-debian-amd64-0.1.0~dev6

- **Type:** dev build
- **Package:** `linux-studio_0.1.0~dev6-2_amd64.deb` (514M, installed size 2181 MB)
- **SHA-256:** `7fb76e635e6176c58ca63616a45ff2f28f0d024e7a1b0be2722632d4600640a0`
- **Built:** 2026-11-26T22:09Z from git commit `7e6d449`
- **Editor:** Code - OSS 1.148.0, run 45640173838, sha256 `faa5cee2ad2cd9f8…`
- **Runtime:** Linux Studio runtime: Debian trixie, built 2026-11-26T21:21Z
- **Depends:** bubblewrap, python3, python3-gi, gir1.2-gtk-4.0, apparmor, xserver-xephyr, python3-xlib, xauth
- **Changes from dev5:**
  - the terminal (login shell) PATH restores `xdg-open` and the chosen toolchains
  - `--no-sandbox` for the short-lived editor command on Ubuntu 24.04+/Mint
  - page full screen stays inside its tab (editor patch)
  - no self-test X errors
  - safer private-display size

  dev6-1 (without the full-screen fix) was not delivered.

## Checks
- **Test suites before the build:**
  - isolation 18/18, network 23/23, toolchains 13/13
  - remove-data 20/20, x11-clipboard 11/11, vsce-sign 15/15, link-router 32/32
  - proxy and toolchains unit tests OK
  - self-test 8/8
- **Package contents:** the full-screen change is in the packaged editor.
- **Clean Ubuntu 24.04 (noble) test:** **27/27 passed**.
- **lintian:** **0 errors in Linux Studio's own packaging**, and 3 explained warnings (this time without `initial-upload-closes-no-bugs`, since this is revision 2).
- **Pending:** the PM's Mint test.
