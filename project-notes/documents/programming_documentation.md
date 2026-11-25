# Programming Documentation

This document explains how Linux Studio works and why each part was chosen, in plain language.
It's written so that you can understand and keep working on the project without an AI agent.

> Status (2026-11-25): no application code has been written yet. This document currently holds the
> design and the Phase 1 research results. Code explanations will be added as each part is built.

## What Linux Studio is

Linux Studio is a code editor (built from Code - OSS, the open-source version of VS Code) that runs inside a
**sandbox**. A sandbox is a locked room for a program: it can only see and touch what we put in the room.

- The only real folder in the room is your **project folder**. Inside the app it's always called `/project-folder`.
- The editor, its extensions and its terminal can't see your home folder, other drives or system files.
- The internet is blocked, except for websites you approve. Approved traffic goes through a gatekeeper
  program called the **proxy**.
- Inside the room, the computer has a fake name (`studio`), a fake user (`user`), and no real network
  devices, so extensions can't learn who or where you are. Approved websites can still see your public IP address.

## The parts (planned)

| Part | Language | What it does | Why this choice |
|---|---|---|---|
| Launcher (`src/launcher/linux-studio`) | Bash (shell script) | Builds the sandbox and starts the editor inside it | Bash is on every Linux system and is easy to read line by line |
| Sandbox tool: **bubblewrap** (`bwrap`) | (external program) | Creates the locked room | Small, widely used (Flatpak uses it), free, needs no background service |
| Runtime (`scripts/build-runtime.sh`) | Bash + **mmdebstrap** | Builds a tiny private copy of Linux (Debian) containing the editor's tools | Keeps your real system's files completely out of the sandbox |
| Proxy (`src/proxy/studio-proxy.py`) | Python (standard library only) | Lets traffic through only to approved websites | No extra downloads to trust, and the code is short enough to read in full |
| Toolchains explorer (`src/toolchains-explorer/`) | Python + GTK4 | Window for downloading extra languages and compilers | GTK is the standard Linux desktop toolkit |

## Building the editor (Phase 1c)

**What we build:** "Code - OSS", the open-source version of VS Code that Microsoft publishes on GitHub (MIT licence), renamed to
Linux Studio. We first tried building VSCodium, but VSCodium's privacy patches only fit an older VS Code (1.143.1) that has a
critical security flaw (CVE-2026-120779). Code - OSS 1.148.0 has the fix.

**Is Code - OSS private?** Microsoft's telemetry only works when a secret tracking key is added to the app's settings file
(`product.json`). Code - OSS doesn't include one, so it sends no Microsoft telemetry. We also strip out:
- the Microsoft voice service address (`voiceWsUrl`)
- the GitHub Copilot sign-in and usage addresses (`defaultChatAgent`)
- the permission that lets Copilot use your logins (`trustedExtensionAuthAccess`)

