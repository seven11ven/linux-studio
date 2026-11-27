# Linux Studio: dev6 security review fixes (dev7)

- **Date:** 2026-11-27 · **Time:** about 03:15–03:30 UTC
- **Performed By:** Claude Opus 5.5 (Anthropic), via Claude Code. Review by jake-lockley (Claude Opus 5.5).
- **Approved By:** Project Manager ("fix all", delete the stray files, no cooldown)

## PM test of dev6-2 (Linux Mint)
- **Working:** Cline's sign-in through the in-app tab, and the network approval pop-ups (PM: "so far the browser works"). The remaining checks are in progress.

## Changes
- **Full-screen patch** `src/editor/patches/browser-fullscreen.patch`:
  - no user gesture on exit (D6-1)
  - the window's full-screen state is followed from its events (D6-3)
  - full screen is ended at once if it starts after the page lost focus (D6-4)
  - the editor's named world id is used (D6-8)

  The local build was updated to match. The previous patch is in `version-control/editor-patches/2026-11-27_0328/`.
- **Launcher:** internal variables are cleared at start (D6-2), and PATH is joined safely (D6-6).
- **Runtime:** PATH set-up moved to `/etc/linux-studio/path.sh`, loaded by bashrc and `/etc/profile.d` (D6-6/D6-7). `scripts/build-runtime.sh` gained a
  profile.d hook. The runtime was rebuilt (`2026-11-27`), and the previous one moved to `version-control/runtime/`.
- **Removed** the three stray VS Code source files from the repo root (D6-5; my mistake in commit `7e6d449`).
- **Tests:** isolation gained three checks (bash -lc, empty PATH, decoy SELFTEST_DIR).
- **Backups:** `version-control/{launcher,linux-studio,scripts,editor-patches}/2026-11-27_0328/`.
- **Security log** updated (`project-notes/security_log.md`).
- **Build:** dev7-1. See `project-builds/logs/Linux-Studio-debian-amd64-0.1.0~dev7-1.md`.

## Update 03:52 UTC: PM results and decisions
- **dev6-2 PM-tested on Mint:**
  - `xdg-open` in the terminal works
  - video full screen stays inside its tab
  - Cline's sign-in and the approval pop-ups work
- **New feature approved: network inbox** (mockup screen 8): a small notice + inbox window + editor status-bar "🌐 N waiting"; requests expire after 10 minutes. Next build after dev7.
- **Planned (research first): a hardened, telemetry-free Firefox-based private browser** as its own phase after the inbox.
- **Performed By:** Claude Opus 5.5 (Anthropic) / Project Manager (tests and decisions) · **Approved By:** Project Manager

## Update 03:59 UTC: disk cleanup (explicit PM permission)
- **Deleted, as the PM selected:**
  - the dev2, dev3 and dev4 build folders
  - the dev6-1 package (never delivered; its line was removed from that folder's `SHA256SUMS`)
  - the runtime backups `version-control/runtime/2026-11-25_2235` and `2026-11-26_1511`
- **Kept:** all build logs and changelogs; dev5, dev6-2 and dev7; the runtime backups `2026-11-26_2120` and `2026-11-27_0331`. Free space went from about 3 GB to 8.4 GB.
- **Performed By:** Claude Opus 5.5 (Anthropic) · **Approved By:** Project Manager
