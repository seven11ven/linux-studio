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
| No network by default | ✅ | The sandbox has no internet access at all (Phase 2). |
| GPU off by default | ✅ | The graphics card is hidden from the app unless started with `--gpu`. |
| Locked privacy settings | ✅ | Telemetry, updates, experiments and AI features are forced off at every launch. |
| Workspace Trust | ✅ | Projects open in Restricted Mode until you trust them. |
| Approved-websites proxy | 📋 | Extensions that need the internet can reach only websites you approve (Phase 3). |
| Network approval prompt | 📋 | A desktop pop-up asks Deny / Allow once / Always allow for new websites (Phase 3). |
| Approved websites manager | 📋 | A window to add, block or remove websites, plus a network off switch (Phase 3). |
| Toolchains explorer | 📋 | Browse and install extra languages from official sources, with checksum verification (Phase 4). |
| Linux packages | 📋 | Installable packages for Linux distributions (Phase 5). |

**Known limits**
- Websites you approve can see your public IP address.
- Some unused Copilot code remains inside the editor's core files. It's switched off and can't reach any address.
- Saved extension logins are stored obscured but not encrypted, in Linux Studio's private folder.
- On X11 desktops, other X11 programs could see Linux Studio's window. Wayland is more private.
