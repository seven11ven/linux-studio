# Feature Documentation

A running list of Linux Studio's features, for specifications, legal and consumer-facing use.
Status key: ✅ built and tested · 🚧 in progress · 📋 planned

| Feature | Status | Description |
|---|---|---|
| Private code editor | ✅ | Built from Microsoft's open-source "Code - OSS" 1.148.0 (MIT licence), branded Linux Studio. Includes the fix for CVE-2026-120779. |
| No Microsoft telemetry | ✅ | No telemetry keys in the product file. All Microsoft collector addresses are replaced with a dead address. Telemetry settings are locked off. |
| Copilot removed | ✅ | The Copilot extension and its engine are removed from the app. AI features are switched off and Copilot's web addresses are dead. |
| Open VSX extension store | ✅ | Extensions come from the open-source Open VSX registry instead of Microsoft's marketplace. |
| One-folder sandbox | ✅ | The editor, its extensions and its terminal can see only your chosen project folder, shown inside as `/project-folder`. |
| Project folder chooser | ✅ | A first-run window (or `linux-studio --set-project-folder`) picks the folder. System folders and your whole home folder are refused. |
| Clean terminal paths | ✅ | The terminal starts in the project folder and shows paths like `project-folder/apples $`, never your real path. |
| Fake identity | ✅ | Inside the app: computer name `studio`, user `user`, a new random machine ID every launch, and no real network devices or MAC address. |
| Private mini-Linux | ✅ | A bundled Debian 13 system (signature-verified) supplies Python, Node.js, C/C++, Git and a shell. Your real system files are never used. |
| No direct network | ✅ | The sandbox has no network devices or address lookup. Its only way out is the approved-websites proxy. |
| GPU off by default | ✅ | The graphics card is hidden from the app unless started with `--gpu`. |
| Locked privacy settings | ✅ | Telemetry, updates, experiments and AI features are forced off at every launch. |
| Workspace Trust | ✅ | Projects open in Restricted Mode until you trust them. In Restricted Mode, tasks, debugging, the terminal and some extensions ask for trust first. |
| Linux Studio themes | ✅ | Dark and Light themes matching the design mockups. They follow your desktop's setting, and you can change them freely. All Linux Studio windows use the same colours. |
| Built-in block list | ✅ | Known background addresses, currently Google's spellchecker download (`redirector.gvt1.com`), are blocked from the start with no pop-up. They're shown as "Blocked (built in)" and can be overridden. |
| Private X11 display | ✅ | On X11 desktops Linux Studio runs in its own isolated window (Xephyr, no fake keyboard), so code inside can't read your screen or type into other windows. Wayland is used as-is. |
| Clipboard setting | ✅ | **Paste only** (default): your clipboard reaches Linux Studio only when you really paste in its window, and copies inside stay inside. **Both directions:** like a normal app, with a warning. Text only. |
| Settings window | ✅ | `linux-studio --settings` or the menu entry. Kept outside the sandbox. |
| Extension signature check | ✅ | Every extension from Open VSX is checked against Open VSX's Ed25519 signature (key pinned in Linux Studio) before it installs, using Linux Studio's own open-source checker. A missing, wrong or tampered signature stops the install, with **Install Anyway** to override. Can be switched off in Settings, and the largest extension it checks (256 MB to 1.5 GB, default 512 MB) is chosen there too (applies at next start). |
| CPU and memory limits | ✅ | Settings > CPU and memory. Defaults: all cores but one, and 75% of memory. Programs inside see only the allowed cores. The memory cap stops the biggest program inside Linux Studio instead of slowing the computer (needs systemd's user session; otherwise it says so). |
| Links open inside Linux Studio | ✅ | Web links, including extensions' "complete sign-in in your browser" pages, open in a tab inside Linux Studio (sandboxed, approved websites only). Sign-in redirects back to the editor (`linux-studio://`) reach the waiting extension. Other kinds of links are refused. |
| "Connection refused" notice | ✅ | When something is refused without asking (a site you blocked, or an unanswered question), a small notice says so once per site per session, with "Open Approved websites…" or "Ask me now". |
| Non-Latin text | ✅ | Noto fonts are included, so Arabic, Chinese, Japanese, Korean and other scripts display properly. |
| Remove my Linux Studio data | ✅ | Settings > Your data, or `linux-studio --remove-my-data`. Deletes the chosen parts (extensions/editor settings/logins, toolchains, Settings choices and approved websites). Refuses while Linux Studio is open and never touches the project folder. Uninstalling never deletes this data by itself. |
| Consistent look | ✅ | Every Linux Studio window follows light or dark. Linux Studio icon on every window, watermark, a Linux Studio welcome walkthrough, and the unused AI panel hidden. |
| Approved-websites proxy | ✅ | Extensions and terminal tools can reach only exact websites you approve, over HTTPS only. Your computer, home network and cloud metadata addresses are never reachable. No traffic is logged. |
| Network inbox | ✅ | New websites wait in an inbox instead of popping up one by one. A single small notice ("N websites are waiting") and a "🌐 N waiting" item in the editor's status bar open the inbox, where each site gets Deny, Allow once or Always allow (or Deny all). Waiting sites are refused; requests expire after 10 minutes. Also in Settings > More and `linux-studio --network-inbox`. |
| Network approval pop-up (replaced by the inbox) | ✅ | A desktop pop-up asks Deny, Allow once, Always allow or Block all new sites. It shows one at a time, has a 1-second button delay, and treats no answer as deny. On X11 desktops it stays on top of other windows and flashes in the taskbar, so it can't hide behind Linux Studio. |
| Approved websites window | ✅ | `linux-studio --network`: add, block, allow or remove sites, and turn the network on or off. Changes apply immediately. |
| Toolchains explorer | ✅ | `linux-studio --toolchains`: install extra Python, Node.js, Go, Rust, Java and CMake versions from official publishers. SHA-256 is always checked, and publisher signatures where published. It's online only while open, and limited to official sites. Choose versions with Use this version, and uninstall with Remove. |
| Read-only toolchains | ✅ | Inside the editor, installed toolchains can't be changed by project code. |
| Go telemetry off | ✅ | Go's telemetry is switched off, and Go can't download other Go versions by itself. |
| .deb package (dev build) | 🚧 | Dev builds for Ubuntu 24.04+ / Linux Mint 22 (latest: dev3). Each passes a clean-install, upgrade, remove and purge test and lintian (0 errors in Linux Studio's own files); dev2-2 and dev3 tested on the PM's Mint machine. Not yet a release build. |
| Self-test | ✅ | `linux-studio --self-test` checks the sandbox on your computer and explains anything that's off. |
| Ubuntu-safe sandbox permission | ✅ | Follows Ubuntu's own restricted AppArmor design: only Linux Studio's bwrap copy may sandbox, and nothing inside gets kernel capabilities. |

**Known limits**
- On Ubuntu 24.04+, the editor's inner Chromium sandbox and the nested Rust-installer sandbox are off (Ubuntu's AppArmor rules). The main Linux Studio sandbox still isolates everything.
- The dev build uses a placeholder icon.
- The project has no licence chosen yet.
- Go and python-build-standalone publish checksums only, with no signature. Their HTTPS downloads protect the transfer, but not against a compromised publisher.
- Websites you approve can see your public IP address.
- Some unused Copilot code remains inside the editor's core files. It's switched off and can't reach any address.
- Saved extension logins are stored obscured but not encrypted, in Linux Studio's private folder.
- On X11 the editor appears as one window inside your desktop (Xephyr), labelled as Linux Studio with its icon. Use your desktop's window buttons; the editor's own are hidden there.
- In Both-directions clipboard mode, code inside Linux Studio can read what you copy elsewhere.
- The editor engine tries to contact Google (`redirector.gvt1.com`, spellchecker dictionaries) at start-up. It's pre-blocked silently, and can be allowed in the websites window.
