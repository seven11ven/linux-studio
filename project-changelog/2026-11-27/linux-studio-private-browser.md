# Linux Studio: private Firefox browser (blocks dev8)

## Update 13:10 UTC: PM decisions and mockup screen 9 approved
- **Date:** 2026-11-27 · **Time:** about 12:55–13:10 UTC
- **Performed By:** Claude Opus 5.5 (Anthropic), via Claude Code
- **Approved By:** Project Manager ("Looks good to me")

### PM answers to the four open questions (deferred earlier today)
1. **Browser:** Firefox ESR from Debian's signature-checked security archive (not LibreWolf).
2. **Where web links open:** a Settings choice, **defaulting to the private browser**. "Linux Studio tab" keeps the current in-editor tab.
3. **Logins and history:** a Settings choice, **defaulting to "Forget when closed"**. "Remember" keeps them in Linux Studio's private data.
4. **uBlock Origin:** yes, from Debian (`webext-ublock-origin-firefox`), always on.

The PM also accepted the proposed terminal command `linux-studio --private-browser`.

5. **Files (asked with the build plan):** the browser sees **only a `Downloads` folder inside the project folder**, nothing else.

### Changes
- **Mockup screen 9, "Private browser"**, added to `project-notes/mockups/linux-studio-mockups.html`:
  - the Settings section (Open web links in, Logins and history, browser summary, Open private browser)
  - the example of a link opening: an editor link, then the Network inbox, then the browser or the Linux Studio tab
  - the "Linux Studio · Private browser" window (address bar, uBlock counter, a strip saying whether it forgets or remembers)
  - the Remove my data pop-up with the new tick box "Private browser logins and history"
  - The "new" label moved from screen 8 to screen 9. Screens 1–8 are unchanged.
- The PM reviewed a private preview page of screen 9 before it was added to the repo. It used example sites only and nothing from the repo except the mockup styles.

### Impacts
- Documentation and mockups only. No application code, runtime or package changed, so no `version-control/` backup was needed.
- **Next:** a build plan for PM approval: runtime rebuild with Firefox ESR and uBlock Origin (backed up first), the policy file, launcher and link-routing
  changes, Settings, Remove my data, tests, a jake-lockley security review and the docs. Then dev8.

## Update 13:20 UTC: step 1, runtime rebuilt with Firefox ESR and uBlock Origin
- **Performed By:** Claude Opus 5.5 (Anthropic), via Claude Code · **Approved By:** Project Manager ("you may start with step 1")
- **Changes:**
  - `scripts/build-runtime.sh` adds `firefox-esr` and `webext-ublock-origin-firefox`, and Debian's security archive (`trixie-security`,
    checked with the same Debian signing keys).
  - The runtime was rebuilt in 73 s: `build-cache/runtime/2026-11-27/rootfs`, 1.9 GB (was 1.6 GB). `build/runtime-manifest.txt` updated.
- **Versions:** firefox-esr `153.8.0esr-1~deb13u1`, webext-ublock-origin-firefox `1.67.0+dfsg-1~deb13u1`. OpenSSL moved to `3.5.9-1~deb13u1`
  and other packages picked up security fixes from the security archive.
- **Backups:** `version-control/scripts/2026-11-27_1308/build-runtime.sh`, and the previous runtime in `version-control/runtime/2026-11-27_1308/`.
  No backups or builds were deleted.
- **Tests on the new runtime:** isolation 21/21, network 23/23, toolchains 13/13, remove-data 20/20, vsce-sign 15/15, link-router 32/32, proxy and
  toolchain unit tests OK. x11-clipboard was 8/11 in the full run (its known timing problem under load) and **11/11 when rerun on its own**.
  No test processes were left running.
- **Impacts:** the package will grow by about 80–90 MB once Firefox is used. 6.5 GB of disk is free.
  uBlock is installed in Firefox's system extensions folder, which Firefox switches off by default; step 2's policy file has to turn it on.

## Update 13:45 UTC: PM changes to step 2; extensions researched; screen 9 revision 2 for approval
- **Performed By:** Claude Opus 5.5 (Anthropic), via Claude Code · **Approved By:** Project Manager (decisions below); screen 9 revision 2 **awaiting approval**
- **PM decisions:**
  - Step 2 approved, with additions: one **"Firefox Browser"** Settings section holding "Open web links in", a **Remember logins, cookies and
    passwords** on/off toggle, a **Safe Browsing** toggle (**off by default**), and extension toggles for **uBlock Origin, NoScript, ClearURLs and
    Bitwarden** (**all on by default**).
  - The browser sees **only `project-folder/Downloads`**.
  - **Bitwarden:** use the Mozilla-signed build from addons.mozilla.org, accepting its **Bitwarden License (not open source)** as an exception. The
    GPL build is source-only and would be unsigned, which would mean turning off Firefox's add-on signature checks (not allowed by the guidelines).
