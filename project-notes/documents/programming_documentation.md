# Programming Documentation

This document explains how Linux Studio works and why each part was chosen, in plain language.
It's written so that you can understand and keep working on the project without an AI agent.

> Status (2026-11-25): no application code has been written yet. This document currently holds the
> design and the Phase 1 research results. Code explanations will be added as each part is built.

## What Linux Studio is

Linux Studio is a code editor (based on VSCodium, the open-source build of VS Code) that runs inside a
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

## Building our own VSCodium (Phase 1b)

**Why:** the official VSCodium download was older than a critical security fix (CVE-2026-120779). So we build VSCodium ourselves
from a fixed VS Code release.

**Where it's built:** on GitHub's computers, using **GitHub Actions**. It's free for public repos, and VSCodium builds its own releases
the same way. Our Codespace is too small for the build (it needs a lot of memory).

**How it works, step by step:**
1. `.github/workflows/build-vscodium.yml` is the recipe. Start it by hand from the repo's **Actions** tab ("Build VSCodium (patched)"
   → Run workflow), or with `gh workflow run build-vscodium.yml`.
2. **Compile job:** checks that the chosen VS Code version really matches its commit hash, downloads VSCodium's build scripts at a fixed,
   reviewed version, downloads that VS Code source, removes Microsoft's telemetry and branding, and compiles it.
3. **Package job:** turns the compiled code into a runnable app, packs it as `vscodium-<version>-linux-x64.tar.gz`, and writes
   a `SHA256SUMS` fingerprint and a `build-info.json` record.
4. On your machine, `scripts/fetch-vscodium.sh <run-id>` downloads the result, **checks the fingerprint** (it refuses to install
   anything that doesn't match), and unpacks it into `build-cache/vscodium/<version>/`. That folder isn't saved in git because it's large.
5. Copy `build-info.json` to `build/vscodium-version.json` and commit it. That's our permanent record of exactly what was built.

**Safety measures in the recipe:** it only runs when started by hand, has read-only permissions, uses no stored secrets, pins every
external piece to an exact fingerprint, and publishes nothing publicly. The build is kept for 7 days as a download on the run's page.

**To update to a newer VS Code later:** find the new tag's commit hash with
`git ls-remote https://github.com/microsoft/vscode refs/tags/<tag>`, run the workflow with both values, and keep the old build in
`/version-control/vscodium/<date>/`. If VSCodium's patches fail on a very new VS Code version, use the newest version that works,
as long as it's at least 1.145.3.

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
