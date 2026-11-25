# Linux Studio — Phase 1: dependency research

- **Date:** 2026-11-25
- **Time:** 12:42–12:55 UTC
- **Performed By:** Claude Opus 5.5 (Anthropic), via Claude Code (research partly done by a Claude Sonnet research agent)
- **Approved By:** Project Manager

## Changes

- Researched licence, cost, telemetry and security for VSCodium, Open VSX, bubblewrap, mmdebstrap, Electron and the bundled language tools.
- Wrote the results into `project-notes/documents/programming_documentation.md`, along with the planned architecture.

## Impacts

- **Blocking issue found:** the newest VSCodium (1.143.17232) predates the fix for critical VS Code flaw CVE-2026-120779.
  The Project Manager must decide how to proceed before Phase 2.
- Open VSX supply-chain attacks in 2026 mean extensions must be installed by exact publisher and pinned version.
- Ubuntu 24.04+ users must install an AppArmor profile once with `sudo`.
- Documentation only. No code, dependencies, secrets or environment variables affected.