- **Research** (add-ons downloaded to an empty scratchpad folder, hashes checked, code searched, nothing run):
  - None of the three is in Debian (trixie). All are Mozilla "Recommended" (reviewed) and Mozilla-signed (`META-INF/cose.sig`, `mozilla.rsa`).
  - NoScript 13.6.39 (GPL-2.0, sha256 `15ca1a36…073e`): no tracking. Opens its welcome page on install, which needs suppressing in forget mode.
  - ClearURLs 1.28.0 (LGPL-3.0, sha256 `693601ba…08d1`): no tracking. Rule updates from `rules2.clearurls.xyz` / `kevinroebert.gitlab.io`.
  - Bitwarden 2026.11.0 (Bitwarden License, 28 MB, sha256 `607d6433…0b97`): no analytics libraries (the "sentry"/"amplitude" matches are
    words in its password-strength list; "Datadog" is a business log integration). It contacts its vault servers, `icons.bitwarden.net`, and
    sends audit events only for organization accounts.
- **Mockup:** screen 9 revision 2 (the Firefox Browser section with toggles) shown to the PM as a private preview. It will be added to
  `project-notes/mockups/linux-studio-mockups.html` after approval.

## Update 14:15 UTC: screen 9 revisions 3–6; revision 6 approved
- **Performed By:** Claude Opus 5.5 (Anthropic), via Claude Code · **Approved By:** Project Manager ("then the mockup should be good")
- **PM changes, in order:**
  - Revision 3: show the whole Settings page as built today. Screen 5 lacked the **Network inbox…** button that the app has under More.
  - Revision 4: "Needs organization." Settings becomes **pages with a side list**: General (Clipboard, Display), Performance (CPU and memory),
    Editor extensions (signatures and size limit), Network &amp; tools (Approved websites, Network inbox, Toolchains), Your data.
  - Revision 5: the browser is renamed **Studio Browser**, with **no Firefox branding** in anything Linux Studio shows. It is a side-list group with
    its own page (Privacy: Remember logins, cookies and passwords; Safe Browsing; About) and two sub-pages.
  - Revision 6: the sub-pages are **Web Links** and **Extensions**. The command becomes `linux-studio --studio-browser`.
- **Mockup file** `project-notes/mockups/linux-studio-mockups.html`:
  - screen 9 replaced with revision 6 (element ids prefixed `s9-`; all 47 script references checked)
  - screen 5 gains the Network inbox… button and a note pointing to the new page layout
- **Known limit, told to the PM:** Debian's engine build still says "Firefox" in a few places inside the browser itself (Help › About, some
  about: pages). Removing them would need our own rebranded engine build. No decision yet; the default is to accept them.
- **Impacts:** the Settings window (`src/settings/settings_window.py`) will be reorganized into these pages during the build steps, with the same
  behaviour per section.

## Update 14:40 UTC: step 2, locked policy file and extension switches (built and tested)
- **Performed By:** Claude Opus 5.5 (Anthropic), via Claude Code · **Approved By:** Project Manager (step 2 with the toggle additions)
- **New files** (no earlier versions exist, so there is nothing to back up):
  - `scripts/fetch-browser-extensions.sh`: downloads NoScript 13.6.39, ClearURLs 1.28.0 and Bitwarden 2026.11.0 from addons.mozilla.org at pinned
    versions, refuses any file whose SHA-256 differs, and writes `build-cache/browser-extensions/` (ignored by git). Like `fetch-editor.sh`, it is
    run before a package build, so the package build itself needs no network. No runtime rebuild was needed.
  - `src/browser/make_policies.py`: writes the locked `policies.json` from the Settings choices (remember, Safe Browsing, four extension switches),
    run by the launcher outside the sandbox. It locks: telemetry, studies, Pocket, accounts, feedback, updates, first-run pages, about:config and
    about:profiles off; the proxy to Linux Studio's `127.0.0.1:3128`; DNS over HTTPS off; tracking protection on; downloads to
    `/project-folder/Downloads`; `linux-studio://` links to the link helper; extension signature checks on; and no other extensions.
  - `tests/studio-browser-test.sh`: **15/15** (headless, no network).
- **Findings:**
  - Debian's browser reads the policy from its `distribution` folder. The sandbox mounts a folder holding only `policies.json` there, which replaces
    Debian's extra search-engine entry (`debsearch.xml`).
  - Debian's build doesn't force add-on signatures by itself (`MOZ_REQUIRE_SIGNING: false`), so the policy locks them on. Extensions in the
    runtime's read-only system folder (only Debian's uBlock) load without a Mozilla signature, as Debian intends.
  - Two preferences (`app.normandy.enabled`, `app.shield.optoutstudies.enabled`) aren't accepted by the policy engine. They were removed; the
    DisableFirefoxStudies policy already covers them.
  - The browser still contacts Mozilla's remote-settings service at start, which can't be switched off by policy. Raised with the PM.
- **Open questions for the PM:** remote settings and certificate revocation checks; whether extensions keep their data between sessions in "forget"
  mode (NoScript shows its welcome tab on every fresh install); the remaining Firefox names inside the browser.
