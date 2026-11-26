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

## The parts

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

**⚠ Known limit:** Copilot (Microsoft's AI assistant) is woven into VS Code's build itself. We delete the Copilot extension and Copilot's ready-built engine (`copilot-sdk`, which
contains telemetry addresses that can't be safely edited) from the finished app. VS Code's build needs them present while
compiling, so they're removed afterwards, switch AI features off with locked settings (`chat.disableAIFeatures`), and the sandbox blocks every website you haven't approved.
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

## Running the editor in the sandbox (Phase 2)

### The private mini-Linux ("runtime"): `scripts/build-runtime.sh`
A tiny Debian 13 system that the sandbox uses as its `/`. It contains the shell, Git, Python, Node.js, C/C++ compilers, fonts,
and the libraries the editor needs. Your real system's files are never used inside the sandbox.
- Built with `mmdebstrap` without root. Every package is checked against **Debian's signing keys** (`debian-archive-keyring`),
  and the build refuses to run without them.
- Everything comes from Debian's "main" section, which by Debian policy contains only free software.
  `build/runtime-manifest.txt` lists every package and version.
- `src/runtime/overlay/etc/linux-studio/bashrc` sets the terminal prompt to show `project-folder/apples $` (no leading `/`) and stops
  pip and npm from contacting the internet on their own.
- Output: `build-cache/runtime/<date>/rootfs/` (about 1.4 GB, not stored in git). Rebuild it with `scripts/build-runtime.sh`.

### The launcher: `src/launcher/linux-studio` (Bash)
This is what you run. Step by step:
1. **Finds your project folder** in `~/.config/linux-studio/config`. If there isn't one, it opens the first-run window.
2. **Safety rules for the folder:** it refuses `/`, system folders, your whole home folder, folders that contain your home folder,
   and Linux Studio's own settings folders.
3. **Creates a fake identity for this launch** in a temporary folder that's deleted when the editor closes:
   computer name `studio`, user `user`, and a new random machine ID every time.
4. **Prepares the settings.** The settings are now written *inside* the sandbox by `src/launcher/apply_settings.py`
   (security review fix, see Phase 3). It keeps your own settings, fills in starting choices from `src/editor/initial-settings.json`
   (such as the theme) only where you haven't chosen, and always re-applies the locked privacy settings from `src/editor/default-settings.json`.
5. **Builds the sandbox with bubblewrap.** Inside, the editor sees only:
   - the mini-Linux, read-only
   - the editor, read-only, at `/app`
   - Linux Studio's private home at `/home/user`, stored on your computer in `~/.local/share/linux-studio/home`
   - your project folder at `/project-folder`

   It has no network, no `/sys`, no special permissions ("capabilities"), and no graphics card unless you use `--gpu`.
6. **Connects the window to your screen.** It uses Wayland. On X11-only desktops it **refuses to start** unless you add `--allow-x11`,
   because on X11 code inside the sandbox could read your screen and type into your other windows.

Useful commands:
- `linux-studio --set-project-folder ~/Code/my-project`: change the project folder.
- `linux-studio --shell`: open a terminal inside the same sandbox, for checking or debugging.
- `linux-studio --gpu`: allow the graphics card, for smoother drawing at a small privacy cost (your GPU model becomes visible).
- `--editor-dir` and `--runtime-dir`: use a development build. The installed defaults are in `/opt/linux-studio/`.

**Saved logins:** the sandbox can't reach your desktop's password keyring, so the editor uses `--password-store=basic`. Logins saved by
extensions are stored in Linux Studio's private folder, obscured but not encrypted.

**Chromium's own sandbox stays on** inside ours, so `--no-sandbox` is never used.

### The first-run window: `src/first-run/first_run.py` (Python + GTK4)
This is the window from the approved mockup, used to choose the project folder. It runs on your desktop, outside the sandbox, before the
editor starts. It doesn't check folders itself; it asks the launcher (`--set-project-folder`), so the safety rules live in one place.
It uses the system Python (`/usr/bin/python3`), because other Python installs such as pyenv or conda usually can't load GTK.

### Why `product.json` still has a Copilot entry
VS Code 1.148 crashes at start-up ("Onboarding requires a default chat agent product configuration") if the `defaultChatAgent` entry is
missing. So we keep it, but every web address in it is replaced with `https://0.0.0.0`, an address that goes nowhere (see
`__neutralise_urls` in `src/editor/product-overrides.json`).

### Tests: `tests/isolation-test.sh`
`tests/isolation-test.sh --runtime-dir <rootfs>` runs 17 checks with throwaway settings folders, so your real settings are never touched.
It checks:
- only sandbox folders are visible, and your home folder isn't
- there are no host passwords, and `/sys` is empty
- the hostname is studio, the user is user, and the only network device is loopback
- there's no internet
- the terminal starts in the project folder, and the prompt shows `project-folder/...`
- there's no GPU, and all capabilities are dropped
- files you make appear in the real project folder
- the machine ID changes every launch
- temporary files are cleaned up, and unsafe folders are refused

## Approved-websites network (Phase 3)

Linux Studio's sandbox has no network of its own. Its **only** way to the internet is a gatekeeper program, the **proxy**, which runs on
your real computer and lets through only websites you've approved.

### How a connection travels
1. A program inside, such as an extension or `pip` in the terminal, connects to `127.0.0.1:3128`. That's the address the sandbox's proxy
   settings (`HTTPS_PROXY` and similar) point to.
2. **`src/network/net_bridge.py`** (inside the sandbox) passes it through a special file, a "unix socket", to the proxy outside.
   The bridge makes no decisions.
3. **`src/network/studio_proxy.py`** (outside) checks the request:
   - Only **`CONNECT <site>:443`** (HTTPS) is accepted. Plain HTTP, other ports, IP addresses and odd names are refused.
   - **Network off** means refuse. A **blocked** site means refuse. An **allowed** site goes ahead.
   - An **unknown** site shows the **approval pop-up**. No answer, or no screen, means refuse.
   - It looks up the site's address itself and **refuses private, loopback, link-local and reserved addresses**, including ones wrapped
     inside IPv6. So the sandbox can never reach your computer, your home network or cloud "metadata" services. It then connects to
     exactly the address it checked.
   - It passes the encrypted data through **without reading it**, and keeps **no log** of traffic. It only stores each site's "last used" time.
   - Open connections re-check the rules every 5 seconds, so blocking a site or turning the network off closes them.
4. There's no address lookup (DNS) inside the sandbox at all: `/etc/resolv.conf` is empty.

### Your list of websites: `~/.config/linux-studio/network.json`
- Stored on your real computer and **never visible inside the sandbox**. Each entry is one **exact** address (approving `api.anthropic.com`
  doesn't approve `www.anthropic.com`), marked Allowed or Blocked. There's also a network on/off switch.
- Saved safely: a lock plus whole-file replacement, readable only by you. A damaged file is treated as "network off".
- Shared rules live in **`src/network/netpolicy.py`**.

### The windows (GTK4, on your desktop, outside the sandbox)
- **Approval pop-up** (`src/network/approval_prompt.py`):
  - The buttons are **Deny** (the site is saved as blocked), **Allow once** (until you close Linux Studio), **Always allow** (saved),
    and **Block all new sites until restart**.
  - **Safety:**
    - Buttons are disabled for 1 second, and Enter does nothing.
    - Site names never wrap, so a name can't look like a different one.
    - Only one pop-up is shown at a time.
    - Closing it, or giving no answer within 60 s, refuses that site until restart.
    - More than 3 new sites waiting at once are refused straight away.
- **Approved websites** (`src/network/sites_manager.py`, opened with `linux-studio --network`): add, block, allow or remove sites,
  and turn the whole network off or on. Changes apply immediately, even while Linux Studio is running.
- All Linux Studio windows share the mockup colours from **`src/common/studio_theme.py`**.

### Security review (2026-11-25)
The project's security agent (jake-lockley) reviewed the network code and launcher. These were fixed:
- **High:** the launcher used to edit the sandbox's `settings.json` from outside, so a planted link could read or overwrite your real
  files. Settings are now written inside the sandbox, and a test with a planted link confirmed the real file stayed untouched.
- Hex-style addresses (`0x8.0x8.0x8.0x8`) slipping past the "names only" rule.
- IPv6 addresses wrapping private IPv4 addresses (NAT64) counting as public.
- Pop-up flooding, and pop-up mis-clicks.
- Odd characters in the port number causing error output.
- Connections that could hang forever.
- Open connections surviving a block.
- X11 keystroke-injection risk, now refused unless you opt in with `--allow-x11`.

Accepted as low risk: an approved name that points at your own public IP address.

### Tests
- `python3 tests/test_proxy.py`: 17 unit tests.
- `tests/network-test.sh --runtime-dir <rootfs>`: 21 end-to-end checks. This needs internet on the host.

### What it can't hide
- Approved sites see your **public IP address**, and whatever the program itself sends inside the encrypted connection, such as login tokens.
- Extensions share one connection, so approval is per website, not per extension.

### Known background connections seen in testing
- `redirector.gvt1.com` is Google, used by the editor engine's spellchecker to download dictionaries.
- `raw.githubusercontent.com` is the download of Eclipse's list of known-malicious extensions, from the `extensions.excludeUnsafes` setting.

- `redirector.gvt1.com` is **pre-blocked** (Project Manager decision). It's on a built-in block list (`BUILTIN_BLOCKED` in
  `src/network/netpolicy.py`), refused silently with no pop-up, and shown in the websites window as "Blocked (built in)". Choosing **Allow**
  there overrides it.
- `raw.githubusercontent.com` asks as normal.

## Toolchains explorer (Phase 4)

A window for adding **extra languages and versions** from their **official publishers**. Open it with `linux-studio --toolchains`.

### How it stays safe
- **The window** (`src/toolchains/explorer.py`, GTK4, on your desktop) never touches the internet or the toolchains folder itself.
- **The downloader** (`src/toolchains/worker.py`) runs in **its own sandbox**:
  - It can write **only** to Linux Studio's toolchains folder (`~/.local/share/linux-studio/toolchains`).
  - It can reach **only** the official sites in `src/toolchains/official-sites.json`, through the Linux Studio proxy in "fixed list" mode.
    There are no pop-ups, and every other site is refused.
  - When you close the window, the downloader and its connection stop.
- **Every download is checked before it's installed:**
  1. The **SHA-256 checksum** must match the publisher's.
  2. The **publisher's signature** must check out against a key stored in `src/toolchains/keys/` (see its README for fingerprints and sources).
     This applies to Node.js, Rust, Java (Temurin) and CMake. Go and python-build-standalone publish checksums only.
  3. It's **unpacked safely**. Archives with absolute paths, `..`, links leaving the folder, device files, or more than 4 GB are refused.
  4. It's built in a staging folder and moved into place **only if every step succeeded**. Otherwise nothing is installed.
- **Inside the editor**, `/toolchains` is **read-only**, so code in your project can't change installed toolchains.

### Security review (2026-11-25, jake-lockley)
Fixed:
- **High:** chosen toolchains came first on the downloader's PATH, so a compromised one could replace `gpgv` and switch off signature checks.
  The downloader now gets a fixed PATH (`/usr/bin:/bin`) and runs every program by full path. A test plants fake tools to prove they never run.
- **Medium:** `gpgv` accepts any key in the keyring, including expired ones. Signatures are now read in machine format (`--status-fd`)
  and must come from a currently valid signing key in `src/toolchains/keys/allowed-signers.json`.
- **Low:** caps on message size between window and downloader and on files per archive (200,000).
- **Info:** Rust's version list is now signature-checked too, so an older release can't be passed off as the newest.

- **Low (fixed later the same day, PM-approved):** Rust's installer script now runs in a **nested sandbox**. It sees no other toolchains,
  has no network, and can write only to its own install folder. The mini-Linux includes `bubblewrap` 0.12.0 for this.

Accepted and documented:
- The official-sites list includes GitHub, which hosts any project's files. The downloader holds no personal data.
- Go and python-build-standalone are checked by SHA-256 only. The window says so.


- **Installed** tab: the bundled tools, plus each extra version with **Use this version** and **Remove**.
- "Use this version" makes that version the one your terminal runs: `/toolchains/<tool>/current/bin` comes first on PATH.
  Restart the editor afterwards. If no version is chosen, the bundled tool is used.
- Go settings inside the sandbox: telemetry is **off** (a settings file is written at every start) and `GOTOOLCHAIN=local`, so Go never
  downloads other Go versions by itself.

### Sources
| Language | Publisher | Checked by |
|---|---|---|
| Python | python-build-standalone (Astral, GitHub) | SHA-256 |
| Node.js | nodejs.org | SHA-256 + Node.js release-team signature |
| Go | go.dev / dl.google.com | SHA-256 |
| Rust | static.rust-lang.org | SHA-256 + Rust release signature |
| Java (Temurin) | adoptium.net / GitHub | SHA-256 + Adoptium signature |
| CMake | Kitware (GitHub) | SHA-256 + CMake release signature |

All are free, and no account is needed. GitHub-hosted downloads pass through GitHub's servers, which see your public IP address.

### Tests
- `python3 tests/test_toolchains.py`: 16 offline tests, covering tampered checksums, bad and wrong-key signatures, path-escape and device-file archives,
  the size limit, the install, use and remove flow, and odd names.
- `tests/toolchains-test.sh --runtime-dir <rootfs>`: 10 end-to-end checks with real downloads (about 100 MB).

### Runtime change
The bundled mini-Linux now includes `gpgv` (signature checking), `xz-utils` and `bubblewrap` (for the nested Rust installer sandbox), and has a `/toolchains` mount point.

## Colour themes (Phase 3b)
- `src/editor/theme/` is a tiny built-in extension with **Linux Studio Dark** and **Linux Studio Light**. It contains colour data only,
  with no code, and is generated from the mockups' palette by `scripts/make-themes.py`.
- `src/editor/initial-settings.json` makes the editor follow your desktop's light or dark setting. Pick another theme any time; your choice is kept.
- The build recipe copies the themes into the finished app and checks that they contain no code.

## Installing Linux Studio: the .deb package (Phase 5)

**Build it:** `scripts/build-deb.sh --type dev --version 0.1.0~dev1 --revision N`. The result goes in
`project-builds/dev-builds/Linux-Studio-debian-amd64-<version>/`, with a summary in `project-builds/logs/`. Old builds are never overwritten;
change the revision number for each new build.

**What gets installed:**
- `/opt/linux-studio/editor` is the editor, and `/opt/linux-studio/runtime` is the private mini-Linux.
- `/opt/linux-studio/share` holds Linux Studio's own scripts and windows.
- `/usr/bin/linux-studio` is the command, and the menu entry includes **Approved websites** and **Toolchains** shortcuts.

**Why there's an AppArmor file (Ubuntu 24.04+):** Ubuntu blocks programs from creating sandboxes by default, because that ability has been
used in kernel attacks. Linux Studio follows Ubuntu's own recommended design (`bwrap-userns-restrict`):
- At install time, a **copy of Ubuntu's bwrap** is placed at `/opt/linux-studio/libexec/bwrap`. It's re-copied automatically whenever Ubuntu updates bubblewrap.
- The profile `/etc/apparmor.d/io.github.seven11ven.linuxstudio` lets **only that copy** build sandboxes. Everything it starts runs with
  **all kernel capabilities denied**, so neither Linux Studio nor anyone misusing the copy gains the powers Ubuntu's restriction protects.
- Because of that, two inner sandboxes can't start on Ubuntu 24.04+, and Linux Studio switches them off automatically (PM decision):
  the editor's Chromium web-content sandbox, and the nested sandbox for Rust's installer. Linux Studio's main sandbox still isolates everything,
  and Rust downloads are still checksum- and signature-checked.

**Check it works on your computer:** `linux-studio --self-test`.

**Removing:** `sudo apt remove linux-studio` deletes the program. Your settings and projects (`~/.config/linux-studio`, `~/.local/share/linux-studio`,
and your project folder) are **never** deleted, not even by `apt purge`.

**Security review (jake-lockley), Phase 5:**
- **Medium-High, fixed (PM chose Ubuntu's restricted design):** the first profile let any program use the bwrap copy to get around Ubuntu's protection.
- **Low, fixed:**
  - a failed removal now restores the bwrap copy
  - an administrator's choice to disable the profile is respected
  - there's a clear message if bwrap is missing
  - an installed Linux Studio never searches PATH for bwrap
  - self-test cleanup
  - a wider secret scan in the build
  - the runtime `/tmp` stays sticky

## Safe X11 desktops and the clipboard setting (Phase 6)

**The problem:** on X11 desktops (Linux Mint's Cinnamon uses X11 by default), any program that can talk to your display can read
your whole screen and type into your other windows. Giving that ability to code inside the sandbox would break it.

**The solution, a private display:** on X11, Linux Studio starts **Xephyr**, a small X server from the X.org project that shows up as
**one window titled "Linux Studio"** on your desktop. The editor draws inside it and can only see or type into that window.
- Xephyr runs in **its own sandbox**: it sees your display socket and its own socket folder, not your files.
- The private display is protected by a **fresh random password ("cookie")** every launch.
- Its **fake-keyboard feature (XTEST) is switched off**, so nothing inside can type keys.
- A tiny window manager (`matchbox-window-manager`, in the runtime) keeps the editor filling the window when you resize it.
- On Wayland nothing changes, because Wayland already keeps apps apart. `--allow-x11` is no longer needed.
  The old direct mode exists only as `--unsafe-direct-x11` and isn't recommended.

**The clipboard bridge** (`src/display/clipboard_bridge.py`, in its own sandbox) moves **text only** (up to 1 MB) between your desktop
and Linux Studio, depending on the **Clipboard setting**:
- **Paste only (default):** your desktop clipboard is handed over **only at the moment you really paste** inside the Linux Studio window
  with Ctrl+V, Ctrl+Shift+V, Shift+Insert, or middle-click.
  - "Really" means real keyboard or mouse input. The bridge watches the private display's *raw input events*, which programs can't fake.
  - Background reads get nothing, and text you copy inside Linux Studio stays inside.
- **Both directions:** works like a normal app. Code inside could read anything you copy elsewhere, which the setting window warns about.

**Settings window:** `linux-studio --settings` (also in the app menu) shows the Clipboard toggle and the display mode.
- Settings live in `~/.config/linux-studio/config` (`CLIPBOARD=paste-only|both`).
- They're **outside the sandbox**, so nothing inside can change them.
- Only the launcher writes them (`--set-clipboard`), and changes apply immediately.

**Check it:** `linux-studio --self-test` on an X11 desktop adds three checks:
- only the private display is visible
- the private display is running
- there's no fake keyboard

The automated test `tests/x11-clipboard-test.sh` checks the bridge (9 checks).

## Look fixes (Phase 6, after the screenshot gallery)
- **Desktop windows follow your light or dark setting** like the editor does (`src/common/studio_theme.py` asks the desktop's colour-scheme setting).
- **Editor branding:** the Linux Studio icon in the title bar and window, plus an LS watermark in the empty editor (`src/editor/branding/`).
- **Unused AI side panel hidden:** VS Code's built-in welcome is replaced by a short **Get started with Linux Studio** walkthrough.
  It's data only, with no code.
- **Light theme terminal:** now light, so its hint text is readable.
- **One set of window buttons (2026-11-26):** in the private X11 window your desktop already draws minimise, maximise and close. The editor's own
  copies are hidden there (`window.controlsStyle: hidden`, set by `src/launcher/apply_settings.py` only when `LS_PRIVATE_X11=1`). On Wayland the
  setting is removed again, because there the editor's buttons are the only ones. Reason: the editor's "minimise" could hide it inside the private
  display, where there is no taskbar to bring it back.
- **Linux Studio icon on every window (2026-11-26):**
  - The small GTK windows (Settings, Approved websites, Toolchains, the pop-up, first-run) use the installed LS icon (`APP_ICON` in
    `src/common/studio_theme.py`).
  - The main window is Xephyr's, which calls itself "Xephyr" with no icon. `src/display/window_label.py` runs right after Xephyr starts, in its own
    sandbox that sees only your display socket. It sets the window's class to `linux-studio-editor` (the menu entry's `StartupWMClass`) and its icon
    (`src/display/icons/ls-*.png`), then exits. It's cosmetic: if it fails, Linux Studio still works.

## Extension compatibility check: Claude Code (closed 2026-11-26)
The PM tested the Claude Code extension inside Linux Studio as an example of a demanding extension (signs in, uses a website, runs commands,
edits files). **Nothing Claude-specific is built into Linux Studio:** no pre-approved sites, no special permissions, no special code. It follows
the same rules as every other extension.
- **Result:** it works.
  - It installed from Open VSX, under the verified "Anthropic" namespace.
  - It runs inside the sandbox and sees the folder only as `/project-folder`.
  - It used git in the sandboxed terminal.
- **Websites it asked for:** `api.anthropic.com` (needed for it to work), plus `github.com` when cloning a repository. Both went through the normal approval pop-up.
- **What it uncovered:** the approval pop-up could hide behind the Linux Studio window, making the extension look stuck. Fixed for everyone in dev4 (the pop-up stays on top).
- **Not needed:** an extension-specific sign-in workaround. If an extension ever needs to open a web page in your real browser, that becomes a general
  feature ("Open link in my browser"), designed with a mockup first.

## Extension signatures, Remove my data, pop-up on top (dev4, 2026-11-26)

### Extension signature checker: `src/editor/vsce-sign/`
- **Why:** the editor checks each extension download by loading a module called `@vscode/vsce-sign`. Microsoft's version is closed source and isn't part
  of Code - OSS, so without a replacement every install said "Signature verification was not executed".
- **What ours does** (JavaScript, Node's built-in tools only, no network, no telemetry):
  1. Opens the signature archive (`.sigzip`) Open VSX publishes for every extension. It contains `.signature.sig`, a 64-byte Ed25519 signature over the
     downloaded `.vsix` file, and `.signature.manifest`, the package's size and SHA-256. Strict limits are applied: archive at most 16 MB, at most 16 entries,
     and no encrypted or oddly compressed entries.
  2. Checks the download's size and SHA-256 against the manifest.
  3. Checks the Ed25519 signature against **Open VSX's public key, pinned in the file**: key id `14ccb407-4e79-41ed-be5a-6d608325c45a`, key SHA-256
     `ffd108d0…4b623`. Pinning means a tampered server can't hand us its own key.
- **Results:** anything except "Success" makes the editor refuse the install and show its prompt with **Install Anyway** (PM decision). Unsigned extensions are
  refused the same way, because the editor's store settings declare every Open VSX extension signed.
- **Setting:** Settings > Extension signatures, stored as `EXTENSION_SIGNATURES=check|off` in `~/.config/linux-studio/config`. The launcher passes it in as
  `LS_VERIFY_EXTENSIONS`, and `apply_settings.py` writes `extensions.verifySignature`. It applies at the next start.
  Known limit: code inside Linux Studio could switch it off in the editor's own settings until the next start.
- **Size limit ("Largest extension to check"):** 256 MB, 512 MB (default), 1 GB or 1.5 GB, stored as `EXTENSION_SIZE_LIMIT_MB`.
  - **Why there's a limit:** the whole package must be in memory to check an Ed25519 signature.
  - **How it reaches the checker:** the launcher writes the value into a **read-only** file inside the sandbox, `/run/linux-studio/max-extension-mb`, which
    code inside can't change. The checker reads it from there.
  - **What happens above it:** bigger packages are refused, with Install Anyway.
- **Hardening from the security review:**
  - Only `.signature.sig` (exactly 64 bytes) and `.signature.manifest` (at most 8 MB) are ever unpacked, so "zip bomb" archives are refused.
  - The package is read through one open file handle with a byte limit.
  - A 3,000-case fuzz run caused no crashes and peaked at about 150 MB.
- **Build:** the editor workflow copies the two files into `resources/app/node_modules/@vscode/vsce-sign`.
- **If Open VSX changes its key:** installs start showing the refusal prompt. Add the new key to `PINNED_KEYS`, keeping the old one while older versions still use it.
- **Tests:** `tests/vsce-sign-test.sh` runs 11 cases against real Open VSX files: genuine, one byte changed, forged, missing or malformed signature, broken or overfilled archive.

### Remove my Linux Studio data
- Settings > Your data (a confirmation card with tick boxes), or `linux-studio --remove-my-data` in a terminal (asks, then you type `remove`).
- **Parts:**
  - `extensions`: the private home `~/.local/share/linux-studio/home`, which holds extensions, editor settings and logins
  - `toolchains`: `~/.local/share/linux-studio/toolchains`
  - `settings`: `~/.config/linux-studio`, which holds Settings choices, approved websites and the project folder choice

  The project folder itself is never touched.
- **Safety:**
  - It refuses while any Linux Studio is running. Each running launcher registers its process number in `~/.local/share/linux-studio/running/`.
    A lock file wasn't used because an open file would be passed into the sandbox and reveal its real path there.
  - It deletes only real folders at their exact expected paths. Anything that is a link, or reached through a link, is left alone.
  - It uses `rm --one-file-system`.
- **Read-only folders:** these (Go's module cache, or ones locked on purpose by code inside) are made writable for you first. `find` doesn't follow links
  and stays on one disk.
- **Further guards:** it refuses folders owned by someone else, and refuses if the settings and data folders overlap. Running entries store the
  process start time, so a reused process number never counts as running.
- **Tests:** `tests/remove-data-test.sh` (20 checks, including the size-limit setting).

### Approval pop-up stays on top (X11)
- `src/common/window_attention.py`: after the pop-up appears, it asks the window manager to keep it above other windows (`_NET_WM_STATE_ABOVE`) and flash
  it (urgency hint). It deliberately does **not** take keyboard focus.
- **Buttons:** they unlock only after the pop-up has been on screen, untouched, for 1 second. The wait restarts when the window appears or is activated, and
  on any key press or click while the buttons are locked. Typing or clicking meant for the editor therefore can't approve a site, even with the pop-up
  on top. Once unlocked, the buttons work by keyboard as normal (PM decision).

### Flatter corners (PM decision, 2026-11-26)
All Linux Studio desktop windows use corners 30% less rounded: 4 px instead of 6 px, and pills 7 px instead of fully round. They're set in
`src/common/studio_theme.py`, and the mockups use the same values.
- It does nothing on Wayland.

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