**⚠ Known limit:** Copilot (Microsoft's AI assistant) is woven into VS Code's build itself. We delete the Copilot extension from the finished app (VS Code's build needs it
present while compiling, so it's removed afterwards), switch AI features off with locked settings (`chat.disableAIFeatures`), and the sandbox blocks every website you haven't approved.
Some unused Copilot code still ships inside the app.

**Where it's built:** on GitHub's computers, using **GitHub Actions** (free for public repos). Our Codespace is too small for the
build, which needs about 8 GB of memory.

**How it works, step by step:**
1. `.github/workflows/build-editor.yml` is the recipe. Start it by hand from the repo's **Actions** tab ("Build Linux Studio editor"
   → Run workflow), or with `gh workflow run build-editor.yml` from a terminal logged in as you.
2. It checks that the chosen VS Code version really matches its commit hash, downloads that VS Code source, applies our settings from
   `src/editor/product-overrides.json` (name, Open VSX extension store, removed Microsoft and Copilot addresses), compiles everything, and
   then deletes the Copilot extension from the finished app.
3. It packs the app as `linux-studio-editor-<version>-linux-x64.tar.gz`, with a `SHA256SUMS` fingerprint and a `build-info.json` record.
4. On your machine, `scripts/fetch-editor.sh <run-id>` downloads the result, **checks the fingerprint** (it refuses to install anything
   that doesn't match), and unpacks it into `build-cache/editor/<version>/`. That folder isn't saved in git because it's large.
5. Copy `build-info.json` to `build/editor-version.json` and commit it. That's our permanent record of exactly what was built.

**Telemetry addresses removed:** 13 built-in extensions (git, markdown, typescript and others) and a few core files contain
Microsoft's telemetry "collector" addresses and keys. `scripts/neutralise-telemetry.sh` runs during the build, after packages are
installed and before compiling, and replaces every collector address with `0.0.0.0`, an address that goes nowhere. It covers
`*.data.microsoft.com`, `dc.services.visualstudio.com` and Application Insights. After the build, the same script with `--check` scans
the finished app, including packed archives, and stops the build if any address is left.
- The keys themselves are left in place. They're compiled into the extensions' code, and removing them could crash those extensions.
  With nowhere to send data, they do nothing.
- This is the third layer of protection, after the locked `telemetry.telemetryLevel: off` setting and the proxy.
- It must run before the build. Editing the finished app would corrupt its packed archive (`node_modules.asar`) and break VS Code's
  own file fingerprints.

**Locked settings:** `src/editor/default-settings.json` lists the privacy settings the launcher will force on every start
(telemetry off, updates off, AI off, built-in file dialog, proxy, and the terminal starting in `/project-folder`).

**Safety measures in the recipe:** it only runs when started by hand, has read-only permissions, uses no stored secrets, pins every
external piece to an exact fingerprint, and publishes nothing publicly. The build is kept for 7 days as a download on the run's page.

**To update to a newer VS Code later:** find the new tag's commit hash with
`git ls-remote https://github.com/microsoft/vscode refs/tags/<tag>`, run the workflow with both values, and keep the old build in
`/version-control/editor/<date>/`.

**History:** the earlier VSCodium-based recipe is backed up in `version-control/build-workflow/2026-11-25_1305/`.

No API keys, webhooks or secrets are used. If any are ever added, they'll be explained here and listed in `/.env_example`.

## Phase 1 research results (2026-11-25)

Rules checked: free with no card needed, no hidden tracking, and secure (see `guidelines/Implementation.md` and `guidelines/Security.md`).

### VSCodium (the editor)
- **Licence / cost:** MIT, free.
- **Tracking:** Microsoft's telemetry is off by default. We will still lock these settings off:
  `telemetry.telemetryLevel`, `telemetry.enableCrashReporter`, `telemetry.enableTelemetry`, `telemetry.editStats.enabled`,
  `telemetry.feedback.enabled`, `workbench.enableExperiments`, `workbench.settings.enableNaturalLanguageSearch`,
  `update.mode=none`, `extensions.autoUpdate=false`, `extensions.autoCheckUpdates=false`, `workbench.welcomePage.extraAnnouncements=false`.
- Extensions can send their own tracking data, and VSCodium can't stop that. Our proxy can, by blocking unapproved websites.
- **Security: ⚠ open issue.** The newest VSCodium (1.143.17232, 28 Oct 2026) is built on VS Code 1.143.1.
  A critical VS Code flaw, **CVE-2026-120779** (score 9.6, remote code execution), was published 10 Nov 2026.
  Research says it's fixed in VS Code 1.145.3, but that version number is not yet confirmed. VSCodium has not released a patched build.
  Several other 2026 VS Code CVEs also exist. Keep "Workspace Trust" switched on.

### Open VSX (where extensions are downloaded from)
- **Cost:** free for individuals and open-source projects. Run by the Eclipse Foundation.
- **Privacy:** follows the Eclipse Foundation privacy policy. It logs IP addresses (kept up to 90 days; security logs up to 1 year).
- **Security: ⚠** there were real attacks on this registry in 2026: malicious extensions ("GlassWorm"), 77 fake look-alike
  extensions (July to August 2026), and an account-takeover bug (CVE-2026-13323, fixed June 2026). In October 2026 a fake Claude Code
  extension spread through a *different* registry (Cursor's mirror).
- **What we'll do:** install extensions only by exact publisher and pinned version, and keep `extensions.excludeUnsafes` on.
  That setting downloads a list of known-malicious extensions.
- Claude Code is published there as `Anthropic.claude-code`. It needs an Anthropic account and talks to Anthropic's servers.

### bubblewrap (the sandbox)
- **Licence / cost:** LGPL-2.1, free.
- **Security:** use version **0.12.0 or newer** (fixes CVE-2026-87766, an escape that writes outside the sandbox). Never use "setuid" mode.
- **Ubuntu 24.04 and newer** block sandboxes like this by default. You must install an AppArmor permission profile once, which needs `sudo`.
  The exact command will be in the install instructions.

### mmdebstrap (builds the private Linux copy)
- Free and open source. Its licence is believed to be MIT, but this isn't yet confirmed.
- Can run without root ("unshare mode"). Needs the `uidmap` package and entries in `/etc/subuid` and `/etc/subgid`.

### Electron (the engine inside VSCodium)
- Crash reporting is off unless switched on, and VSCodium leaves it off.
- Whether Chromium's built-in background calls are fully disabled is **not confirmed**. We will rely on the sandbox having no
  direct internet access, and check with a network capture.
- Several 2026 Electron CVEs exist. Which Electron version VSCodium 1.143 uses is **not confirmed**.

### Bundled language tools (Python, Node.js, GCC, Clang, Git)
- All free and open source.
- Turn off their "phone home" checks with `PIP_DISABLE_PIP_VERSION_CHECK=1`, `NPM_CONFIG_UPDATE_NOTIFIER=false` and
  `NPM_CONFIG_AUDIT=false`. The last one stops npm sending your dependency list to the registry.

### Still to confirm
Open VSX full terms of use; mmdebstrap licence; VSCodium Settings Sync behaviour; Electron version in VSCodium 1.143;
the exact fixed version for CVE-2026-120779; Debian security status for each bundled package.
