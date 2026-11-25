# Linux Studio — Phase 4: Toolchains explorer

- **Date:** 2026-11-25
- **Time:** 15:10–15:35 UTC
- **Performed By:** Claude Opus 5.5 (Anthropic), via Claude Code. Research by a Claude Sonnet agent; security review by the jake-lockley agent (Claude).
- **Approved By:** Project Manager

## Changes
- **`src/toolchains/explorer.py`:** GTK4 window (mockup screen 4, plus the approved "Use this version" and "Remove" buttons). It never touches the network or the toolchains folder.
- **`src/toolchains/worker.py`:** sandboxed downloader with publisher adapters for:
  - python-build-standalone, Node.js, Go, Rust, Temurin and CMake
  - SHA-256 checks, and gpgv signature checks restricted to an allowlist of signing keys
  - safe unpacking (data filter, plus refusing absolute paths, `..`, more than 4 GB, or more than 200k files)
  - staging and atomic install, a relative `current` link, and Remove
  - changes run one at a time; fixed PATH and full program paths
- **`src/toolchains/keys/`:** publisher keyrings (node, rust, java, cmake), `allowed-signers.json` and a README with fingerprints and sources. Every fingerprint was cross-checked by hand.
- **`src/toolchains/official-sites.json`:** the only sites the downloader may reach.
- **`src/network/studio_proxy.py`:** `--fixed-allowlist` mode (no pop-ups, nothing saved). Backup in `version-control/network/2026-11-25_1516/`.
- **`src/launcher/linux-studio`:**
  - `--toolchains`, plus the internal `--toolchains-worker` mode (its own sandbox and proxy, stopped when the window closes)
  - `/toolchains` mounted read-only in the editor and shell, with PATH taking the chosen versions
  - Go telemetry off and `GOTOOLCHAIN=local`

  Backup in `version-control/launcher/2026-11-25_1517/`.
- **Runtime:** added `gpgv`, `xz-utils` and a `/toolchains` mount point, then rebuilt. The previous runtime is in `version-control/runtime/2026-11-25_1516/`
  (binary ignored by git; `.gitignore` updated so runtime backups are never committed).
- **Shared GTK style:** explorer styles (sidebar, banner, pills).
- **Tests:** `tests/test_toolchains.py` (17), `tests/toolchains-test.sh` (12), `tests/test_proxy.py` (19). `tests/isolation-test.sh` now expects `/toolchains`.

## Security review (jake-lockley) results
| # | Severity | Finding | Result |
|---|---|---|---|
| 1 | High | Chosen toolchains came first on the worker's PATH, so a fake gpgv or python3 could bypass checks | **Fixed** (fixed PATH and full paths). E2E test plants fake tools and proves they never run. |
| 2 | Medium | Python and Go are checksum-only, from the same source | **Documented**; the window labels them as not signed by the publisher. A decision on stronger options was asked of the PM. |
| 3 | Medium | gpgv accepts any keyring key, including expired, and parsed English text | **Fixed** (`--status-fd`, VALIDSIG, signer allowlist). Unit-tested. |
| 4 | Low | The allowlist includes general GitHub hosts | **Accepted, documented** |
| 5 | Low | Rust's install.sh can write to all toolchains (it's signature-checked) | **Open**; a nested sandbox was suggested and asked of the PM |
| 6 | Low | No caps on message size or archive entries | **Fixed** |
| 7 | Info | Rust version list not signature-checked (downgrade) | **Fixed** |

## Verification
- **Tests:** proxy unit 19/19, toolchains unit 17/17, toolchains e2e 12/12 (real Node.js, Go and CMake installs), network 23/23, isolation 17/17.
- **GUI under Xvfb:** matches mockup screen 4. Install Go → "Installing" → listed; "Use this version" shows "In use" with the link `current -> 1.27.4`; Remove deletes it;
  closing the window stops the downloader, proxy and sandbox (0 left).
- **Research side effect:** the research agent's `gpg` created an empty `~/.gnupg/` in the Codespace home (harmless; left for the PM).

## Impacts
- Linux Studio can now add extra language versions from official publishers. Downloads are verified and installed read-only for the editor.
- No secrets or environment variables introduced.
