# Linux Studio security log

A running record of security reviews: what was looked at, what was found, and what was done about it. Newest first.
Each review is done by the jake-lockley security agent (Claude) unless stated otherwise. Fixes are approved by the Project Manager.
Earlier reviews (Phases 2 to 6) are recorded in the changelogs under `project-changelog/` and in `project-notes/documents/programming_documentation.md`.

---

## 2026-11-26: dev5 (link router, browser patch, refused notice, CPU and memory limits, fonts)
- **Reviewed by:** jake-lockley (Claude Opus 5.5) · **Fixes by:** Claude Opus 5.5 (Anthropic) · **Approved By:** Project Manager
- **Verdict:** nothing reaches the host desktop. Two Medium issues in the link router were fixed before dev5 shipped.

| # | Severity | Finding | Fix |
|---|---|---|---|
| F1 | Medium | Web links were decoded twice on the way to the in-app tab. Links with `&` were cut short (breaking sign-in links), and a crafted link (`%2F@`) could open a different site than intended. | Links travel base64url-encoded between the in-sandbox `xdg-open` and the router, so no decoding step can change them. Tests: tricky links (`&`, `+`, `%2F`, `%2F@`) in `tests/link-router-test.sh`, and end to end in the real editor. |
| F2 | Medium | Any web page in the in-app browser could drive Linux Studio's own trusted link router with no prompt, opening tabs that open more tabs (local denial of service, or an unprompted phishing tab). | (1) The browser patch refuses the router's own address and accepts callbacks only from the main page, not frames. (2) The router accepts only requests carrying a random per-session key from a read-only file (`/run/linux-studio/link-token`), which web pages can't read. (3) Rate limit (PM decision): at most 3 links per 10 s, the same link repeated within 2 s is ignored, with one warning. Other extensions' sign-in callbacks still work and still ask "Allow …?" (PM decision). |
| F3 | Low–Med | The "Connection refused" notice could cover an approval pop-up whose buttons were already unlocked, so a click aimed at the notice could land on "Allow". | No notice while an approval pop-up is open (it can appear later). The pop-up re-locks its buttons for 1 s whenever it becomes active again. Unit test added. |
| F4 | Low | A timing gap could show a second pop-up for a site that had just been denied. | The saved status is checked again inside the pop-up step. Unit test added. |
| F5 | Low | CPU pinning (`taskset`) could be widened from inside, and there was no cap on the number of processes (fork bombs). | Where systemd's user session allows it: a kernel-enforced `CPUQuota` and `TasksMax=4096` (PM approved). `taskset` stays so programs see the right core count. |
| F6 | Low | The shim passed any `linux-studio://` link through unchecked. | The same strict `<publisher>.<extension>` rule as the browser patch, and the router's own address is refused. |
| F7 | Info | The memory cap stopped programs abruptly, and swap wasn't capped. | `MemoryHigh` at 90% of the cap (slows down first) and `MemorySwapMax` at a quarter of the cap (PM approved). |

**Confirmed safe as is:**
- The sandbox has no D-Bus or portal sockets, and the shim is read-only and first on PATH.
- Shim arguments can't be turned into options.
- The router accepts only http(s) links and refuses `user:password@` links.
- The notice and the Settings window pass everything as argument lists and never use markup.
- Limits apply only to the sandbox.
- The fonts are signature-checked Debian packages under the OFL.

---

## 2026-11-26: dev4 (extension signature checker, Remove my data, pop-up on top)
- **Reviewed by:** jake-lockley (Claude Opus 5.5) · **Fixes by:** Claude Opus 5.5 (Anthropic) · **Approved By:** Project Manager

| # | Severity | Finding | Fix |
|---|---|---|---|
| 1 | Medium | The approval pop-up took keyboard focus, and its 1 s button lock started before it was shown, so typing or clicking on bait could approve a site. | No focus request. The lock starts when the pop-up is shown and restarts on any key press or click. The buttons stay keyboard-reachable (PM decision). |
| 2 | Medium | Remove my data failed on read-only folders (Go module cache, or folders locked on purpose). | Folders are made writable first (`find -xdev`, never following links). Tests with 555 and 000 folders. |
| 3 | Low | The signature archive parser unpacked every entry (memory blow-up). | Only the two needed entries are unpacked, with caps. Zip bombs are refused; a 3,000-case fuzz run peaked at about 150 MB. |
| 4 | Low | The package read was 1.5 GB, and a file could grow between the size check and the read. | The read goes through a single file handle with a limit. The limit is configurable in Settings (PM): 256 MB to 1.5 GB, default 512 MB. |
| 5 | Low | No check that the settings and data folders don't overlap, and no ownership check. | Overlap is refused, and only folders owned by the user are deleted. |
| 6 | Info | A reused process ID could look like a running Linux Studio. | The process start time is stored and compared. |
| 7 | Info | Code inside can turn `extensions.verifySignature` off until restart. | Documented as a known limit. |

**Confirmed safe:**
- No malformed input makes the signature checker report Success.
- The pinned Open VSX key matches the live key.
- The editor refuses installs if the checker fails, is missing, or the signature is stripped.

**Context:** Open VSX signatures only prove Open VSX served what was uploaded, not that an extension is safe (for example the 2025 "GlassWorm" campaign). Keep extensions to a minimum.
