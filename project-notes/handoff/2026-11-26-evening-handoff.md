# Linux Studio handoff, 2026-11-26 evening (paused at 22:38 UTC)

Written by Claude Opus 5.5 (Anthropic) for the Project Manager and the next agent. Read `/guidelines` first, as `AGENTS.md` requires.
This continues `project-notes/handoff/2026-11-26-handoff.md` (the morning handoff and its "Update, later" section).
Branch: **`dev`**, last commit **`0d9ba06`**, pushed. The working tree is clean. No ports, test displays or background jobs are left running.

---

## 1. Where the project stands

| Item | State |
|---|---|
| dev4: signature checker, Remove my data, pop-up on top | ✅ Delivered; PM-tested on Mint |
| dev5: CPU/memory limits, links in an in-app tab, extension sign-ins, refused notice, Noto fonts | ✅ Delivered; PM self-test 11/11 with "Memory limit: 9 GB (enforced by systemd)". PM testing found the bugs fixed in dev6 |
| dev6-1 | Built but **not delivered** (PM: "hold and put both in one build"). Kept |
| **dev6-2** (dev5 + all fixes below) | ✅ Built and checked (install 27/27, lintian 0 errors in our files). **Downloaded by the PM; not yet tested** |
| Official editor build (GitHub workflow) | ⚠ **The PM still needs to re-run "Build Linux Studio editor" on `dev`.** dev builds use a locally patched editor |
| Phase 7, game development support (Unity, .NET, `.sln`) | 📋 Planned only (see the plan file and the morning handoff §4.7) |

---

## 2. Everything done since the morning handoff

### dev4 (commit `74beb1c`) and its fixes
- **Extension signature checker:** `src/editor/vsce-sign/`, our open-source replacement for Microsoft's closed `vsce-sign`. It verifies Ed25519 signatures against the pinned Open VSX key `14ccb407…`.
  - Settings: Check / Don't check, and **Largest extension to check** (256 MB, **512 MB default**, 1 GB, 1.5 GB), passed in through the read-only file `/run/linux-studio/max-extension-mb`.
- **Remove my Linux Studio data:** Settings > Your data, and `linux-studio --remove-my-data`. It refuses while Linux Studio is open, uses the running registry with process start times, never follows links, unlocks read-only folders first, checks ownership and overlap, and never touches the project folder.
- **Approval pop-up:** stays on top on X11, doesn't take keyboard focus, and its 1 s button lock restarts on input. The buttons stay keyboard-reachable (PM).
- **Corners** 30% less rounded across all Linux Studio windows (PM).
- **jake-lockley review** findings 1–7 fixed.
- **PM Mint test passed:** Settings, extension installs (no "Install Anyway"), pop-up on top, Remove my data.

### dev5 (commits `156d1c5`, `dc14136`)
- **CPU and memory** (Settings, `--set-cpu-cores`, `--set-memory-limit`). Defaults: **all cores but one, 75% of memory**. Enforced with `taskset`, plus a systemd user scope (`CPUQuota`, `TasksMax=4096`, `MemoryMax`, `MemoryHigh` 90%, `MemorySwapMax` 25%). If unsupported, it says so in Settings, at start and in the self-test.
- **Links open inside Linux Studio:**
  - `workbench.externalUriOpeners: {"*": "workbench.integratedBrowser"}`
  - the in-sandbox **`xdg-open` shim** (`src/launcher/xdg-open`, mounted at `/run/linux-studio/bin`)
  - the built-in **link router** extension (`src/editor/link-router/`): base64url links, a per-session key in `/run/linux-studio/link-token`, at most 3 links per 10 s
  - the router is a trusted handler in the product overrides
  - **browser patch** `src/editor/patches/browser-callbacks.patch`: only the main page may send `linux-studio://<publisher>.<ext>/…` sign-in callbacks, never to the router
- **"Connection refused" notice** (`src/network/refused_notice.py`): for blocked or unanswered sites, once per site per session, no focus, auto-closes after 20 s, "Open Approved websites…" highlights the row, "Ask me now".
- **Approved websites** explains Block versus Remove. The **Remove-data confirmation** is its own pop-up. **Settings scrolls** to fit 1080p screens.
- **Runtime rebuilt with Noto fonts** (OFL).
- **Claude Code compatibility check closed** (PM: nothing Claude-specific built in).
- **jake-lockley review F1–F7 fixed.** `project-notes/security_log.md` was started (PM approved).
- **Disk cleanup with explicit PM permission:** the dev1 builds and the runtime backups `_1516`/`_1830` were deleted.

### dev6 (commits `7e6d449`, `0d9ba06`): fixes from the PM's dev5 testing
1. **`xdg-open: command not found` in the editor terminal.** The terminal is a login shell, and Debian's `/etc/profile` reset PATH. That also hid **toolchains chosen with "Use this version" since dev3**.
   - Fixed in `src/runtime/overlay/etc/linux-studio/bashrc`; the runtime was rebuilt.
   - The new login-shell tests failed before the fix and pass after it.
