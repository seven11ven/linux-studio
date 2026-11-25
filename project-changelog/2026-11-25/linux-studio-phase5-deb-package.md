# Linux Studio — Phase 5: first .deb package (dev build)

- **Date:** 2026-11-25
- **Time:** 18:30–19:15 UTC
- **Performed By:** Claude Opus 5.5 (Anthropic), via Claude Code. Security review by the jake-lockley agent (Claude).
- **Approved By:** Project Manager

## Decisions (PM)
- dev build; .deb only; target Ubuntu 24.04 / 24.10+
- AppArmor: Ubuntu's restricted `bwrap-userns-restrict` design (inner Chromium and Rust-installer sandboxes off where not allowed)

## Changes
- **Nested Rust-installer sandbox** (finished from Phase 4): runtime gains `bubblewrap` 0.12.0; `worker.py` runs install.sh nested when possible.
- **Launcher:** packaged bwrap path (`/opt/linux-studio/libexec/bwrap`; no PATH search when installed), `--self-test`,
  and an automatic `--no-sandbox` for the editor only when inner sandboxes can't start.
- **`packaging/deb/`:**
  - `postinst` (copies bwrap, loads the profile, handles abort-remove, respects admin disable), `prerm`, `postrm`, and a `triggers` file on `/usr/bin/bwrap`
  - restricted AppArmor profile, desktop file with Approved websites and Toolchains actions, and a placeholder SVG icon
- **`scripts/build-deb.sh`:**
  - assembles the package, with folders 0755, sticky `/tmp`, no setuid, a secret scan, and the Debian changelog and copyright
  - builds with `--root-owner-group -Zxz` and writes a build summary
- **`scripts/build-runtime.sh`:** removes the unreadable `/etc/*-` backup files.
- **`tests/deb-install-test.sh`:** a clean Ubuntu 24.04 install, upgrade, trigger, remove and purge test with mmdebstrap (no Docker).
- **Version control:**
  - launcher → `version-control/launcher/2026-11-25_1841/`
  - runtime → `version-control/runtime/2026-11-25_1830/` (ignored)
  - worker → `version-control/toolchains/2026-11-25_1831/`
  - rev-2 inputs → `version-control/packaging/2026-11-25_1856/`

## Builds (project-builds/dev-builds/Linux-Studio-debian-amd64-0.1.0~dev1/)
| Revision | Status |
|---|---|
| -1 | **Defective**: folders 0754 (users couldn't open the launcher). Kept; don't install. |
| -2 | **Superseded**: AppArmor profile too broad (security review). Kept; don't install. |
| -3 | **Current**: 469 MB, clean Ubuntu 24.04 test 25/25. |

## Security review (jake-lockley)
1. **Medium-High:** the unrestricted bwrap copy let any program bypass Ubuntu's userns restriction. **Fixed** with Ubuntu's restricted design (PM).
2. **Low:** abort-remove left a broken install. **Fixed.**
3. **Low:** an admin's disable of the profile was ignored. **Fixed.**
4. **Low:** unclear error if bwrap is missing. **Fixed.**
5. **Low:** PATH search for bwrap. **Fixed** for installed copies.
6. **Info:** self-test temp folder cleanup. **Fixed.**
7. **Info:** narrow secret scan. **Widened.**
8. **Info:** `/tmp` sticky bit dropped. **Fixed.**

## Verification
- **Clean Ubuntu 24.04:** 25/25 (see the build summary in `project-builds/logs/`).
- **Codespace:** `--self-test` 7/7 plus INFO, toolchains unit 17, e2e 12, isolation 17, network 23 (earlier this session).
- **Pending:** `lintian` and `desktop-file-validate` (PM to install the tools); real AppArmor behaviour on the PM's Ubuntu 24.04 machine.

## Impacts
- First installable Linux Studio package. No secrets or environment variables introduced. The `.deb` files are not committed (ignored).

## Update 19:54 UTC: lintian and desktop-file-validate

- The PM installed `lintian` and `desktop-file-utils`.
- **desktop-file-validate:** no errors. One hint fixed in the source (removed the `TextEditor` category). It takes effect in the next build.
- **lintian on revision 3:** 0 errors, 40 warnings, all in Debian's own runtime files. Each is explained in the build log; none are silenced.
- **Performed By:** Claude Opus 5.5 (Anthropic) · **Approved By:** Project Manager
