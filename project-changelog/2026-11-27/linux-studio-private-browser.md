# Linux Studio: private Firefox browser (blocks dev8)

## Update 13:10 UTC: PM decisions and mockup screen 9 approved
- **Date:** 2026-11-27 · **Time:** about 12:55–13:10 UTC
- **Performed By:** Claude Opus 5.5 (Anthropic), via Claude Code
- **Approved By:** Project Manager ("Looks good to me")

### PM answers to the four open questions (deferred earlier today)
1. **Browser:** Firefox ESR from Debian's signature-checked security archive (not LibreWolf).
2. **Where web links open:** a Settings choice, **defaulting to the private browser**. "Linux Studio tab" keeps the current in-editor tab.
3. **Logins and history:** a Settings choice, **defaulting to "Forget when closed"**. "Remember" keeps them in Linux Studio's private data.
4. **uBlock Origin:** yes, from Debian (`webext-ublock-origin-firefox`), always on.

The PM also accepted the proposed terminal command `linux-studio --private-browser`.

5. **Files (asked with the build plan):** the browser sees **only a `Downloads` folder inside the project folder**, nothing else.

### Changes
- **Mockup screen 9, "Private browser"**, added to `project-notes/mockups/linux-studio-mockups.html`:
  - the Settings section (Open web links in, Logins and history, browser summary, Open private browser)
  - the example of a link opening: an editor link, then the Network inbox, then the browser or the Linux Studio tab
  - the "Linux Studio · Private browser" window (address bar, uBlock counter, a strip saying whether it forgets or remembers)
  - the Remove my data pop-up with the new tick box "Private browser logins and history"
  - The "new" label moved from screen 8 to screen 9. Screens 1–8 are unchanged.
- The PM reviewed a private preview page of screen 9 before it was added to the repo. It used example sites only and nothing from the repo except the mockup styles.

### Impacts
- Documentation and mockups only. No application code, runtime or package changed, so no `version-control/` backup was needed.
- **Next:** a build plan for PM approval: runtime rebuild with Firefox ESR and uBlock Origin (backed up first), the policy file, launcher and link-routing
  changes, Settings, Remove my data, tests, a jake-lockley security review and the docs. Then dev8.
