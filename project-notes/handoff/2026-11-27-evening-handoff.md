# Linux Studio handoff, 2026-11-27 evening (paused at 14:20 UTC)

Written by Claude Opus 5.5 (Anthropic) for the Project Manager (PM) and the next agent. **This is the current handoff.** It continues
[`2026-11-27-handoff.md`](2026-11-27-handoff.md) (the morning handoff, still valid for everything before the Studio Browser work).
Before doing anything, read `/guidelines` (as `AGENTS.md` requires).

- **Branch:** `dev`, in sync with GitHub, working tree clean after this handoff's commit.
- **Nothing is running:** no builds, test displays (Xvfb/Xephyr), browsers, proxies, download links or open ports.
- **Where to look:** the plan's **"Studio Browser"** section in [`project-notes/plan.md`](../plan.md) has every PM decision and the step list.
  The full history of today's browser work is in [`project-changelog/2026-11-27/linux-studio-private-browser.md`](../../project-changelog/2026-11-27/linux-studio-private-browser.md).

---

## 1. Where the project stands

| Area | State |
|---|---|
| Phases 0–6, dev4, dev5, dev6-2 | ✅ Done and PM-tested on Mint (unchanged) |
| Network inbox + videos staying full screen | ✅ Committed, **not yet in a package** (goes into dev8) |
| **Studio Browser** (the private browser; was "Firefox private browser") | 🚧 **Steps 1–2 done, step 3 designed and approved, not started** |
| dev8 | ⏸ On hold until the Studio Browser is ready (PM) |
| Official editor build (GitHub workflow) | ⚠ The PM still needs to re-run "Build Linux Studio editor" on `dev` (unchanged; see the morning handoff §3.3) |
| Phase 7 (game development support) | 📋 Planned only |

**Installed on the PM's Mint machine:** dev6-2.

---

## 2. What was done today (afternoon)

### 2.1 PM decisions (all recorded in the plan and changelog)
- **Engine:** Firefox ESR from Debian's signature-checked archive, but **shown to users only as "Studio Browser"**. No Firefox branding in
  anything Linux Studio shows.
- **Settings reorganized into pages with a side list** (mockup screen 9, revision 6, approved):
  - General (Clipboard, Display)
  - **Studio Browser** (new), with Privacy: Remember logins, cookies and passwords (**off**) and Safe Browsing (**off**). Two sub-pages:
    - **Web Links:** Studio Browser (**default**) or Linux Studio tab
    - **Extensions:** uBlock Origin, NoScript, ClearURLs, Bitwarden, **all on**
  - Performance (CPU and memory)
  - Editor extensions (signatures and size limit)
  - Network & tools (Approved websites, Network inbox, Toolchains)
  - Your data
- **The browser sees only `project-folder/Downloads`.**
- **Bitwarden:** the Mozilla-signed build is accepted, including its **Bitwarden License (not open source)** as an exception. The GPL build
  would be unsigned, which would mean turning off add-on signature checks.
- **Forget mode:** a fully clean profile on every start (NoScript's welcome tab and a Bitwarden login each time are accepted).
- **Mozilla remote settings: allowed** (certificate revocation lists, malicious-extension block list). Per-site OCSP lookups off.
- **Rebranding added to the plan** as step 4 (see §3).
- **Command:** `linux-studio --studio-browser`.
- **Step 3 design approved**, including: links whose sign-in return address is `localhost`/`127.0.0.1` open in the Linux Studio tab.

### 2.2 Built, tested and pushed
| Commit | What |
|---|---|
| `6f994b5` | Mockup screen 9 (first version) and the changelog |
| `85be154` | **Step 1:** runtime with `firefox-esr` 153.8.0esr-1~deb13u1 and `webext-ublock-origin-firefox` 1.67.0, plus Debian's `trixie-security` archive (`scripts/build-runtime.sh`). Mockup screen 9 revision 6; screen 5 gains the Network inbox… button |
| `cbf8541` | **Step 2:** `scripts/fetch-browser-extensions.sh` (NoScript 13.6.39, ClearURLs 1.28.0, Bitwarden 2026.11.0, pinned SHA-256), `src/browser/make_policies.py` (locked `policies.json`), `tests/studio-browser-test.sh` |
| `6bc31a9` | OCSP off with remote settings kept; the Studio Browser section in `plan.md` |
| (this commit) | Step 3 design in `plan.md`, this handoff, changelog |

- **Tests:** `tests/studio-browser-test.sh` **15/15**. All other suites passed on the new runtime: isolation 21, network 23, toolchains 13,
  remove-data 20, vsce-sign 15, link-router 32, proxy and toolchain unit tests. x11-clipboard was 11/11 when run on its own (8/11 under load,
  the known timing issue).
- **Backups:** `version-control/scripts/2026-11-27_1308/` (old `build-runtime.sh`), `version-control/browser/2026-11-27_1405/`
  (`make_policies.py` before OCSP), and the previous runtime in `version-control/runtime/2026-11-27_1308/` (ignored by git).
  **Nothing was deleted.**

### 2.3 Research findings (details in the changelog)
- None of NoScript, ClearURLs or Bitwarden is in Debian. All three are Mozilla "Recommended", Mozilla-signed, and showed no tracking code.
  ClearURLs updates its rules from `rules2.clearurls.xyz`; Bitwarden contacts its vault servers and `icons.bitwarden.net`.
- Debian's engine build doesn't force add-on signatures by itself (`MOZ_REQUIRE_SIGNING: false`), so the policy locks
  `xpinstall.signatures.required` on. Extensions in the runtime's read-only system folder (Debian's uBlock) load unsigned, as Debian intends.
  **Point this out in the security review.**
