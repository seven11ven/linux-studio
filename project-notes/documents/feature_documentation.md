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
| Wayland-only by default | ✅ | X11 desktops need `--allow-x11`, because on X11 sandboxed code could read the screen or type into other windows. |
| Approved-websites proxy | ✅ | Extensions and terminal tools can reach only exact websites you approve, over HTTPS only. Your computer, home network and cloud metadata addresses are never reachable. No traffic is logged. |
| Network approval pop-up | ✅ | A desktop pop-up asks Deny, Allow once, Always allow or Block all new sites. It shows one at a time, has a 1-second button delay, and treats no answer as deny. |
| Approved websites window | ✅ | `linux-studio --network`: add, block, allow or remove sites, and turn the network on or off. Changes apply immediately. |
| Toolchains explorer | 📋 | Browse and install extra languages from official sources, with checksum verification (Phase 4). |
| Linux packages | 📋 | Installable packages for Linux distributions (Phase 5). |

**Known limits**
- Websites you approve can see your public IP address.
- Some unused Copilot code remains inside the editor's core files. It's switched off and can't reach any address.
- Saved extension logins are stored obscured but not encrypted, in Linux Studio's private folder.
- With `--allow-x11`, code inside Linux Studio could read your screen and type into your other windows. Wayland avoids this.
- The editor engine tries to contact Google (`redirector.gvt1.com`, spellchecker dictionaries) at start-up. The proxy refuses it unless you approve it.
