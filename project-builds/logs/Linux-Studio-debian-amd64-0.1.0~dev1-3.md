# Build summary: Linux-Studio-debian-amd64-0.1.0~dev1

- **Type:** dev build
- **Package:** `linux-studio_0.1.0~dev1-3_amd64.deb` (448M, installed size 2041 MB)
- **SHA-256:** `24461ac56cc95fc814298cfc21d6020d762c379480fd00de293da5cd4e200dde`
- **Built:** 2026-11-25T19:01Z from git commit `59f28ea` (with uncommitted changes)
- **Editor:** Code - OSS 1.148.0, run 45640173838, sha256 `faa5cee2ad2cd9f8…`
- **Runtime:** Linux Studio runtime: Debian trixie, built 2026-11-25T18:31Z
- **Depends:** bubblewrap, python3, python3-gi, gir1.2-gtk-4.0, apparmor

## Checks
- **Clean Ubuntu 24.04 (noble) test** (`tests/deb-install-test.sh`): **25/25 passed**.
  - Install with dependencies from Ubuntu. The `/usr/bin` link, bwrap copy, AppArmor profile (`apparmor_parser` syntax OK; capabilities denied inside)
    and desktop file all check out, Exec/TryExec/Icon point to shipped files, the runtime `/tmp` is sticky, and there are no setuid files.
    Everything is root-owned, and `--help` works.
  - Upgrade to the next revision: the bwrap copy is kept and user data survives.
  - A bubblewrap reinstall fires the trigger, which re-copies bwrap.
  - Remove: the bwrap copy is deleted, nothing is left in `/opt`, and user data survives.
  - Purge: the profile and `/opt/linux-studio` are gone, and user data survives.
- **Folder permissions:** every folder is 0755 except the runtime `tmp` folders (1777).
- **desktop-file-validate:** passes with no errors. One hint: `TextEditor` is usually paired with `Utility`. Fixed in the source (`Categories=Development;IDE;`) for the next build.
- **lintian:** **0 errors, 40 warnings.** Every warning is in Debian's own files inside the private runtime (`opt/linux-studio/runtime/`), not in Linux Studio's packaging:
  - `unusual-interpreter python` ×22: doc and example scripts and pip's vendored files with `#!/usr/bin/python`. They're never run on the host.
  - `uses-dpkg-database-directly` ×16: dpkg and debconf internals in the read-only runtime. Never run.
  - `systemd-service-file-refers-to-unusual-wantedby-target` ×2: Debian getty units. There's no systemd in the sandbox.

  These are explained here, not silenced. The Debian files are left unmodified.
- **Still pending:** AppArmor behaviour on a real Ubuntu 24.04 kernel can only be tested on the PM's machine (`linux-studio --self-test`).

## Real-machine test (PM, Ubuntu 24.04, 22:06 UTC)
- Downloaded through a temporary private port (auto-closed after one complete download), installed with `apt`, then ran `linux-studio --self-test`.
- **Result: 7 passed, 0 failed.** The sandbox works under Ubuntu's AppArmor restriction with the Linux Studio profile: fake name and user, home hidden,
  loopback only, no direct internet, proxy bridge running.
- **INFO:** inner sandboxes aren't allowed, as expected under the restricted design. The editor's Chromium inner sandbox and the Rust installer's nested sandbox are off; the main sandbox still isolates everything.
- **Still to confirm:** the editor window opens from the app menu.

## Correction (2026-11-26 07:17 UTC): the lintian result above was wrong
- The "0 errors, 40 warnings" line is **incorrect**. The command used (`lintian … | sort | uniq -c | sort -rn | head -40`) kept only the first 40 lines.
  Every line had a count of 1, so the reverse sort put all `W:` lines before the `E:` lines, and every error was cut off.
- A full count on the next build (dev2) shows the real picture. That build differs only in Phase 6 files, so revision 3 would have shown nearly the same
  result. Most findings are `dir-or-file-in-opt`, which is expected because the app lives in `/opt` on purpose, and the rest are in the bundled Debian
  runtime and the editor, plus 3 minor issues in Linux Studio's own packaging. These were fixed in dev2-2. See `Linux-Studio-debian-amd64-0.1.0~dev2-2.md`.
- No security or functional problem was hidden by the mistake. Lintian results are now counted per tag with the full report saved, never cut with `head`.
- **Performed By:** Claude Opus 5.5 (Anthropic) · **Approved By:** Project Manager
