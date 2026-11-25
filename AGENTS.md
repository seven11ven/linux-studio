# AGENTS.md — Mandatory instructions for ALL AI agents and LLMs

This file applies to **every** AI agent, assistant, or LLM working in this repository,
regardless of brand or tool (Claude, GPT/Codex, Gemini, Copilot, Cursor, Windsurf,
Cline, Roo, Aider, Junie, Zed, Amp, Jules, or any other).

## STOP — Read the guidelines before doing anything

Before carrying out **ANY** action in this repo (including planning, editing, running
commands, installing dependencies, building, or committing), you MUST read **every file**
in [`/guidelines`](guidelines/) **in full** and follow them **to the letter**:

1. [`guidelines/Security.md`](guidelines/Security.md)
2. [`guidelines/Implementation.md`](guidelines/Implementation.md)
3. [`guidelines/Documentation.md`](guidelines/Documentation.md)
4. [`guidelines/Linux-Packaging.md`](guidelines/Linux-Packaging.md)

The files in `/guidelines` are the single source of truth. If anything in this file or
any other agent-instruction file conflicts with `/guidelines`, **`/guidelines` wins**.
If a guideline is unclear, ask the Project Manager (the user) before acting.

## Non-negotiable summary (not a substitute for reading the full guidelines)

- **Plan first, get explicit permission.** Reading is fine. Never make any change
  (permanent or temporary) without first presenting a plan and receiving explicit approval
  from the Project Manager.
- **Ask questions** whenever anything about the project or the change is uncertain.
- **Log every action** in `/project-changelog/YYYY-MM-DD/` (time done, details, impacts,
  "Performed By" with your model/brand, "Approved By").
- **Back up prior versions** of changed application components in
  `/version-control/<component>/<YYYY-MM-DD_HHMM>/<file>` (never secrets; not docs).
- **This repo is PUBLIC.** Never expose secrets, keys, API values, webhooks, or PII in
  code, commits, terminal output, or chat. Only one `.gitignore` and one `.env`, both in the
  root. Keep `/.gitignore` and `/.env_example` (empty values only) up to date.
- **Keep documentation current** in `/project-notes/documents/`.
- **Free, privacy-respecting, secure dependencies only** — verify fully; inspect for telemetry.
- **UI work requires mockups** — ask the Project Manager what form they want first.
- **Commands needing root:** tell the user to run them themselves.
- **Builds** follow `guidelines/Linux-Packaging.md` exactly; always ask dev vs release;
  never delete old builds without explicit permission.
