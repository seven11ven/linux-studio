# Linux Studio — Phase 6: private X11 display, clipboard setting, Settings window, look fixes

- **Date:** 2026-11-25 (late) to 2026-11-26
- **Time:** 2026-11-25 22:20 – 2026-11-26 06:30 UTC (with a pause)
- **Performed By:** Claude Opus 5.5 (Anthropic), via Claude Code. Security review by the jake-lockley agent (Claude).
- **Approved By:** Project Manager

## Why
The PM's computer runs Linux Mint (Cinnamon, X11). The dev1 package passed `--self-test` there, but the editor refused to open on X11, as designed.
The PM chose to make X11 safe with a **private nested display (Xephyr)** instead of the risky `--allow-x11`, plus a **clipboard setting** they control.
After reviewing a real-screenshot gallery, the PM also approved **five look fixes** and **mockup screen 5 (Settings)**.

## Changes
- **Private X11 display** (`setup_x11` in `src/launcher/linux-studio`):
  - On X11, the editor runs inside Xephyr, one host window titled "Linux Studio", sized to 85% of the screen.
  - Xephyr has a fresh random cookie each launch, XTEST off, and GLX, XVideo, MIT-SCREEN-SAVER and X-Resource off. It runs in its own sandbox:
    `--clearenv`, `--cap-drop ALL`, only `/usr` and `/etc`.
  - The editor sees only the private display. `matchbox-window-manager` (added to the runtime) keeps the editor maximised.
  - `--allow-x11` is no longer needed. The old direct mode is available only as `--unsafe-direct-x11`.
- **Clipboard bridge** (`src/display/clipboard_bridge.py`, its own sandbox, python3-xlib). Text only, 1 MB cap.
  - **Paste only (default):** one read within 1 s after a real Ctrl+V, Ctrl+Shift+V or Shift+Insert, detected through XInput2 raw events with virtual XTEST
    devices ignored. The desktop's highlighted-text selection is never shared, and copies made inside stay inside.
  - **Both directions:** two-way sync, including the selection, with a rate limit.
- **Settings window** (`src/settings/settings_window.py`, mockup screen 5):
  - shows the clipboard toggle, the display mode, and shortcuts to Approved websites and Toolchains
  - `linux-studio --settings` and a Settings menu action
  - settings are stored by the launcher (`get_setting`/`set_setting`; `--get-clipboard`/`--set-clipboard`), and other keys are kept on update
- **Look fixes:**
  1. The desktop GTK windows follow the system's light or dark setting (`src/common/studio_theme.py`, both mockup palettes).
  2. Linux Studio icon and LS watermark in the editor (`src/editor/branding/`, plus a workflow step).
  3. The unused AI side bar is hidden by default.
  4. `startupEditor: none`, plus a declarative "Get started with Linux Studio" walkthrough (data only).
  5. The light theme gets a light terminal, so hints are readable.
- **`--self-test`** adds three X11 checks: only the private display is visible, it's running, and XTEST is absent.
- **Packaging:**
  - `Depends` adds `xserver-xephyr`, `python3-xlib` and `xauth`
  - the share folders `display/` and `settings/` are included
  - Settings menu action; the install test gains two checks
- **Runtime** rebuilt with `matchbox-window-manager` and `x11-utils`.
- **Mockup page:** screen 5 (Settings) and a real-screenshot gallery (tab 6) added and republished.
- **Version control backups:**
  - `version-control/launcher/2026-11-25_2228/`
  - `version-control/build-workflow/2026-11-25_2225/`
  - `version-control/editor-config/2026-11-25_2225/`
  - `version-control/packaging/2026-11-25_2247/`
  - `version-control/runtime/2026-11-25_2235/` (binary, ignored by git)

## Security review (jake-lockley) and results
| # | Severity | Finding | Result |
|---|---|---|---|
| 1 | Medium-High | A Xephyr exploit would hold a full host cookie | **Partly addressed:** unneeded Xephyr extensions turned off, and Xephyr's sandbox tightened (#2). An "untrusted" host cookie could **not** be verified on the test X server (rejected as invalid even though generation succeeded), so it was **not shipped**. It's a follow-up to test on the PM's real desktop. |
| 2 | Medium | Xephyr and bridge sandboxes too loose (environment, `/`, capabilities) | **Fixed:** `--clearenv`, `--cap-drop ALL`, only `/usr` and `/etc` |
| 3 | Medium-Low | Cookies visible in `xauth` command arguments | **Fixed:** cookies are piped (`xauth source -`) |
| 4 | Medium-Low | Middle-click releases the desktop's highlighted text | **Fixed (PM):** the selection isn't shared in Paste only |
| 5 | Low | Reusable 2 s window | **Fixed (PM):** one read within 1 s; a formats (TARGETS) query doesn't use it up |
| 6 | Low | Bridge memory and stall abuse (both mode) | **Fixed:** capped property read (`bytes_after` rejected) and a rate limit on fetches |
| 7 | Low | Raw events from virtual XTEST devices | **Fixed:** source devices named "XTEST" ignored |
| 8 | Low | A stuck Ctrl key | **Fixed:** Ctrl and Shift confirmed with `query_keymap` |
| 9 | Info | Forged events reach the bridge; Settings always says "Isolated" | **Fixed:** synthetic events ignored; wording explains `--unsafe-direct-x11` |

