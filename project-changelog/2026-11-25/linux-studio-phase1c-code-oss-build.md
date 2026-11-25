# Linux Studio — Phase 1c: switch editor build to Code - OSS

- **Date:** 2026-11-25
- **Time:** 13:03–13:07 UTC
- **Performed By:** Claude Opus 5.5 (Anthropic), via Claude Code
- **Approved By:** Project Manager

## Why

The second VSCodium build (run 45619378836, VS Code 1.145.3) also failed: `00-brand-remove-branding.patch` doesn't apply.
VSCodium's patches only fit VS Code 1.143.1, and VSCodium has no update in progress. The Project Manager chose to build
Microsoft's open-source Code - OSS 1.148.0, which includes the CVE-2026-120779 fix, directly.

## Changes

- **Backed up** the old `build-vscodium.yml` (stored as `.txt` so GitHub never runs it) and `fetch-vscodium.sh` in
  `version-control/build-workflow/2026-11-25_1305/`.
- **Removed** `.github/workflows/build-vscodium.yml`. **Added** `.github/workflows/build-editor.yml` with the same safety measures
  (manual start, read-only token, no secrets, pinned actions, tag-to-commit check). It builds Code - OSS with gulp target `vscode-linux-x64-min`.
- **Added** `src/editor/product-overrides.json`: Linux Studio name, Open VSX store, and removal of the Microsoft voice, Copilot and
  auth-sharing endpoints. Tested against the real 1.148.0 `product.json`.
- **Added** `src/editor/default-settings.json`: the locked privacy and AI-off settings the launcher will apply in Phase 2.
- **Renamed** `scripts/fetch-vscodium.sh` to `scripts/fetch-editor.sh` and updated every reference to it.
- **Updated** the root `.gitignore` so small text backups in `version-control/` are committed and only binaries are ignored.
- **Rewrote** the build section of `programming_documentation.md`.

## Impacts

- The editor will be Code - OSS 1.148.0 branded as Linux Studio, not VSCodium.
- **Known limit:** some unused Copilot code still ships inside the app. It's switched off by settings and its websites are blocked by the
  sandbox and proxy.
- **To check after the build:** whether the desktop app contacts Microsoft's webview CDN (`vscode-cdn.net`).
- The workflow has not been run yet. The Project Manager must start it.
- No secrets or environment variables introduced.

## Update 13:19 UTC: first Code - OSS run failed; Copilot removal moved after the build

- **Run:** 45620621850 failed in "Build" (13:17 UTC). The error was `prepareBuiltInCopilotRipgrepShim: Copilot SDK directory not found`.
  VS Code's packaging step needs `extensions/copilot` to be present.
- **Fix (chosen by the Project Manager):** the source folder is no longer deleted before the build. A new step deletes
  `resources/app/extensions/copilot` from the finished app, and fails the build if that folder is missing or any Copilot extension is left.
- **Version control:** the previous workflow is backed up in `version-control/build-workflow/2026-11-25_1319/`.
- **Docs:** `programming_documentation.md` updated.
- **Performed By:** Claude Opus 5.5 (Anthropic) · **Approved By:** Project Manager

## Update 13:31 UTC: build succeeded and verified

- **Run:** 45622687556 succeeded. `scripts/fetch-editor.sh` downloaded it, the SHA256 matched (`f4e3e5f7…5cfa`), and it was unpacked to
  `build-cache/editor/1.148.0/` (827 MB, ignored by git). The record is saved to `build/editor-version.json`.
- **Verified:** `product.json` shows Linux Studio, version 1.148.0, commit `661626d0…`, and the Open VSX gallery. The voice, Copilot,
  auth-sharing, telemetry-key and update entries are absent. No Copilot extension is in the app.
- **Couldn't run:** `linux-studio-editor --version`. The Codespace lacks desktop libraries (`libatk-1.0.so.0`). The Phase 2 bundled runtime will provide them.
- **Found:** 13 built-in extensions (git, markdown, typescript and others) contain Microsoft telemetry keys (`aiKey`) and collector addresses
  (`mobile.events.data.microsoft.com`, `dc.services.visualstudio.com`). They are inactive while `telemetry.telemetryLevel` is `off`, which we lock,
  and the proxy blocks them. The webview CDN address (`vscode-cdn.net`) is also still present.
  A stronger fix was proposed to the Project Manager.
- **Performed By:** Claude Opus 5.5 (Anthropic) · **Approved By:** Project Manager

## Update 13:35 UTC: neutralise telemetry addresses (Project Manager approved)

- **Added `scripts/neutralise-telemetry.sh`:**
  - Clean mode (run on the source before the build) replaces `*.data.microsoft.com`, `dc(-int).services.visualstudio.com` and
    Application Insights addresses with `0.0.0.0`. It edits text files only.
  - `--check` mode scans a finished app, including `.asar` archives, and fails if any address remains.
  - Tested on a sample tree and against the current build. The check correctly fails on the un-neutralised 1.148.0 build.
- **Workflow:** added "Neutralise telemetry addresses" (after install, before build) and "Verify no telemetry addresses in the finished app".
  The previous workflow is backed up in `version-control/build-workflow/2026-11-25_1334/`.
- **Changed from the proposal:** extension telemetry keys are not stripped. They're compiled into extension code, for example the git
  extension calls `new TelemetryReporter(aiKey)` at startup, so removing them risks crashing extensions. With the addresses neutralised they're inert.
- **Design note:** a first version edited the finished app. Testing showed it would corrupt `node_modules.asar` and invalidate
  `product.json` checksums, so it was redesigned to run before the build.
- **Next:** rebuild. Before fetching the new build, move the current `build-cache/editor/1.148.0/` to `version-control/editor/<timestamp>/`.
- **Performed By:** Claude Opus 5.5 (Anthropic) · **Approved By:** Project Manager
