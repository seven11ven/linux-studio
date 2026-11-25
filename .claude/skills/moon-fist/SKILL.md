---
description: Security standards for proper handling of consumer and proprietary data, along with secure storage and appropiate measures taken for the protection of project keys and other critical infrastructure.
---

# Moon Fist

Before acting, read `/project-guidelines/*.md` (Security, Implementation, Documentation) and `CLAUDE.md`; they apply to everything you do.

When auditing the project or any programming action:
1. If the program pulls a package, ensure the it is the latest version(lts) and alert the user of any known issues in said package(if package repo is publicly available)
2. Always keep code up to OWASP and OSINT standard when able to. Do not break system functionalities. 
3. Always refer auditing data from credible, reputable sources. A confidence rate of 80% or higher is preferred
4. DO NOT reveal any values of critical components, infrastructure, or keys.

## Required Output

Return:

- A summary of the audit, with sources and confidence ratings cited
- A plan the main agent can implement, with user questions respected and asked.
- A summary of the risks detected with proper prevention methods included
- A updated "security_log.md" file in project-notes for record keeping
- A small section summary of any social media experiences that were recurring patterns related to your findings.