Also verified: the reviewer was right that several `-extension` flags work together. My earlier "only the last one counts" result came from mixing `+` and `-`.

## Verification
- `tests/x11-clipboard-test.sh`: **11/11** (isolation, XTEST off, background read blocked, real paste allowed, one read per paste, re-locks after 1 s,
  highlighted text never shared, copy-out blocked in paste-only, both directions working each way, mode switch applying immediately).
- **Real editor on an X11 test desktop:** opens inside the private "Linux Studio" window, and a real Ctrl+V pasted desktop text into a file under the one-read rule.
  Closing it leaves 0 processes and 0 temp files.
- `--self-test` on X11: **10/10**. Headless: 7/7.
- Other suites: isolation 17/17, network 23/23, toolchains e2e 12/12, proxy and toolchain unit tests OK.

## Notes
- The dev2 editor files are the official build from run 45640173838, with the new branding (icon, watermark) and walkthrough **copied in locally**. The workflow now
  adds these itself; re-run "Build Linux Studio editor" before any release so the official build includes them.
- Disk space in the Codespace is getting low (about 7 GB free). Old builds and backups are kept, as the guidelines require, until the PM allows cleaning.

## Update 07:55 UTC: dev2 package, lintian fixes, record correction
- **dev2-1** built and passed the clean Ubuntu 24.04 test **27/27**. A full lintian count found **3 minor issues in our own packaging**: a relative `/usr/bin` link,
  Python helpers with `#!` not marked executable, and a long changelog line.
- **PM decision:** fix them and rebuild. `scripts/build-deb.sh` was changed (backup in `version-control/packaging/2026-11-26_0716/`), and **dev2-2** was built:
  install test **27/27**, lintian **0 errors and 3 explained warnings in Linux Studio's own files**. Everything else is by design (`/opt`) or in unchanged upstream
  runtime and editor files. See `project-builds/logs/Linux-Studio-debian-amd64-0.1.0~dev2-2.md`.
- **Correction:** revision 3's earlier "lintian 0 errors" record was wrong, because the output had been cut to its first 40 lines. Correction notes were added to that build log
  and the Phase 5 changelog.
- **Planned:** Phase 7, game and software developer support starting with Unity. It comes after the Claude Code test, at the PM's request.
- **Performed By:** Claude Opus 5.5 (Anthropic) · **Approved By:** Project Manager

## Update 07:50 UTC: dev2-2 delivered to the PM
- A temporary download page in the scratchpad (not in the repo) on private Codespaces port 8765. It served only the dev2-2 package at a random link and closed itself after one complete download. The port has been confirmed closed.
- **Performed By:** Claude Opus 5.5 (Anthropic) · **Approved By:** Project Manager

## Update 07:52 UTC: dev2-2 real-machine self-test passed
- The PM installed dev2-2 on Linux Mint (X11). `linux-studio --self-test`: **10/10 passed**, including the private X11 display checks.
- **Next:** the PM opens the editor from the menu and tries pasting, then the Claude Code compatibility test.
- **Performed By:** Claude Opus 5.5 (Anthropic) / Project Manager (on-machine test) · **Approved By:** Project Manager

## Update 08:37 UTC: dev3, one set of window buttons and the app icon everywhere
- **PM request:** remove the duplicate window buttons and show the Linux Studio icon instead of a generic gear.
- **Window buttons:** `src/launcher/apply_settings.py` sets `window.controlsStyle: hidden` only in the private X11 window (`LS_PRIVATE_X11=1`), and removes it elsewhere
  so Wayland keeps the editor's buttons. Backup: `version-control/launcher/2026-11-26_0800/`.
- **Icons:**
  - `APP_ICON` default for all GTK windows (`src/common/studio_theme.py`, backup `version-control/common/2026-11-26_0800/`).
  - New `src/display/window_label.py` and `src/display/icons/`: labels the Xephyr window `linux-studio-editor` with the LS icon. It runs in its own sandbox and exits.
  - Launcher backup: `version-control/launcher/2026-11-26_0800/`.
- **dev3-1:** install test **27/27**, lintian 0 errors in our own files. The PM's real-machine test is pending.
- **Performed By:** Claude Opus 5.5 (Anthropic) · **Approved By:** Project Manager

## Update 08:46 UTC: dev3 delivered; dev4 work in progress; paused for the day
- dev3 was delivered through a one-time private link (closed after download) and installed by the PM. One set of window buttons and the LS icon are confirmed.
- **dev4** is written and tested (signature checker 11/11, Remove my data 15/15, real editor install accepts a genuine signature, refuses a wrong one and skips the check when off)
  but **not committed or built**. A security review was running at pause.
  See `project-notes/handoff/2026-11-26-handoff.md` for the full state and next steps.
- **Performed By:** Claude Opus 5.5 (Anthropic) · **Approved By:** Project Manager
