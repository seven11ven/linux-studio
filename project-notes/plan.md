# Linux Studio project plan

> Copied into the repo on 2026-11-27 (PM approval) from the agent's working plan file, so any agent or tool can read it.
> Phases are listed newest-first in places; the **current state and next steps** are always in the newest file in `project-notes/handoff/`.
> Keep this file updated when plans change.

# Plan: Linux Studio — a private, sandboxed code editor

## Context
The Project Manager (PM) wants a privacy-first version of VS Code for Linux:
- The editor and its extensions can't see anything on the computer except **one project folder**.
- The terminal starts inside that folder and shows paths like `project-folder/apples`, never the real host path.
- Extensions that genuinely need the internet (such as Claude Code) can reach **only websites the PM has approved**. They see a fake identity: fake hostname, username, network adapters, MAC address and local IP.
- A **Toolchains explorer** connects to the internet only while it's open, to browse and download extra compilers and runtimes.

Decisions already made by the PM:
- Base editor: VSCodium
- Sandbox: bubblewrap
- Name: **Linux Studio** (App ID `io.github.seven11ven.linuxstudio`)
- Project folder: defaults to `~/LinuxStudio/project-folder`, but **the user can choose where it lives**
- Bundled tools: Python, Node.js, C/C++, Git and a shell
- Masking: allowlist proxy plus fake identity, without Tor
- Mockups: interactive HTML page

## Architecture

```
HOST (your real system)                      SANDBOX (all Linux Studio can see)
────────────────────────                     ──────────────────────────────────
linux-studio launcher (bash)  ──bwrap──▶     /            read-only bundled runtime (own mini Linux)
studio-proxy (Python, stdlib only)           /app         VSCodium (read-only)
  • listens on a unix socket only            /home/user   app-private settings + extensions
  • domain allowlist (host-side file,        /toolchains  extra toolchains (read-only)
    sandbox can NOT edit it)                 /project-folder  ◀── bind of chosen host folder (read-write)
  • approval prompt for new domains          network: loopback only; 127.0.0.1:3128 ─▶ unix socket ─▶ proxy
Toolchains explorer (separate, temporary)    hostname "studio", user "user", random machine-id
```

### 1. Sandbox launcher — `src/launcher/linux-studio`
- Runs `bwrap` with `--unshare-all`, `--die-with-parent`, `--new-session`, `--clearenv`, `--hostname studio`, a new `/proc`, a minimal `/dev`, and **no `/sys`**.
- **Nothing from the host is mounted** except:
  - the bundled runtime (read-only),
  - the chosen project folder, mounted at `/project-folder`,
  - app-private state in `~/.local/share/linux-studio/`,
  - the Wayland display socket. X11 is a fallback only, with a warning, because X11 lets apps snoop on other windows.
- Fake identity files: `/etc/passwd`, `/etc/hostname` and `/etc/machine-id`, the last regenerated randomly on each launch.
- No D-Bus, audio or host home access. File dialogs use VSCodium's built-in dialog, so they only ever show the sandbox's files.
- Project folder location is stored in `~/.config/linux-studio/config`. A first-run dialog lets the user pick it, and `linux-studio --set-project-folder PATH` changes it later.

### 2. Bundled runtime — `scripts/build-runtime.sh`
- Builds a minimal Debian rootfs with `mmdebstrap` (free and open source). It contains bash, coreutils, git, python3 with pip, nodejs with npm, gcc/g++, clang, make, cmake and fonts.
- Because it's a separate rootfs, nothing from the host's `/usr` or `/etc` is exposed.
- Terminal settings:
  - `terminal.integrated.cwd = /project-folder`
  - the bash prompt removes the leading `/`, so it shows `project-folder/apples $`

### 3. VSCodium hardening — `src/vscodium/`
- `product.json` overrides set the name and icon to Linux Studio, use Open VSX as the extension gallery (reached through the proxy), and turn off telemetry, update checks and the crash reporter.
- Locked default settings: no telemetry, no automatic extension updates, the custom file dialog, and `http.proxy=http://127.0.0.1:3128`.

### 4. Network proxy and masking — `src/proxy/studio-proxy.py`
- A small Python HTTP CONNECT proxy using only the standard library, so there are no third-party dependencies to audit.
- It listens on a **unix socket** outside the sandbox. Inside the sandbox, a small bridge exposes it as `127.0.0.1:3128`. The sandbox has no other way out.
- It allows connections only to domains in `~/.config/linux-studio/allowlist` (for example `api.anthropic.com` and `open-vsx.org`). The sandbox can't read or edit this file.
- When a domain isn't on the list, the connection is blocked and the user gets an **approval prompt** on the host with Allow once, Always allow or Deny.
- The proxy logs domain names only, never the content of requests. It shuts down and closes its socket when Linux Studio exits, which follows the "clean up loose ends" rule.
- Masking: inside the sandbox there are only loopback adapters, so there's no real MAC address or local IP. Hostname, username and machine-id are fake. Approved websites still see the PM's **public IP**. This limit will be written in the documentation.

### 5. Toolchains explorer — `src/toolchains-explorer/`
- A separate host-side window that opens its own sandbox with network access **only while it's open**.
- It's limited to official sources, for example python.org, nodejs.org and GitHub releases.
- Downloads are verified against checksums and signatures before being placed in `~/.local/share/linux-studio/toolchains/`. That folder is mounted read-only in the editor's sandbox.
- The network connection closes as soon as the window does.
- UI toolkit is GTK4 via PyGObject. That's the final choice only after the mockups are approved.

### 6. Repo housekeeping (required by the guidelines)
- Create a root `/.gitignore` that excludes build outputs, the downloaded VSCodium, the runtime rootfs, `/project-builds` artifacts and any `.env` files.
- Add `/.env_example` only if a variable is ever introduced. None are planned.
- Keep `project-notes/documents/programming_documentation.md` and `feature_documentation.md` up to date, written for a non-programmer.
- Add a changelog entry per session in `/project-changelog/YYYY-MM-DD/`.
- Save prior versions of changed components in `/version-control/`.

## Phase 6 — Safe X11: private nested display (Xephyr) + clipboard setting

**Context:** the PM's machine runs **Linux Mint (Cinnamon, X11 by default)** with an AMD GPU. The dev .deb passed `--self-test` 7/7 there, but the
editor refuses to start on X11, as designed. On X11, sandboxed code with the X socket could read the screen and type into other windows.
`--allow-x11` works, but it carries that risk. The PM chose to **isolate X11 properly**:
- Linux Studio runs inside its own **Xephyr** nested display: one resizable window, and code inside can see or type into **only that window**.
- Clipboard behaviour is a **setting the user controls**, toggling between **Paste only** and **Both directions**. It's kept outside the sandbox so
  code inside can't change it.

**Checked availability (all free, distro-signed):**
- `xserver-xephyr` 21.1.12 is in Ubuntu 24.04 / Mint 22. It comes from the X.org project, MIT licence.
- `python3-xlib` 0.33 is in Ubuntu 24.04 (pure Python, LGPL).
- `matchbox-window-manager` is in Debian 13, for the runtime.

### How it works
```
Host X11 desktop ──(only Xephyr talks to it)── Xephyr window "Linux Studio"  ← own bwrap sandbox: sees host X socket +
                                                   │ private display :N         its own socket dir; no home, no network
                       clipboard bridge (host) ────┤ (python3-xlib; obeys the Clipboard setting)
Linux Studio sandbox ── sees ONLY display :N ──────┘ matchbox WM inside keeps the editor maximised; no host X socket at all
```
- **The launcher** uses Wayland when available. Otherwise it uses this **nested X11 mode by default**: no more refusal, and `--allow-x11` is no longer needed.
  The old direct X11 mode stays only as `--unsafe-direct-x11`, with the same strong warning. Back up the launcher first.