2. **Links not opening on Mint even with the full path.** The short-lived editor command (`--open-url`) quit silently, because inner sandboxes aren't allowed on Ubuntu 24.04+/Mint.
   - The PM confirmed it: `--status` printed nothing, `--no-sandbox --status` worked.
   - Fixed with `LS_EDITOR_NO_SANDBOX`, which makes the shim pass `--no-sandbox` the same way the editor itself runs.
3. **Web page full screen took over the whole window** (menus hidden, keys seemed dead; the PM got stuck).
   - **PM decisions:** allow page full screen; end it when leaving the page; then **option B: full screen stays inside its tab**.
   - **Editor patch** `src/editor/patches/browser-fullscreen.patch`: the window is put back at once, and blur or a hidden tab ends the page's full screen (via an isolated world).
   - **Tested:** the menu bar stays, and clicking the side bar ends it. Mockup screen 7 notes say option B was built.
4. **Self-test "X protocol error / BadWindow" lines.** The window-labelling helper is skipped for the self-test, and its errors are ignored.
5. **Private display size:** only `WIDTHxHEIGHT` is taken from the measurement, with a 1280×800 fallback (an X warning had ended up in Xephyr's `-screen` argument).

### Answers given to the PM today
- **Codespace timeout:** nothing lost. Only the scratchpad was cleared: helper scripts, and the copies of the unpatched editor files, which the official workflow rebuild replaces anyway.
- **Double-click on a tab maximises the editor area:** undo it with Ctrl+K then Ctrl+M, or by double-clicking the tab again. It can be turned off under Settings → "double click tab".
- **The giant "Go full screen" button** was only my test page. Real pages have their own small ⛶ (video players). F11 is the editor's own window full screen.

---

## 3. What remains (in order)

1. **PM tests dev6-2 on Mint** (installed from the download; close Linux Studio before installing):
   1. `linux-studio --self-test` passes with no X error lines.
   2. In Linux Studio's terminal, `xdg-open https://example.com` opens in an in-app tab.
   3. **Cline's sign-in:** the page opens in a tab → "Allow 'Cline' to open this URI?" → Open → signed in.
   4. A video's ⛶ fills only its tab; Esc or clicking elsewhere ends it.
   5. Settings: the **CPU and memory** section and the **Remove** pop-up (still unchecked since dev5).
   6. Optional: Toolchains → "Use this version", then `node --version` (or similar) in the terminal shows the chosen version.
2. **Record the PM's results** in `project-builds/logs/Linux-Studio-debian-amd64-0.1.0~dev6-2.md` and the changelog. Fix anything found.
3. **Security review (jake-lockley)** of the dev6 changes, listed in the "dev6 notes" in `project-notes/security_log.md`: the full-screen patch and `LS_EDITOR_NO_SANDBOX`.
4. **PM:** re-run the **"Build Linux Studio editor"** workflow on `dev`. It applies both patches in `src/editor/patches/` (and fails if either no longer applies), adds the signature checker and the link router, and sets the trusted router. Then fetch it (`scripts/fetch-editor.sh`) and build the next dev package from the official editor.
5. **Phase 7: game and software developer support.**
   - Research, then a plan and mockups for PM approval:
     - .NET SDK in Toolchains
     - a vetted Open VSX C# extension
     - Unity as the external script editor (read-only Unity libraries, opening files from Unity, debugging only as a PM security decision)
     - `.sln` support: building with the .NET SDK; Mono for .NET Framework; `EnableWindowsTargeting` for WinForms/WPF; optional Wine; choices for C++ `.vcxproj`
     - Godot, Java/Gradle
   - The outline is in the plan file `~/.claude/plans/sprightly-seeking-seahorse.md`.
6. **Before a release build:** choose a licence, design a real icon, add a man page (the remaining lintian warning), and test an untrusted Xephyr cookie on the PM's desktop.

---

## 4. Useful facts for the next agent
- **Runtime:** `build-cache/runtime/2026-11-26/rootfs` (Noto fonts + login-shell PATH fix). Previous runtimes are in `version-control/runtime/2026-11-26_1511`, `…_2120` and `2026-11-25_2235` (ignored by git).
- **Local editor** `build-cache/editor/1.148.0/app` has these applied locally:
  - the signature checker (`node_modules/@vscode/vsce-sign`)
  - the link router (`extensions/linux-studio-link-router`)
  - product.json `trustedExtensionProtocolHandlers`
  - `out/mainImpl.js` patched for the sign-in callbacks and for full screen

  The official workflow rebuild makes these local patches unnecessary.
- **Delivery:** a one-time link through a scratchpad script (`serve_deb.py`, private port 8765, closes after one download). Recreate it if the scratchpad was cleared.
- **Test suites** (all passing at `0d9ba06`):
  - isolation 18, network 23, toolchains 13, remove-data 20, x11-clipboard 11, vsce-sign 15, link-router 32
  - proxy and toolchain unit tests
  - `tests/deb-install-test.sh` 27, plus a full lintian run counted per tag
- **Lessons:**
  - never cut lintian output with `head`
  - test login shells, not just `bash -c`
  - Ubuntu/Mint have no inner sandboxes, so test that path too
  - test window managers must answer ConfigureRequest
  - `rm` with `$()` paths is blocked: delete literal paths
  - `pkill -f` can match its own command
- **Disk:** about 7 GB free. Never delete builds or backups without explicit PM permission.
