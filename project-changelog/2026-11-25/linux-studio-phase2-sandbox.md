# Linux Studio — Phase 2: sandbox launcher, runtime and first-run window

- **Date:** 2026-11-25
- **Time:** 13:58–14:19 UTC
- **Performed By:** Claude Opus 5.5 (Anthropic), via Claude Code
- **Approved By:** Project Manager

## Changes

- **`scripts/build-runtime.sh`:** builds the Debian 13 runtime with `mmdebstrap` without root.
  - Requires `debian-archive-keyring`; signature checks are never skipped.
  - Creates the mount points (`/home/user`, `/project-folder`, `/app`, `/run/user`).
  - Writes `build/runtime-manifest.txt` (681 packages, all from Debian main).
- **`src/runtime/overlay/etc/linux-studio/bashrc`:** prompt without the leading slash; pip and npm phone-home checks switched off.
- **`src/launcher/linux-studio`:**
  - bubblewrap sandbox: `--unshare-all`, `--cap-drop ALL`, read-only runtime and editor, no `/sys`, no network, GPU only with `--gpu`
  - fake identity regenerated every launch and deleted on exit
  - locked settings merged at every launch
  - Wayland first, X11 fallback with a warning
  - folder safety rules
  - options `--set-project-folder`, `--shell`, `--gpu`, `--editor-dir`, `--runtime-dir`
- **`src/first-run/first_run.py`:** GTK4 window matching mockup screen 1. It uses the system Python, and validation is done by the launcher.
- **`tests/isolation-test.sh`:** 17 automated checks.
- **Fix: start-up crash.** VS Code 1.148 needs `product.json` → `defaultChatAgent`, and crashed with "Onboarding requires a default chat
  agent product configuration". The entry is now kept, with every web address replaced by `https://0.0.0.0`.
  - Applied through a new `__neutralise_urls` key in `src/editor/product-overrides.json` and the matching jq in `build-editor.yml`.
  - The local test build was patched the same way. `product.json` isn't covered by VS Code's file checksums.
  - Previous versions are backed up in `version-control/editor-config/2026-11-25_1416/`. Chosen by the Project Manager.
- **Docs:** added a Phase 2 section to `programming_documentation.md`, and wrote `feature_documentation.md` (feature list with status and known limits).

## Verification results

- **Isolation tests: 17/17 passed.**
- **Editor launch:** under Xvfb with the X11 fallback, the window shows Linux Studio with Explorer on `project-folder/apples`,
  Restricted Mode on and no chat panel. Chromium's own sandbox runs nested ("zygote" processes), so `--no-sandbox` is not used.
  The log shows "Unable to retrieve mac address", which confirms the masking works.
- **Prompt:** an interactive bash in the sandbox shows `project-folder $` and `project-folder/apples $`.
- **First-run window:** the screenshot matches mockup screen 1.
- **Cleanup:** after closing, 0 editor or bwrap processes, 0 temporary identity folders, and Xvfb stopped.
- **Libraries:** `ldd` inside the runtime finds every library the editor needs.

## Not verified / open items

- Wayland was not tested; the Codespace only has X11 (Xvfb).
- Test environment needed sudo installs by the Project Manager: `mmdebstrap uidmap xvfb imagemagick jq python3-gi gir1.2-gtk-4.0 debian-archive-keyring`.

## Impacts

- Linux Studio now runs locked to a single folder, with no network and a fake identity.
- The next CI editor build must be run so the `defaultChatAgent` fix is part of the official build (the local build was patched for testing).
- No secrets or environment variables introduced. Large outputs (`build-cache/`) are ignored by git.

## Update 14:25 UTC: editor terminal panel tested with xdotool

- `xdotool` was installed by the Project Manager (root command).
- **Result:** the terminal panel inside the editor opens at `project-folder $`. After `cd apples` the prompt is `project-folder/apples $`.
  `pwd` gives `/project-folder/apples`, `hostname` gives `studio`, and `whoami` gives `user`. `ls /` shows only sandbox folders, and `~` is empty.
- **Note:** `pwd` prints the real path inside the sandbox, `/project-folder/apples`, with a leading slash. The prompt hides the slash, but `pwd` is
  left unchanged so scripts keep working.
- **Workspace Trust finding:** during the test the folder became trusted, because a simulated Enter keypress answered the first-open
  "Do you trust the authors?" pop-up, whose default button is "Trust". This came from the test automation, not a sandbox flaw. The earlier
  launch without keystrokes showed Restricted Mode. Suggested to the Project Manager: lock `security.workspace.trust.startupPrompt` to
  `"never"`, so folders always open in Restricted Mode and trust must be granted on purpose.
- **Cleanup:** editor, bwrap and Xvfb stopped (0 left); test config, data and project folders deleted.
- **Performed By:** Claude Opus 5.5 (Anthropic) · **Approved By:** Project Manager

## Update 14:33 UTC: official build with defaultChatAgent fix verified

- **Run:** 45633090731 succeeded. The locally patched test build was moved to `version-control/editor/2026-11-25_1431/` (`app/` ignored by git).
- **New build verified:**
  - SHA256 OK; telemetry check passed
  - `defaultChatAgent` addresses are all `https://0.0.0.0`; the voice and auth-sharing entries are absent
  - no Copilot extension or SDK
  - all `product.json` checksums match
- **Smoke launch** under Xvfb with no keystrokes: the editor opens on `project-folder` in **Restricted Mode**, with no onboarding crash.
  Everything was closed afterwards (0 processes left) and test data deleted.
- `build/editor-version.json` updated to this build.
- **Performed By:** Claude Opus 5.5 (Anthropic) · **Approved By:** Project Manager