- **Xephyr** starts with `-resizeable -nolisten tcp -extension XTEST`, plus a private auth cookie, a per-launch socket and a title of "Linux Studio".
  Turning off XTEST stops code from faking keypresses. Xephyr runs in its own bwrap sandbox, which sees only the host X socket and its own
  socket folder. Everything stops when the editor closes.
- **Inside the editor sandbox:** only Xephyr's socket and cookie are mounted, never the host X socket. `matchbox-window-manager` (added to the runtime)
  keeps the editor window filling the Linux Studio window as you resize it.
- **Clipboard bridge** (`src/display/clipboard_bridge.py`, host, `python3-xlib`):
  - **Paste only:** your desktop clipboard is handed to Linux Studio **only at the moment you really paste inside its window** (Ctrl+V,
    Ctrl+Shift+V, Shift+Insert or middle-click). The bridge detects real keyboard and mouse input through the nested display's RECORD
    extension. Faked events can't trigger it, because XTEST is off and events sent by programs aren't real device input. Nothing inside can read your
    clipboard in the background, and copies made inside never leave Linux Studio.
  - **Both directions:** the clipboard is synced both ways, like a normal app. The settings window explains the risk: code inside could read what you
    copy elsewhere.
  - Text only, size-capped, with no files or images in either mode.
- **Setting storage:** `~/.config/linux-studio/config` gets a new `CLIPBOARD=paste-only|both` line. The default is **paste-only**. It's host-only and never
  mounted into the sandbox.
- **Settings window** (`src/settings/settings_window.py`, GTK4, the shared studio theme):
  - a **Clipboard** toggle (Paste only / Both directions, with a plain-language note) and the current **display mode** (Wayland, or Private X11 window)
  - shortcuts to Approved websites and Toolchains
  - opened with `linux-studio --settings` and a new **Settings** menu action
  - changes apply at the next launch, or immediately if the bridge re-reads the setting

  This is new UI, so I'll **add mockup screen 5 to the approved HTML mockup page and get PM approval before building it.**
- **Package:**
  - `Depends` gains `xserver-xephyr` and `python3-xlib`
  - the runtime gains `matchbox-window-manager`; back up and rebuild it
  - new dev build `0.1.0~dev2-1`
