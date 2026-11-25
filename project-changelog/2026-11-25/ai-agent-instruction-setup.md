# AI agent instruction setup

- **Date:** 2026-11-25
- **Time:** 12:25–12:28 UTC
- **Performed By:** Claude Opus 5.5 (Anthropic), via Claude Code
- **Approved By:** Project Manager

## Changes

1. **Removed** the empty "Workflow" section from `guidelines/Implementation.md` (per Project Manager).
2. **Added `AGENTS.md`** (root): the main instruction file telling every AI agent/LLM to read all
   of `/guidelines` in full before any action, plus a short summary of the core rules.
3. **Added tool-specific pointer files**, each directing that tool's agent to `AGENTS.md` and `/guidelines`:

   | File | Tool(s) |
   |---|---|
   | `CLAUDE.md` | Claude Code (auto-imports AGENTS.md and all four guideline files) |
   | `GEMINI.md` | Gemini CLI |
   | `.github/copilot-instructions.md` | GitHub Copilot |
   | `.cursor/rules/guidelines.mdc` | Cursor (`alwaysApply: true`) |
   | `.windsurf/rules/guidelines.md` | Windsurf (`trigger: always_on`) |
   | `.clinerules` | Cline / Roo |
   | `.junie/guidelines.md` | JetBrains Junie |
   | `CONVENTIONS.md`, `.aider.conf.yml` | Aider (loads all guideline files read-only) |

4. **Created `project-notes/documents/`** containing placeholder `programming_documentation.md`
   and `feature_documentation.md` (title only), as required by `guidelines/Documentation.md`.

## Impacts

- Supported AI tools will load the project guidelines automatically at the start of a session.
- `/guidelines` remains the single source of truth; the pointer files hold no copies of the rules,
  so they will not drift out of sync when guidelines change.
- Limitation: these files are conventions. They cannot force compliance from tools that ignore
  project instruction files or have them disabled.
- `guidelines/Linux Packaging.md` was renamed to `guidelines/Linux-Packaging.md` by the Project Manager
  (12:27 UTC); all references updated and `CLAUDE.md` now auto-imports all four guideline files.
- No application code, dependencies, secrets or environment variables affected. No version-control
  backup required (documentation only, per `guidelines/Implementation.md`).
