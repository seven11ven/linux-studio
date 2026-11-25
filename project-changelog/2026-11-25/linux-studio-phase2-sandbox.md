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

- The prompt was checked in an interactive bash inside the sandbox, not by typing in the editor's own terminal panel.
  That needs keyboard automation (`xdotool`), or a manual check on the Project Manager's machine.
- Wayland was not tested; the Codespace only has X11 (Xvfb).
- Test environment needed sudo installs by the Project Manager: `mmdebstrap uidmap xvfb imagemagick jq python3-gi gir1.2-gtk-4.0 debian-archive-keyring`.

## Impacts

- Linux Studio now runs locked to a single folder, with no network and a fake identity.
- The next CI editor build must be run so the `defaultChatAgent` fix is part of the official build (the local build was patched for testing).
- No secrets or environment variables introduced. Large outputs (`build-cache/`) are ignored by git.
