# Linux Studio: dev4, extension signature checker, size limit, Remove my data, pop-up on top, flatter corners

- **Date:** 2026-11-26
- **Time:** about 08:30–09:00 UTC (written before the pause) and 13:45–14:30 UTC (security fixes, size limit, corners, build)
- **Performed By:** Claude Opus 5.5 (Anthropic), via Claude Code. Security review by the jake-lockley agent (Claude Opus 5.5).
- **Approved By:** Project Manager

## Why
- Installing any extension said "Signature verification was not executed". Code - OSS lacks Microsoft's closed-source signature checker. **PM decisions:**
  - write our own checker
  - make it switchable in Settings
  - refuse missing **and** wrong signatures, with Install Anyway
  - make the largest checkable extension configurable in Settings
- The PM asked how to remove extensions after uninstalling, and asked for a **Remove my Linux Studio data** button and command.
- The network approval pop-up hid behind the Linux Studio window, making Claude Code look stuck. **PM: "we have to fix that".**
- After reviewing a preview, the PM chose **corners 30% less rounded** across the UI.

## Changes
- **Signature checker:** `src/editor/vsce-sign/` (new; open source; Node built-ins only).
  - Checks Open VSX's Ed25519 signature and manifest against the pinned Open VSX key `14ccb407-…`.
  - Added to the editor by a new step in `.github/workflows/build-editor.yml` (backup `version-control/build-workflow/2026-11-26_0842/`).
  - Copied into the local build for dev4.
- **Settings (outside the sandbox):**
  - Extension signatures: **Check** (default) or **Don't check**.
  - **Largest extension to check:** 256 MB, 512 MB (default), 1 GB or 1.5 GB.
  - **Your data:** Remove my Linux Studio data, with tick boxes.
- **Launcher options:**
  - `--get/--set-extension-signatures`, `--get/--set-extension-size-limit`
  - `--remove-my-data` (interactive), `--remove-my-data-now`, `--is-running`
  - `--help` now shows every option
- **How settings reach the sandbox:**
  - The signature setting goes in as `LS_VERIFY_EXTENSIONS`, and `apply_settings.py` writes `extensions.verifySignature`.
  - The size limit goes in as a read-only file, `/run/linux-studio/max-extension-mb`.
- **Running registry:** `~/.local/share/linux-studio/running/<pid>` stores each process's start time.
- **Approval pop-up:**
  - `src/common/window_attention.py` (new) keeps it on top and sets the urgency flag on X11, without taking keyboard focus.
  - `src/network/approval_prompt.py`: the 1-second button lock starts when the pop-up appears, restarts on any key press or click while locked, and the buttons
    stay keyboard-reachable (PM decision).
- **Flatter corners:** `src/common/studio_theme.py` (6 px → 4 px, pills → 7 px). The mockups use the same values.
- **Tests:**
  - `tests/vsce-sign-test.sh` (new, 15 cases)
  - `tests/remove-data-test.sh` (new, 20 checks)
- **Docs:** programming and feature documentation; mockup screen 5 (Extension signatures, size limit, Your data; flatter corners), republished.
- **Backups:**
  - `version-control/launcher/2026-11-26_0840/`
  - `version-control/settings/2026-11-26_0840/`
  - `version-control/network/2026-11-26_0830/`
  - `version-control/common/2026-11-26_1356/`
  - `version-control/build-workflow/2026-11-26_0842/`

## Security review (jake-lockley) and results
Confirmed safe:
- no malformed input makes the checker report Success
- the pinned key matches the live key
- the editor refuses installs when the checker fails, is missing, or a signature is stripped
- removal never follows links

| # | Severity | Finding | Result |
|---|---|---|---|
| 1 | Medium | The pop-up took keyboard focus; typing or clicking on bait could approve a site | **Fixed:** no focus request; the lock starts on show and restarts on input. Tested: constant typing and repeated clicking never approved. Buttons stay keyboard-reachable (PM) |
| 2 | Medium | Removal failed on read-only folders (Go cache), or folders locked on purpose | **Fixed:** folders are unlocked first (`find -xdev`, no link following). Tested with 555 and 000 folders |
| 3 | Low | The ZIP parser unpacked every entry (memory blow-up) | **Fixed:** only the two needed entries are unpacked, with caps; the zip-bomb test is refused; a 3,000-case fuzz run peaked at about 150 MB |
| 4 | Low | The 1.5 GB package read; stat-then-read race | **Fixed:** single-handle limited read; the limit is configurable (PM), default 512 MB |
| 5 | Low | No overlap or owner checks | **Fixed:** overlapping folders are refused, and only folders owned by the user are deleted |
| 6 | Info | Running check vs reused process numbers | **Fixed:** the start time is stored and compared |
| 7 | Info | Code inside can switch `extensions.verifySignature` off until restart | **Documented** as a known limit |
| 8–9 | Info | build-cache permissions; `window_label.py` | No change needed (packaging fixes permissions; the label helper uses our own files only) |

