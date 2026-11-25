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
