# Linux Studio — Phase 1b: patched VSCodium build pipeline

- **Date:** 2026-11-25
- **Time:** 12:44–12:49 UTC
- **Performed By:** Claude Opus 5.5 (Anthropic), via Claude Code
- **Approved By:** Project Manager

## Changes

- **Added `.github/workflows/build-vscodium.yml`:** a manual GitHub Actions workflow that builds VSCodium for Linux x64 from VS Code
  **1.148.0** (commit `661626d0e72f97806550790a98fb87116c9db825`). That version includes the CVE-2026-120779 fix, which arrived in 1.145.3.
  - Uses VSCodium build scripts pinned at commit `ca7f7b44b5e5c3faa663f6cdc043998f71936653`. Their build, telemetry-removal and
    packaging scripts were reviewed.
  - Read-only token, no secrets, pinned actions and container image digest. Output is a 7-day artifact, not published anywhere.
- **Added `scripts/fetch-vscodium.sh`:** downloads the build artifact, checks its SHA256 and unpacks it into `build-cache/`, which git ignores.
- **Added root `/.gitignore`:** covers secrets, `.env`, large binaries, build outputs and version-control binaries.
- **Updated `project-notes/documents/programming_documentation.md`** with a plain-language explanation of the build.
- **Confirmed:** GitHub Actions is free for public repos on standard runners. Artifact storage pricing for public repos was not stated,
  so artifacts are kept for only 7 days.

## Impacts

- Lets Linux Studio ship a VSCodium that is not affected by CVE-2026-120779.
- The workflow has **not been run yet**. It must be pushed to GitHub first. VSCodium's patches were written for VS Code 1.143.1 and
  may not apply cleanly to 1.148.0. If they don't, rerun with 1.145.3 (`dcd3ad6e368fbe19d03f37054a40dbaf40d676f4`).
- No version-control backup needed: these are new components and nothing was replaced.
- No secrets or environment variables introduced.