## Verification
- **Real editor install, test sandbox:**
  - a genuine extension → "Success"
  - a wrong key → `SignatureIsNotValid`, nothing installed
  - "Don't check" → installed without the check
- **All suites:**
  - proxy and toolchains unit tests OK
  - isolation 17/17, network 23/23, toolchains 12/12
  - remove-data 20/20, x11-clipboard 11/11, vsce-sign 15/15
- dev4 package: see `project-builds/logs/Linux-Studio-debian-amd64-0.1.0~dev4-1.md`.

## Notes
- **The PM should re-run "Build Linux Studio editor" on `dev`** so the official editor build includes the checker (and the earlier branding). dev4 uses a local copy.
- Open VSX signatures prove only that Open VSX served what was uploaded, not that an extension is safe. Keep extensions to a minimum.

## Claude Code compatibility check closed (PM decision)
- The PM confirmed nothing Claude-specific should be built in. The PM's hands-on use already answered the question: it works under the normal rules,
  using `api.anthropic.com` and `github.com` (when cloning) through the approval pop-up. The hidden pop-up it revealed is fixed in dev4.
- It's removed as a separate step. **Next order:** dev4 → dev5 (CPU and memory settings) → Phase 7 (game development support).

## Update 14:46 UTC: dev4 delivered and tested by the PM; dev5 scope approved
- dev4 was delivered through a one-time private link (closed after download). The PM's checks passed: Settings, extension installs (signature check), pop-up on top,
  and Remove my data.
- **Investigated "no pop-up after Remove":** the proxy test shows Remove closes an open tunnel in 5.0 s and the next connection asks again. The silent case is a site
  refused this session after an unanswered pop-up, or a blocked site. Hence the new notice.
- **dev5 scope (all mockups approved by the PM):**
  - CPU and memory settings (defaults: all cores but one, 75% of memory)
  - web links open in the Integrated Browser tab
  - extension sign-in callbacks tested (Cline example)
  - Remove-data confirmation as its own pop-up window
  - "Connection refused" notice (blocked or unanswered; at most once per site per session; no focus; 20 s; Open Approved websites highlights the row; Ask me now)
  - Block/Remove explanation and tooltips in Approved websites
- **Performed By:** Claude Opus 5.5 (Anthropic) / Project Manager (on-machine test) · **Approved By:** Project Manager

## Update 15:02 UTC: dev5 decisions; old builds deleted with PM permission
- **Disk cleanup (explicit PM permission, "Delete all three"):**
  - deleted `project-builds/dev-builds/Linux-Studio-debian-amd64-0.1.0~dev1/` (revisions 1–3; 1 defective, 2 superseded, 3 replaced by dev2–dev4)
  - deleted `version-control/runtime/2026-11-25_1516/` and `…_1830/` (the oldest two runtime backups)

  Build logs, changelogs and the newest runtime backup (`…_2235`) are kept. Free space went from 5.8 GB to 9.9 GB.
- **Found during dev5 testing:**
  - The in-app browser tab works inside the sandbox, and its traffic goes through the approval proxy (example.com's last-used time updated when the tab opened).
  - Links opened **by extensions** skip the editor's configured openers and go to a "system browser" (`xdg-open`), which doesn't exist in the sandbox.
  - So do `linux-studio://` sign-in callbacks. That's why Cline-style sign-ins can't complete.
- **PM decisions:**
  - Add a Linux Studio `xdg-open` inside the sandbox plus a tiny built-in link-router extension: http(s) links go to the in-app tab, `linux-studio://` goes back to the
    waiting extension, and other schemes are refused.
  - Add the free Noto fonts (core + CJK; about 134 MB installed) to the private runtime.
- **Performed By:** Claude Opus 5.5 (Anthropic) · **Approved By:** Project Manager