- **`--self-test`** gains checks: on X11, nested display isolation works (the sandbox can't connect to the host display), and XTEST is unavailable inside.

### Verification
- **Codespace (Xvfb as the "host" display, with xdotool on the host side):**
  - the editor opens inside the Xephyr window
  - from inside the sandbox, connecting to the host display fails, and `xdotool` typing and the XTEST check fail
  - paste-only: a real paste (xdotool on the HOST, into Xephyr) inserts host text, and a background clipboard read from inside gets nothing
  - both directions: text copied inside reaches the host
  - closing the editor stops Xephyr and the bridge, leaving no processes, sockets or temp files
- **Settings window:** screenshot compared with mockup screen 5. The toggle persists, and the sandbox can't see the config file.
- **Existing suites, package build, clean Ubuntu install test** (with the new Depends) and **lintian**.
- **Security review** by jake-lockley: the Xephyr sandbox, the bridge (the paste-arming logic is the critical part) and the launcher changes.
- **PM test on Mint:** install dev2, run `--self-test`, open the editor in a normal X11 Cinnamon session, try paste in and copy out under both settings.
- **Docs and logs:** docs, feature list, changelog and a build summary. Commit to `dev`.

## Phase 5 — First .deb package (dev build, Ubuntu 24.04+)

**Context:** Phases 0–4 are done on `dev`. The PM wants a **dev build** as a **.deb** to install on **Ubuntu 24.04 / 24.10+**.
That Ubuntu restricts user namespaces through AppArmor (`kernel.apparmor_restrict_unprivileged_userns=1`). Ubuntu 24.04 ships the bwrap
profile only as an unused extra (`apparmor-profiles: /usr/share/apparmor/extra-profiles/bwrap-userns-restrict`), so plain `/usr/bin/bwrap`
can't build the sandbox. The package has to handle this safely, without changing anything for other programs that use bwrap, such as Flatpak.

### Project values (filled in for `guidelines/Linux-Packaging.md`)
- App ID `io.github.seven11ven.linuxstudio` · package `linux-studio` · command `linux-studio` (`/usr/bin/linux-studio`, a link into `/opt`)
- Desktop file `io.github.seven11ven.linuxstudio.desktop` · icon `io.github.seven11ven.linuxstudio`
- `StartupWMClass` is read from the running window with `xprop` during testing, not guessed
- Version `0.1.0~dev1-1`. The tilde makes it sort *before* a future `0.1.0` release. Debian revision 1.
- Build folder `project-builds/dev-builds/Linux-Studio-debian-amd64-0.1.0~dev1/`, with a build summary in `project-builds/logs/`
  (`.gitignore` already excludes the binaries, and logs are committed)
- **Depends:** `bubblewrap`, `python3`, `python3-gi`, `gir1.2-gtk-4.0`, `apparmor`, plus the libraries `ldd` finds for the copied bwrap.
  The editor and runtime are bundled.

### The sandbox permission (AppArmor), done narrowly
- At install time, `postinst` **copies Ubuntu's own `/usr/bin/bwrap`** to `/opt/linux-studio/libexec/bwrap`. That's the distro-maintained, patched
  binary, and nothing is downloaded.
- A **dpkg trigger** on `/usr/bin/bwrap` re-copies it whenever Ubuntu updates bubblewrap, so security fixes arrive automatically.
- It installs `/etc/apparmor.d/io.github.seven11ven.linuxstudio` with
  `profile linux-studio-bwrap /opt/linux-studio/libexec/bwrap flags=(unconfined) { userns, }`. That's the same pattern Ubuntu uses for Chrome and
  VS Code, and it grants the permission **only to Linux Studio's copy**, never to the system `bwrap`. It's loaded with `apparmor_parser -r`
  when AppArmor is active, and skipped quietly otherwise.
- **The launcher** uses `/opt/linux-studio/libexec/bwrap` when present, and falls back to the system bwrap in development.
- **Removal:** `prerm` and `postrm` unload the profile and delete the copied binary on `remove` and `purge`, but **never on `upgrade`**.
  User data in `~/.config/linux-studio` and `~/.local/share/linux-studio` is never touched, not even on purge, as the guidelines require.

### Package layout (`packaging/deb/`)
- `/opt/linux-studio/editor/`: the verified Code - OSS build from `build-cache/editor/1.148.0/app`
- `/opt/linux-studio/runtime/`: the Debian runtime, with setuid and setgid bits stripped because nothing in the sandbox needs them
- `/opt/linux-studio/share/`: a copy of `src/` (launcher, network, toolchains, first-run, common, editor settings and theme), which is where the launcher already looks
- `/usr/bin/linux-studio` → `/opt/linux-studio/share/launcher/linux-studio`
- `/usr/share/applications/io.github.seven11ven.linuxstudio.desktop` with menu actions **Approved websites** (`--network`) and **Toolchains** (`--toolchains`)
- `/usr/share/icons/hicolor/scalable/apps/io.github.seven11ven.linuxstudio.svg`: a **placeholder icon** for the dev build (an "LS" monogram in the mockup
  green). A proper icon is designed with a mockup before the release build.
- `scripts/build-deb.sh` assembles everything, writes `DEBIAN/control`, the maintainer scripts and `triggers`, and builds with
  `dpkg-deb --root-owner-group -Zxz`. It refuses to run if the editor or runtime is missing, and checks for leftover secrets or `.git` folders.
  The package is expected to be about 600 to 800 MB.
- **New `linux-studio --self-test`:** starts a sandbox, a nested sandbox and the proxy, and prints PASS or FAIL in plain language. On the PM's real
  Ubuntu 24.04 machine this proves AppArmor and the sandbox work, which the Codespace can't show.

### Verification (guideline checks)
1. `dpkg-deb -c` and `-f`: file list and metadata. `ldd` on the copied bwrap and the editor (inside the runtime) shows no missing libraries.
2. `lintian` and `desktop-file-validate`. The PM installs `lintian desktop-file-utils` with sudo. Every lintian finding is fixed or explained, and none are silenced.
3. **Clean Ubuntu 24.04 test** without Docker: an `mmdebstrap` noble environment, running as fake root.
   - `apt install ./linux-studio_*.deb`
   - check the files and the `/usr/bin` link, and run `linux-studio --help` and `--self-test` (as far as a container allows)
   - **upgrade** to a `~dev1-2` test build
   - **remove** and **purge**, then confirm a test user's data survives and nothing is left in `/opt` or `/etc/apparmor.d`
4. GUI under Xvfb from the installed layout: the editor opens, and `xprop` confirms `StartupWMClass`.
5. Re-run all test suites against the installed paths.
6. **On the PM's Ubuntu 24.04 machine:** install, run `linux-studio --self-test`, then launch from the menu. I'll give exact steps.
   The AppArmor part can only be proven there, and I'll say so plainly.
7. **Security review** by jake-lockley of the maintainer scripts, the AppArmor profile, the trigger and the build script, before commit.
8. Docs, changelog, feature list, and a build summary in `project-builds/logs/`. Commit to `dev`; the `.deb` itself is not committed.

## Phase 4 — Toolchains explorer (mockup screen 4)

**Context:** Phases 1 to 3 are done and on `dev`. Linux Studio ships Python 3.13, Node.js, GCC/Clang, Git and a shell in its private mini-Linux.
The PM wants a window for adding **extra languages and versions from official sources**. It connects to the internet **only while it's
open**, and every download is verified before installing. Mockup screen 4 is approved, with extra buttons approved below.

**PM decisions (2026-11-25):**
- Python comes from **python-build-standalone** (Astral, GitHub releases, SHA-256 checksums).
- Verification: **the checksum is always required, and the signature is also required when the publisher signs its files.** Keys are stored in our repo.
- The Installed list gets **"Use this version"** and **"Remove"** buttons, an approved addition to the mockup.

### Sources (all free, official publisher channels)
| Tool | Version list | Download | Checksum | Signature |
|---|---|---|---|---|
| Python | GitHub releases API, astral-sh/python-build-standalone | GitHub release asset `…x86_64-unknown-linux-gnu-install_only.tar.gz` | release `SHA256SUMS` | none published |
| Node.js | `nodejs.org/dist/index.json` | `nodejs.org/dist/vX/node-vX-linux-x64.tar.xz` | `SHASUMS256.txt` | `SHASUMS256.txt.sig`, Node release keys |
| Go | `go.dev/dl/?mode=json` | `dl.google.com/go/…linux-amd64.tar.gz` | SHA-256 in the JSON | none published |
| Rust | `static.rust-lang.org/dist/channel-rust-stable.toml` | `rust-X-x86_64-unknown-linux-gnu.tar.xz` | `.sha256` | `.asc`, Rust release key |
| Java (Temurin) | `api.adoptium.net` | GitHub-hosted asset | API SHA-256 | `.sig`, Adoptium key |
| CMake | GitHub releases, Kitware/CMake | `cmake-X-linux-x86_64.tar.gz` | `cmake-X-SHA-256.txt` | `.asc`, CMake release keys |

Before writing any adapter I'll read each publisher's download and verification docs in full, as the budget rule requires. Each publisher key is
fetched from its official page, its fingerprint is cross-checked against a second official source, and the key is stored in
`src/toolchains/keys/` along with the source URL and fingerprint.

### How it works
```
Explorer window (GTK4, host)  ──JSON over stdin/stdout──▶  worker (Python, INSIDE a separate bwrap sandbox)
  closes → worker + its proxy stop                            • writes ONLY to the toolchains folder (staging, then atomic rename)
                                                              • network ONLY via studio_proxy in "fixed list" mode:
                                                                official-sites.json, no pop-ups, private IPs still refused
Editor sandbox: ~/.local/share/linux-studio/toolchains  ──read-only──▶  /toolchains ; PATH gets /toolchains/<tool>/current/bin
```
- Downloads and archive unpacking happen **inside the sandbox**, so a malicious archive can't touch your real files.
  Archives are unpacked with Python's `tarfile` "data" filter, which refuses absolute paths, `..`, links leaving the folder and device files.
  There are size limits on downloads and unpacked files.
- Each install goes to `<tool>/<version>.partial` and is renamed to `<tool>/<version>` only after **checksum, signature and unpacking all succeed**.
  On any failure, the partial folder is deleted.
- "Use this version" sets a relative `<tool>/current` link. The editor sandbox puts `/toolchains/<tool>/current/bin` ahead of the bundled
  tools on PATH. With no `current` set, the bundled versions are used.

### Files
1. **`src/toolchains/explorer.py`** (GTK4, host): mockup screen 4.
   - The green banner reads "Connected to official download sites only…"
   - Sidebar: Installed, Python, Node.js, C/C++ (CMake), and Rust, Go, Java
   - Version tables with Install buttons and progress (Downloading → Verifying → Installed), plus plain-language error messages
   - Installed list: **Use this version** and **Remove**, both new
   - Uses `src/common/studio_theme.py`
2. **`src/toolchains/worker.py`** (stdlib, inside the sandbox): source adapters (version list, download URL, checksum, signature), download through the proxy,
   SHA-256 check, `gpgv` signature check against `src/toolchains/keys/*`, safe unpack, and atomic rename. It sends progress as JSON lines.
3. **`src/toolchains/official-sites.json`**: the fixed list of addresses the worker may reach:
   - nodejs.org, go.dev, dl.google.com
   - static.rust-lang.org, api.adoptium.net
   - api.github.com, github.com, and GitHub's release-download hosts

   I'll confirm the exact redirect addresses while implementing.
4. **`src/network/studio_proxy.py`:** a new `--fixed-allowlist FILE` mode with no pop-ups and no `network.json`. Only listed sites are allowed, and all
   existing safety checks still apply. Back up the file first, and add unit tests.
5. **`src/launcher/linux-studio`:**
   - a new `--toolchains` option that starts the explorer
   - an internal `--toolchains-worker` mode that starts the worker sandbox and its proxy, both stopped when the window closes
   - editor sandbox changes: mount `/toolchains` read-only, extend PATH, and set `GOTELEMETRY=off`, `GOTOOLCHAIN=local`, `JAVA_HOME` and `CARGO_HOME=/home/user/.cargo`

   Back up the file first.
6. **Runtime:** add `gpgv` and `xz-utils` to `scripts/build-runtime.sh` and rebuild. The old runtime is moved to `version-control/runtime/`, ignored by git.
7. **Tests:**
   - `tests/test_toolchains.py` (offline, fixture data):
     - each adapter parses version lists correctly
     - a tampered checksum, a bad signature or a missing signature is rejected and the partial folder is removed
     - archives with `../`, absolute paths, symlink escapes or device files are rejected
     - "Use this version" and Remove behave correctly
   - `tests/toolchains-test.sh` (real network, small downloads):
     - install Node.js LTS and Go through the worker
     - in the editor sandbox's shell, `node --version` and `go version` show the new versions after "Use this version"
     - the worker can't reach `example.com`
     - after closing, no worker, proxy or temp folders are left
   - All existing suites still pass.
8. **GUI check under Xvfb:** screenshots compared with mockup screen 4, plus an install, "Use this version" and Remove done through the window.
9. **Security review:** the jake-lockley agent reviews the worker, the archive unpacking, the fixed-list proxy mode and the launcher changes before commit.
10. **Docs and logs:** programming documentation, feature list and changelog. Commit and push to **`dev`** after asking.

### Known limits (to document)
- Go and python-build-standalone publish checksums only, with no signature. Their HTTPS download protects the transfer, but not against a compromised publisher.
- Extra toolchains use disk space, for example about 200 MB for Java. Remove them from the Installed list.

## Phase 3b — Linux Studio colour themes, matching the approved mockups (PM request 2026-11-25)

**Context:** the PM asked that the editor's home page and project editor use the same look as the approved mockups. At the moment
the editor uses VS Code's default "Dark Modern" theme. The PM chose to ship **both a dark and a light theme, following the desktop's
dark or light setting**.

**Palette, taken from `project-notes/mockups/linux-studio-mockups.html` (the source of truth):**

| Role | Dark | Light |
|---|---|---|
| Background (`--bg`) | `#0f1412` | `#eef1f0` |
| Surface (`--surface`) | `#171e1b` | `#ffffff` |
| Panel (`--panel`) | `#1d2522` | `#f5f7f6` |
| Text (`--ink`) | `#e3ebe7` | `#17201d` |
| Muted text | `#97a59f` | `#5b6762` |
| Lines | `#2c3732` | `#d5dcd9` |
| Accent | `#4cc296` | `#1f7a5c` |
| Accent text | `#06130e` | `#ffffff` |
| Accent soft | `#1c3a2f` | `#dcefe7` |
| Warning | `#f0a950` | `#a35a00` |
| Error | `#f2817a` | `#b3261e` |
| Terminal background | `#0a0e0d` | `#0f1513` |

**Files:**
1. **`src/editor/theme/`**: a small built-in VS Code extension, "Linux Studio Themes" (`package.json` plus `themes/linux-studio-dark.json`
   and `themes/linux-studio-light.json`).
   - **Workbench colours** cover the activity bar, sidebar, editor, tabs, panels, the terminal and its ANSI colours, the status bar, title bar, buttons,
     inputs, lists, badges, notifications, the welcome page and the Restricted Mode banner.
   - **Code colours** use a few token rules built from the same palette: green accent for keywords, muted for comments, amber for strings,
     and so on, so code stays readable.
   - No icons, fonts or anything that runs code. A theme is just colour data.
2. **Workflow `build-editor.yml`:** a new step copies `src/editor/theme/` into
   `VSCode-linux-x64/resources/app/extensions/linux-studio-themes/` before the telemetry check and the archive step. The extensions folder
   isn't covered by VS Code's file fingerprints. Back up the workflow first, as usual.
3. **Default without locking:** add `src/editor/initial-settings.json` with:
   - `window.autoDetectColorScheme: true`
   - `workbench.preferredDarkColorTheme: "Linux Studio Dark"`
   - `workbench.preferredLightColorTheme: "Linux Studio Light"`
   - `workbench.colorTheme: "Linux Studio Dark"`

   The launcher applies these **only when the user hasn't set them**, unlike the locked privacy settings, so the user can still choose any theme.
   Back up the launcher first.
4. **The desktop GTK windows** (first-run, the pop-up and the websites window) already use the mockups' dark palette through
   `src/network/studio_theme.py`. Move that file to `src/common/studio_theme.py` and use it in `first_run.py` too, so all four Linux Studio windows match.
5. **For testing now:** copy the theme into the local build (`build-cache/editor/1.148.0/app/...`). The PM then runs the workflow once, so the
   official build includes it.

**Verification:**
- Under Xvfb, screenshot the editor (Explorer, the Welcome page, an open Python file, the terminal panel) in Dark. Switch the colour scheme to Light
  and screenshot again. Compare both with the mockups' palettes side by side.
- Confirm the user can still choose another theme, and that the choice survives a relaunch, because the launcher doesn't overwrite it.
- Confirm the first-run window now uses the dark palette.
- Re-run all tests (unit, network, isolation) and the telemetry check on the rebuilt app.

## Phase 3 — Approved-websites proxy, approval pop-up, websites window

**Context:** Phase 2 is done. The editor runs locked to `/project-folder` with **no network at all**. Phase 3 gives extensions
(such as Claude Code) and terminal tools internet access to **only the websites the PM approves**, while keeping the fake identity.
The mockups for screen 2 (approval pop-up) and screen 3 (approved websites) are already approved.

**PM decisions (2026-11-25):**
- An approval covers that **exact address only**, for example `api.anthropic.com`, not `*.anthropic.com`.
- **Terminal tools** (pip, npm, git, curl) use the **same approvals** as extensions.
- **HTTPS only:** connections are allowed on port 443 only. Plain HTTP and other ports are refused.
- The list **starts empty**, so nothing is approved until the PM says so.

### How it works
```
SANDBOX (no network devices except lo)                HOST
editor / extensions / terminal tools                   studio-proxy.py (Python stdlib, one per launch)
  └─ HTTPS_PROXY=http://127.0.0.1:3128                   ├─ listens ONLY on a unix socket in the launch temp folder
       └─ net-bridge.py (inside, stdlib)  ── socket ──▶   ├─ CONNECT host:443 only; checks network.json
          127.0.0.1:3128 → /run/linux-studio/proxy.sock   ├─ unknown host → approval pop-up (GTK4, host)
                                                          ├─ resolves DNS itself; refuses private/loopback/link-local IPs
                                                          └─ blind TLS tunnel (no decryption, no content logged)
```

### Files
1. **`src/network/studio-proxy.py`** (Python standard library only; runs on the host, started and stopped by the launcher):
   - A threaded server on a **unix socket** that accepts only `CONNECT host:443`. Everything else gets `403`/`405`: plain HTTP,
     other ports, IP-address literals, and malformed or overlong hostnames.
   - **Decisions:**
     - network switched off → deny
     - host blocked → deny silently
     - host allowed, or allowed once this session → connect
     - unknown host → pop-up
   - **Pop-ups:**
     - Requests for the same host while its pop-up is open wait for that one answer, so you get one pop-up per host.
     - No answer within **60 seconds** means deny.
     - **No display (headless) means deny.**
   - **Safety:** the proxy resolves DNS on the host and **refuses addresses that are private, loopback, link-local or reserved**
     (127/8, 10/8, 172.16/12, 192.168/16, 169.254/16, ::1, fc00::/7 and so on). Then it connects to that exact resolved address, which stops
     DNS-rebinding tricks. So the sandbox can never reach your own computer's services, your router, or cloud metadata addresses.
   - **Privacy:** it tunnels the encrypted bytes blindly, with no decryption and no content inspection. It records only a domain's
     "last used" time in `network.json` and writes no traffic log.
   - **Limits:** a cap on simultaneous tunnels and timeouts on idle connections. It shuts down cleanly when it gets SIGTERM, or when the
     launcher's process ends.
2. **`src/network/net-bridge.py`** (stdlib; runs inside the sandbox from the runtime's Python): it listens on `127.0.0.1:3128` and
   forwards each connection to `/run/linux-studio/proxy.sock`. It's started by a small entry script, and the editor or shell starts after it.
3. **`~/.config/linux-studio/network.json`** (host only, never mounted into the sandbox) holds
   `{ "network_enabled": true, "sites": { "<host>": { "status": "allowed"|"blocked", "last_used": "<UTC time>" } } }`.
   - Changes are written as a whole new file with a lock, so the proxy and the window never clash.
   - The proxy re-reads the file whenever it changes, so edits in the window take effect immediately.
4. **`src/network/approval_prompt.py`** (GTK4, host): mockup screen 2. It shows:
   - the host and port, plus the time
   - the "this site will see your public IP" warning
   - **Deny**, **Allow once** and **Always allow** buttons

   Its exit code carries the answer back to the proxy.
5. **`src/network/sites_manager.py`** (GTK4, host): mockup screen 3.
   - Add a site; the name is checked so it can't include `https://` or a path.
   - The table lists each site with its status and last-used time, plus Block/Allow and Remove buttons.
   - A "Turn network off/on" switch.

   It's opened with **`linux-studio --network`**. A menu entry comes in Phase 5.
6. **`src/launcher/linux-studio` changes** (back up the Phase 2 version in `/version-control/launcher/<ts>/` first):
   - Start `studio-proxy.py` with its socket in the per-launch temp folder before bwrap starts. Stop it in the exit cleanup, and confirm the socket is gone.
   - Mount the socket at `/run/linux-studio/proxy.sock` and the bridge read-only.
   - Inside the sandbox, set `HTTPS_PROXY`, `https_proxy`, `HTTP_PROXY`, `http_proxy`, `ALL_PROXY` = `http://127.0.0.1:3128`, and `NO_PROXY=` (empty).
   - Provide an empty `/etc/resolv.conf`, so nothing can look up names except through the proxy.
   - Add the new `--network` option, which opens the websites window.
7. **Runtime:** no new packages; the bridge uses the runtime's existing python3. `src/editor/default-settings.json` already has `http.proxy`.
8. **Tests:**
   - **`tests/test_proxy.py`** (Python unittest, stdlib) covers the decision logic: hostname checks, the private-IP list, port 443 only,
     exact-host matching, network off, allow-once, timeout means deny, and safe file writes.
   - **`tests/network-test.sh`** (end to end, throwaway settings folders, a test `network.json`):
     - direct connection bypassing the proxy fails, and DNS lookup inside the sandbox fails
     - unknown host is denied (headless)
     - a host pre-approved in the test file works through the proxy
     - a blocked host is refused, and network off refuses everything
     - CONNECT to `127.0.0.1`, `169.254.169.254`, `10.0.0.1` and a private-resolving name is refused
     - port 22 and port 80 are refused
     - `network.json` isn't visible inside the sandbox
     - after exit, there's no proxy process or socket left behind (`ss -lx`)
     - Phase 2's `isolation-test.sh` still passes, with its "no internet" check updated to "no direct internet"
   - **GUI under Xvfb with xdotool:** the approval pop-up appears for a new host. Clicking **Allow once** lets the request through, and the
     host isn't saved. **Always allow** saves it. The websites window shows the host, and toggling and Remove work. Screenshots are compared
     with mockup screens 2 and 3.
9. **Security review:** after the tests pass, ask the project's **jake-lockley** security agent to review the proxy and bridge code
   (OWASP/SSRF). I'll report what it finds before committing.
10. **Docs and logs:** programming documentation (how the proxy works, in plain language), the feature list (proxy rows set to ✅),
    and a changelog entry. There are no secrets or environment variables for `.env_example`.

### Known limits (to document)
- Approved websites see the PM's public IP address, and whatever the app itself sends inside the encrypted connection, such as login tokens.
- Programs that ignore proxy settings just fail to connect. That's the safe outcome, not a leak.
- Extensions share one process, so approvals are per website, not per extension.

## Phase 2 — Sandbox launcher, bundled runtime, first-run window (network fully off)

**Context:** the editor build is done and verified (Code - OSS 1.148.0, record in `build/editor-version.json`, app in
`build-cache/editor/1.148.0/app`). Phase 2 makes it run inside the locked sandbox. It can see only the project folder, has no network,
uses a fake identity, and the terminal shows `project-folder/...`.

**PM decisions (2026-11-25):**
- Build the GTK4 first-run window now, matching the approved mockup screen 1.
- GPU off by default, with a `--gpu` option to turn it on.
- Test in the Codespace with a virtual screen (Xvfb).

**Environment facts (checked):**
- bubblewrap 0.9.0-1ubuntu0.3 is installed. It's newer than the fixed 0.9.0-1ubuntu0.2 listed in USN-8779-1 for CVE-2026-87766.
- User namespaces work here. A test sandbox showed hostname `studio`, no `/sys`, and only the `lo` network device.
- `/etc/subuid` has an entry for this user. `mmdebstrap` and `newuidmap` are missing.

**PM runs once (needs sudo; these are test and build tools only, all from the free Ubuntu archive):**
`sudo apt-get update && sudo apt-get install -y mmdebstrap uidmap xvfb imagemagick jq python3-gi gir1.2-gtk-4.0`

### Files
1. **`scripts/build-runtime.sh`:** the private mini-Linux.
   - Runs `mmdebstrap --mode=unshare --variant=minbase` for **Debian 13 (trixie)**, with no root needed.
   - Packages:
     - **Shell and tools:** bash, coreutils, git, ca-certificates
     - **Languages:** python3, python3-pip, python3-venv, nodejs, npm, gcc, g++, clang, make, cmake
     - **Fonts:** fonts-dejavu-core
     - **Editor libraries:** GTK3, NSS, libsecret, libxkbfile, libgbm, ALSA and others, confirmed with `ldd` on the editor binary inside the runtime
   - Output goes to `build-cache/runtime/<YYYY-MM-DD>/rootfs/`, which git ignores, plus a tracked `build/runtime-manifest.txt` listing every package and version.
   - Copies in `src/runtime/overlay/`:
     - `etc/bash.bashrc.d/linux-studio.sh`: the prompt shows the path without the leading `/`, for example `project-folder/apples $`.
     - `etc/profile.d/linux-studio-privacy.sh`: sets `PIP_DISABLE_PIP_VERSION_CHECK=1`, `NPM_CONFIG_UPDATE_NOTIFIER=false` and `NPM_CONFIG_AUDIT=false`.
2. **`src/launcher/linux-studio`** (bash, on the host):
   - **Options:** `--set-project-folder PATH`, `--shell` (opens bash in the same sandbox, used for tests and debugging), `--gpu`,
     `--editor-dir DIR` and `--runtime-dir DIR`. The last two are for development; the defaults are the installed `/opt/linux-studio/...` paths.
     We use options rather than environment variables, so no `.env` is needed.
   - **Config:** `~/.config/linux-studio/config` holds `PROJECT_FOLDER=...`. If it's missing, or the folder doesn't exist, the launcher opens the first-run window.
   - **Fake identity**, written to a temporary folder for each launch and deleted on exit:
     - `/etc/passwd` and `/etc/group` with `user`, uid 1000
     - `/etc/hostname` = `studio`, and `/etc/hosts`
     - `/etc/machine-id`, randomly generated each launch
   - **bwrap options:**
     - `--unshare-all` (this includes the network), `--die-with-parent`, `--new-session`, `--clearenv`, `--cap-drop ALL`,
       `--hostname studio`, `--uid 1000 --gid 1000`
     - read-only binds: the runtime to `/` and the editor to `/app`
     - read-write binds: `~/.local/share/linux-studio/home` to `/home/user`, and the project folder to `/project-folder`
     - `--proc /proc`, `--dev /dev`, `--tmpfs /tmp`, `/run/user/1000`, and **no /sys**
   - **Display:**
     - Wayland socket only, by default (`--ozone-platform=wayland`).
     - X11 is a fallback, with a printed warning. It mounts only that display's socket plus a copied Xauthority file.
     - The GPU is visible only with `--gpu`. Otherwise the editor runs with `--disable-gpu`.
   - **Editor launch:** `/app/linux-studio-editor --user-data-dir /home/user/.config/linux-studio --extensions-dir /home/user/.linux-studio/extensions /project-folder`.
   - **Settings:** before every launch, the settings from `src/editor/default-settings.json` are merged over the user's
     `settings.json` with `jq`, so the user can't switch off the locked privacy settings.
   - **Chromium's own sandbox** stays on, nested inside bwrap. If it refuses to start nested, I stop and ask. I won't add `--no-sandbox` on my own.
3. **`src/first-run/first_run.py`** (Python with GTK4 through PyGObject, on the host, outside the sandbox). It follows mockup screen 1:
   - the title and explanation text
   - a path field, defaulting to `~/LinuxStudio/project-folder`
   - **Browse…** opens `Gtk.FileDialog`, the system folder picker
   - the info note
   - the terminal preview
   - **Quit** and **Create folder and open Linux Studio** buttons

   On confirm it creates the folder, writes the config and returns control to the launcher. It refuses unsafe choices: your home folder
   itself, `/`, system folders, or any folder that contains the Linux Studio state folder.
4. **`tests/isolation-test.sh`** runs every Phase 2 check through `linux-studio --shell -c ...`. It prints PASS or FAIL per check and
   exits non-zero if any check fails.
5. **Docs and logs:** update the programming documentation (each part in plain language) and `feature_documentation.md` (project folder,
   sandbox, fake identity, GPU option), and add a changelog entry. There are no secrets or environment variables, so no `.env_example`.
   Back up any existing file before changing it (`src/editor/default-settings.json`, if it's touched).

### Research before writing code (budget and privacy rules)
- Read the Debian trixie package licences in the generated manifest.
- Check GTK4 and PyGObject (LGPL) for telemetry.
- Check the Ubuntu security tracker for any open CVEs in GTK4 and PyGObject.

### Verification (in the Codespace)
1. `tests/isolation-test.sh` passes all of these:
   - `ls /` shows only sandbox folders.
   - `/home/codespace`, `/etc/shadow` and `/sys` are not reachable.
   - `hostname` is `studio`, `whoami` is `user`, and the network devices are only `lo`.
   - `curl https://example.com` fails because there's no network.
   - `pwd` and the prompt show `project-folder/...`.
   - A file created in the sandbox appears in the host project folder and nowhere else.
   - `/etc/machine-id` is different on each launch, and `/dev/dri` is absent without `--gpu`.
2. **Editor launch:** start Xvfb, run the launcher with the X11 fallback, wait, then take a screenshot with ImageMagick's `import`.
   The screenshot should show the Linux Studio window with the Explorer on `project-folder`. This also confirms it starts without the Copilot SDK.
3. **Integrated terminal:** run `pwd` from the editor's own terminal and confirm the prompt shows `project-folder $`.
4. **First-run window:** take a screenshot under Xvfb and compare it with mockup screen 1.
5. **Cleanup:** after closing, no leftover processes, temporary identity files or open sockets remain.
6. I'll report any check I couldn't run rather than assume it passed.

## Phase 1c — Build plain Code - OSS instead (replaces Phase 1b; PM decision 2026-11-25)

**Context:** both VSCodium build runs failed for the same reason. VSCodium's patches only fit VS Code 1.143.1. Run 45618050509 on 1.148.0
failed in the Copilot-removal list, and run 45619378836 on 1.145.3 failed in the branding patch. VSCodium has no update in progress.
The PM chose to build Microsoft's open-source **Code - OSS 1.148.0** (which includes the CVE-2026-120779 fix) directly, without VSCodium's patches.

**Research findings (VS Code 1.148.0, `product.json` and build files):**
- **Telemetry:** none is sent. Code - OSS ships without Microsoft's telemetry keys (`aiConfig`/`ariaKey` are absent).
- **Network endpoints we must remove or override in `product.json`:**
  - `voiceWsUrl`: a Microsoft voice service.
  - `defaultChatAgent`: GitHub Copilot sign-in and usage endpoints.
  - `trustedExtensionAuthAccess`: lets Copilot use your GitHub and Microsoft logins.
  - `webviewContentExternalBaseUrlTemplate`: a Microsoft CDN (vscode-cdn.net). We need to confirm whether the desktop app uses it.
- **No extension store** is configured (`extensionsGallery` is absent). We add Open VSX, the same settings VSCodium uses.
- **⚠ Copilot is built into the build itself:** an `extensions/copilot` folder, the `@microsoft/copilot-sdk` library and its runtime files.
  We can't safely cut all of it out without VSCodium-style patches. What we'll do:
  1. Try removing the `extensions/copilot` folder before building. If the build breaks because of that, we put it back and report it.
  2. Lock the settings `chat.disableAIFeatures: true` and `chat.commandCenter.enabled: false`.
  3. Rely on the sandbox and proxy to block every Copilot or Microsoft website unless the PM approves it.
- **Build tools:**
  - pnpm 12.16.0 and Node 24.22.1, from the repo's `.nvmrc` and `packageManager`.
  - Gulp target `vscode-linux-x64-min`, which runs with up to 8 GB of memory, so it fits GitHub's free 16 GB runner.
  - Three built-in debug extensions (js-debug and two others, MIT licence) are downloaded from GitHub during the build.

**Changes:**
1. **Version control:** copy the current `.github/workflows/build-vscodium.yml` and `scripts/fetch-vscodium.sh` to
   `/version-control/build-workflow/2026-11-25_HHMM/` before replacing them. They're small text files, so they get committed.
2. **Replace the workflow with `.github/workflows/build-editor.yml`** ("Build Linux Studio editor"). It keeps the same safety measures:
   manual start, read-only token, no secrets, actions pinned by hash, and the tag-to-commit check.
   - Check out `microsoft/vscode` at the checked commit (default `1.148.0` / `661626d0…`).
   - Clear space on the runner, then set up Node from `.nvmrc` and pnpm through corepack, and install the Linux build libraries.
   - Apply `src/editor/product-overrides.json` with `jq`. It sets:
     - name "Linux Studio", `applicationName: linux-studio-editor`, `dataFolderName: .linux-studio`
     - the Open VSX gallery
     - removes `voiceWsUrl`, `defaultChatAgent` and `trustedExtensionAuthAccess`
   - Remove `extensions/copilot`, then run `pnpm install --frozen-lockfile` and `pnpm run gulp vscode-linux-x64-min`.
   - Archive `VSCode-linux-x64` as `linux-studio-editor-<tag>-linux-x64.tar.gz` with `SHA256SUMS` and `build-info.json`, kept as a 7-day artifact.
3. **Add `src/editor/product-overrides.json` and `src/editor/default-settings.json`**, the locked privacy settings from the Phase 1 research plus the
   AI-off settings above. They're applied at launch in Phase 2.
4. **Rename `scripts/fetch-vscodium.sh` to `scripts/fetch-editor.sh`** with the new artifact name, unpacking into `build-cache/editor/<tag>/`.
   Update every reference to the old names in the docs, per the renames rule.
5. **Delete the old `build-vscodium.yml`** after it's backed up. Update the programming documentation, the plan text and the changelog.
6. **The PM starts the workflow**, because the Codespace token can't. I watch it and report the result.

**Verification:**
1. The workflow finishes green.
2. `fetch-editor.sh` checks the SHA256.
3. `bin/linux-studio-editor --version` prints 1.148.0.
4. In the built `product.json`, the removed keys are gone, `extensionsGallery` points to Open VSX, and no telemetry keys are present.
5. Search the unpacked app for `vscode-cdn.net`, `mai.microsoft.com` and `copilot_internal` and report what's left. Phase 3's proxy test
   later confirms that none of them can be reached without approval.

## Phase 1b — Build our own patched VSCodium (superseded by Phase 1c, kept for history)

**Why:** the latest official VSCodium (1.143.17232) is built on VS Code 1.143.1. That's older than the fix for critical flaw
CVE-2026-120779, which arrived in VS Code 1.145.3 on 10 Nov. The PM chose to build VSCodium ourselves. This Codespace is
too small for the build (2 CPUs, 7 GB of memory), so we'll use **GitHub Actions**, which is free for public repos. That's the same
service VSCodium uses for its own releases.

**Files:**
- `.github/workflows/build-vscodium.yml`
  - **Trigger:** manual only (`workflow_dispatch`), with one input: the VS Code version, defaulting to `1.148.0`, the newest.
    If VSCodium's patches don't apply cleanly to that version, we fall back to `1.145.3`, the first patched version.
  - **Security:**
    - `permissions: contents: read`
    - every third-party action pinned to a full commit hash
    - no secrets used
    - VSCodium's build scripts checked out at a pinned commit, which we review before using
  - **Steps:** check out VSCodium's scripts, set the VS Code version, and run their Linux x64 build. Then produce a `.tar.gz` and a
    `SHA256SUMS` file and upload both as a workflow artifact kept for 7 days. Nothing is published as a GitHub Release.
- `scripts/fetch-vscodium.sh`
  - Downloads the artifact with `gh run download` into `build-cache/vscodium/<version>/` and checks the SHA256.
  - Ours is a public repo, so `gh` only needs read access.
- `/.gitignore` (created now) ignores `build-cache/`, `project-builds/*` binaries, `version-control/**` binaries, `.env` and `*.tar.gz`.
- `build/vscodium-version.json` is tracked in git and records the VS Code tag, VSCodium commit, workflow run ID and SHA256.
  That gives us a written record of exactly what we built.

**Branding:** the "Linux Studio" name, icon and locked settings are applied to the built app during packaging (Phase 5), not
inside the build. This keeps the upstream build simple to repeat.

**Version control:** when we later move to a newer VSCodium, the old build is kept in `/version-control/vscodium/<YYYY-MM-DD_HHMM>/`.
The binary is ignored by git because it's hundreds of MB. Only its manifest is committed.

**Budget check before writing the workflow:** read GitHub's Actions billing docs in full to confirm public repos run free on standard
runners. Read VSCodium's `docs/howto-build.md` and build scripts in full, to confirm the version-override variables and the disk and
memory each build needs.

**Verification:**
1. The workflow run finishes green.
2. `fetch-vscodium.sh` downloads the build and the SHA256 matches.
3. `./bin/codium --version` in the Codespace prints the chosen VS Code version. It runs headless, so no display is needed.
4. `product.json` in the build shows telemetry and the crash reporter off.

## Phases (each one needs PM approval before it starts)
0. **Mockups:** an interactive HTML page showing the first-run folder chooser, the network approval prompt, the allowlist manager and the Toolchains explorer. No code is written before the PM approves these.
1. **Research:** confirm the licences, pricing and telemetry of VSCodium, Open VSX, bubblewrap, mmdebstrap and Electron, and check them for known CVEs. Record the results in the programming documentation.
2. **Sandbox, runtime and VSCodium** with the network fully off. Prove the isolation works.
3. **Proxy, masking and approval prompt.**
4. **Toolchains explorer.**
5. **Packaging** following `guidelines/Linux-Packaging.md`. Ask the PM whether it's a dev or release build and which formats to produce. bubblewrap must be a declared dependency.

## Notes and risks
- **Root needed:** installing `bubblewrap` and `mmdebstrap` needs `sudo`, so the PM will run those commands.
- **Ubuntu 23.10 and later** block unprivileged user namespaces through AppArmor. The distro's `/usr/bin/bwrap` has an allowed profile, so we must use the system bwrap and not bundle our own.
- **Testing here:** this Codespace container may not allow user namespaces. If so, isolation tests need a local VM, and I'll report that rather than assume they passed.
- **Download size:** the bundled runtime with all four toolchains is likely 600 MB to 1 GB.
- **Shared extension process:** VS Code runs every extension in one process, so network approval is per website, not per extension.

## Verification (for Phase 2 and 3)
Run these inside a Linux Studio terminal:
- `ls /` should show only the sandbox folders.
- Accessing `/home/<realuser>`, `/etc/shadow` or `/sys` should fail.
- `hostname` should return `studio`, `whoami` should return `user`, and `ip link` should show only `lo`.
- `pwd` and the prompt should show `project-folder/...`.
- `curl https://example.com` should be blocked unless approved, and `curl` to an approved domain should work.
- Files created in the terminal should appear in the chosen host folder, and nowhere else.
- After closing the app, `ss -lx` should show no leftover proxy socket.

### Phase 6 addendum (PM approved 2026-11-25 after reviewing the real-screenshot gallery)
Look fixes in the same round:
1. Desktop GTK windows follow light/dark: the system colour-scheme setting through the XDG portal, with GTK settings as a fallback. Both palettes come from the mockups.
2. The editor's title-bar and window icon become the Linux Studio placeholder icon.
3. Hide the unused secondary side bar (VS Code's AI chat area) by default, as an initial setting.
4. Welcome: `workbench.startupEditor: none`, plus a declarative "Get started with Linux Studio" walkthrough in the theme extension (data only, no code). VS Code's built-in welcome text can't be removed without patching the editor; it only appears if opened manually.
5. Light-theme terminal readability: fix the hint and ghost-text contrast.
Settings window (mockup screen 5) approved as shown.

### Phase 6 addendum 2 (PM approved 2026-11-25): Claude Code compatibility test
After the nested X11 display works, run a real test inside Linux Studio:
- install the Claude Code extension from Open VSX and record every website it requests
- try the sign-in flow under both clipboard settings
- try the `claude` command in the sandbox terminal
- note what breaks (for example Claude Code's own bubblewrap sandbox inside ours)

Likely follow-up: an "Open link in my browser" helper. Sandboxed code asks, a host-side confirmation shows the exact link, and only then is it handed to
the real browser. It's new UI, so a mockup goes to the PM before it's built. Report the findings to the PM before changing anything.

## Phase 7 (future, after the Claude Code test): Game and software developer support, starting with Unity
**PM request (2026-11-26):** "I do want Game/Software devs able to use this application." Plan this phase once the Claude Code compatibility test is done.
Each item below is a proposal; the PM approves the detailed plan (and any mockups) before work starts.

Unity Editor stays on the host. Linux Studio becomes its "External Script Editor".
1. **.NET SDK in the Toolchains explorer.** Use the official Microsoft builds (dotnet.microsoft.com / builds.dotnet.microsoft.com). Check checksums, signatures, the licence and that `DOTNET_CLI_TELEMETRY_OPTOUT=1` is enforced in the sandbox. Read the docs in full first.
2. **C# editing extension from Open VSX.** Microsoft's C# Dev Kit and Unity extension aren't on Open VSX, and their licence ties them to Microsoft's VS Code. Evaluate free options (for example the Open VSX "C#" (free) extension or DotRush) for licence, telemetry and which websites they need.
3. **Unity's own libraries, read-only.** Mount only the Unity Editor version a project uses, from the Hub's Editor folder, read-only. Rewrite or map the host paths in the generated `.csproj`/`.sln` files so code checking works. The PM chooses which Unity installs to expose.
4. **"Open file" from Unity.** The launcher accepts `linux-studio <host-path>[:line]`, translates a path inside the project folder to `/project-folder/...`, opens it in the running window, and refuses anything outside.
5. **Debugging (security decision for the PM).** Unity's debugger needs a local connection to the Unity Editor. Options: keep it blocked (default), or a per-session, PM-approved tunnel to that single port only. Needs a security review and a mockup of the approval screen.
6. **Other game and software stacks to consider in the same phase.** Godot (C# and GDScript language servers on localhost), Java/Gradle, Rust/Cargo already partly covered. Survey with the PM.
Verification: a sample Unity project opens from Unity, code suggestions work for UnityEngine types, nothing outside the project folder and the read-only Unity libraries is visible, all existing test suites still pass.


## Status update 2026-11-26 (PM decisions)
- **Addendum 2 (Claude Code compatibility test): CLOSED.** It works under the normal rules, and nothing Claude-specific is to be built in (PM). The findings are in programming_documentation.md.
- **New order:** dev4 (signature checker, size limit, Remove my data, pop-up on top, flatter corners) → **dev5: CPU and memory settings** (approved mockup: CPU default all
  cores but one, memory default 75% of RAM; "All cores" and "No limit" available; cores via CPU pinning, memory via a systemd user scope with MemoryMax; falls back
  with a notice if unsupported; self-test reports it) → **Phase 7, game development support.**
- **dev5 also: web links open in a tab inside Linux Studio (PM decision 2026-11-26).** Set `workbench.externalUriOpeners: {"*": "workbench.integratedBrowser"}` (an initial setting the user can change, or locked; decide during the build).
  Verify in the GUI: clicking "Open" shows the Integrated Browser tab; the tab's traffic goes through the approval proxy (a new site → pop-up); GitHub loads (not an iframe); cookies are stored inside the sandbox home.
  Consider `workbench.browser.enableChatTools: false` (Copilot is removed anyway). No real-browser hand-off for now.
- **dev5 also: "complete sign-in in your browser" flows (PM 2026-11-26, example: Cline "Almost there!").** Test real sign-ins of each callback type in the in-app tab:
  (1) a redirect to the editor's own URL scheme (`linux-studio-editor://…` from product.json `urlProtocol`): check whether the Integrated Browser hands it to the
  editor's URL handler; (2) a localhost callback server inside the sandbox (should work, same sandbox; make sure the proxy bypasses loopback);
  (3) a device code. Also check extensions that call `xdg-open` directly; if needed, propose an in-sandbox `xdg-open` replacement that routes to the tab.
  Bring any editor change or new channel to the PM before doing it.
- **dev5 additions (PM approved 2026-11-26, mockups screens 2/3/5):**
  - Remove-data confirmation as a modal pop-up window (Cancel default; Remove selected red, 1 s lock).
  - "Connection refused" notice from the proxy when a site is refused without a pop-up (blocked, or session-denied after an unanswered pop-up): once per site per session,
    no focus, auto-close after 20 s, 1 s button lock; Blocked → "Open Approved websites…" (opens with the row highlighted); Unanswered → "Ask me now"
    (clears session-denied and shows the approval pop-up).
  - Approved websites: a "Block: refuse without asking. Remove: forget the site, so you're asked again next time" line plus tooltips.
- **dev5 link router (PM approved):** `src/launcher/xdg-open` (bound at /run/linux-studio/bin, first on PATH inside the sandbox). http(s) → `/app/bin/linux-studio-editor --user-data-dir … --open-url linux-studio://linux-studio.link-router/open?u=<url>`;
  linux-studio:// → `--open-url` as-is; other schemes refused. Built-in extension `src/editor/link-router/` (publisher linux-studio, name link-router; onUri) → `workbench.action.browser.open` for http(s) only.
  Workflow step + local build copy. Test with the scratchpad test extension (localhost page redirecting to linux-studio://ls-test.signin/callback). Security review.
- **dev5 fonts (PM approved):** add fonts-noto-core + fonts-noto-cjk to scripts/build-runtime.sh and rebuild the runtime (check licences in the copyright files).
- **Disk:** PM-approved deletion of the dev1 builds and the runtime backups _1516/_1830 → 9.9 GB free.
- **dev6 also (PM approved 2026-11-26, mockup screen 7): web page full screen with an escape route.** Pages may go full screen. While one is: a bar "This page is full screen. Press Esc to exit." + Exit button that the page can't cover;
  Esc works from anywhere; leaving the page's tab or clicking the editor ends full screen (PM: "End full screen"). Found during a PM test: page full screen hides the menu bar (window full screen), and Esc only reached the page while it had focus → trapped. Implementation = editor patch (research first; fall back to blocking page full screen only with PM approval).
- **dev6 build:** the earlier dev6-1 package (terminal PATH, --no-sandbox CLI, self-test X errors, window size) was built but NOT delivered (PM: hold and combine). Its install test was interrupted.
- **2026-11-27 PM decisions:**
  - **Network inbox APPROVED (mockup screen 8):**
    - no per-site pop-ups; one small notice "N websites are waiting" (count updated in place, no focus) with Open inbox / Later
    - an inbox window (host side) with Deny / Allow once / Always allow per site and Deny all; buttons locked for 1 s
    - waiting sites are refused; requests **expire after 10 minutes**
    - an editor status-bar item "🌐 N waiting" next to the bell (count only, from a read-only file in the sandbox; click → asks Linux Studio to open the inbox, rate-limited)
    - also in Settings > More, and `--network-inbox`
  - **Firefox-based private browser:** plan as its own phase AFTER the inbox. Research first: Firefox ESR (Debian) + enterprise policies (no telemetry, studies, Pocket; tracking and fingerprinting protection) vs LibreWolf. It runs inside the same sandbox, through the proxy. Then a mockup for choosing "open in tab" or "open in private browser".
  - dev6-2 PM-tested OK: Cline sign-in, approval pop-ups, xdg-open, video full screen in its tab.
- **2026-11-27 pause:** dev8 ON HOLD until the Firefox private browser is ready (PM). Research done (see the evening handoff's "Update 2026-11-27"). Four PM questions deferred: engine (ESR vs LibreWolf), where links open by default, remember vs forget, uBlock Origin.