- The policy file must be mounted as a whole `distribution/` folder (the runtime is read-only, so a single file can't be mounted). That
  replaces Debian's `debsearch.xml` search entry.
- **Branding:** "Firefox" appears about 690 times in 72 text files. 648 come from one central file (`localization/en-US/branding/brand.ftl`
  and `chrome/en-US/locale/branding/brand.properties` in `browser/omni.ja` and `omni.ja`), and 18 are hard-coded. Screenshots also showed a
  "Make default" card with the fox mascot in the browser's Settings, and the add-on site's search box on the Add-ons page.
- **Link hand-off:** a second `firefox-esr --new-tab URL` reaches the running browser **only with a private D-Bus inside the browser sandbox**
  (`dbus-run-session`) **and a real display** (headless never hands off).

---

## 3. Next steps, in order (Studio Browser)
The full list with details is in `plan.md` → "Studio Browser" → Steps.

1. **Step 3: launching** (approved design in `plan.md`). Back up `src/launcher/linux-studio`, `src/launcher/xdg-open` and
   `src/network/studio_proxy.py` in `version-control/` before editing. Build the browser sandbox, its window, the proxy sharing, the link hand-off
   and the sign-in return path, plus the localhost rule. Write the tests listed in the plan.
2. **Step 4: rebranding.** When the runtime is built, swap the central branding files and logos in `omni.ja`/`browser/omni.ja` for "Studio
   Browser" and the Linux Studio icon. Fix or hide the 18 hard-coded lines, the fox mascot, the "Make default" card and the add-on search box.
   **Show the PM screenshots for approval.** This needs a runtime rebuild: move `build-cache/runtime/2026-11-27` to `version-control/runtime/`
   first (about 1.9 GB; check disk).
3. **Step 5:** link routing (`xdg-open` and the link router follow Web Links), the **Settings reorganization into pages**
   (`src/settings/settings_window.py`, matching mockup screen 9), and Remove my data's new "Studio Browser logins and history" part.
4. **Step 6:** tests for steps 3–5, then every suite.
5. **Step 7:** jake-lockley security review; fixes need PM approval.
6. **Step 8:** docs (`programming_documentation.md`, `feature_documentation.md`), changelog, `security_log.md`.
7. **Step 9: dev8.** Ask the PM dev or release. Run `scripts/fetch-browser-extensions.sh` before the package build, and add
   `build-cache/browser-extensions` and `src/browser/` to `scripts/build-deb.sh`. dev8 also delivers the network inbox and video full screen.
   PM checks on Mint are listed in the morning handoff §3.2, plus the Studio Browser.

Other open items carry over from the morning handoff: re-run the editor workflow (§3.3), Phase 7, and the pre-release list (licence, icon, man
page, untrusted Xephyr cookie).

---

## 4. Facts for the next agent
- **Runtime:** `build-cache/runtime/2026-11-27/rootfs` (now with the browser engine and uBlock; 1.9 GB). **Extensions:**
  `build-cache/browser-extensions/` (re-create with `scripts/fetch-browser-extensions.sh` if missing). **Editor:** `build-cache/editor/1.148.0/app`.
- **Running the browser by hand for tests:** see `run_browser` in `tests/studio-browser-test.sh`. For anything with windows or hand-off, use
  `Xvfb :57 -nolisten tcp`, a fake passwd/group with `--uid 1000 --gid 1000`, and `dbus-run-session`. Stop Xvfb and every browser afterwards.
- **`about:policies` screenshots** work headless: `firefox-esr --headless --window-size W,H --screenshot FILE URL`. They're useful for
  showing the PM the rebranded pages in step 4.
- **Mockups:** `project-notes/mockups/linux-studio-mockups.html`. Screen 9 is the approved Settings layout and Studio Browser (element ids
  prefixed `s9-`). The PM also saw it as a private preview page; that preview was built from the scratchpad, which is cleared between
  sessions. The repo file is the source of truth.
- **Lessons from today:**
  - check the browser's policy schema and allowed preference prefixes (`Policies.sys.mjs`) before using a policy or preference
  - deletions inside `bash -c` scripts with variable paths are blocked: use new folders or literal paths
  - verify counts before telling the PM (I first said "a few places" said Firefox; it was about 690)
- **Disk:** 6.5 GB free. The step 4 runtime rebuild moves 1.9 GB into backups; a dev build needs 4–5 GB at its peak. Ask the PM before deleting
  any old runtime backup (`2026-11-26_2120`, `2026-11-27_0331`, `2026-11-27_1308`) or build (dev5, dev6, dev7).
- **Standing rules:** plan first and get PM approval; mockups for UI; back up changed files; log everything; secrets scan before each commit; push
  to `dev` only.
