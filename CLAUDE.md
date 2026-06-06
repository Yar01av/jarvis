# Claude Code — Jarvis Kit

Project-specific context lives in `ProjectCLAUDE.md`.

@ProjectCLAUDE.md

## Workflow

- Before non-trivial changes: plan first (use the `planner` agent or `/implement`).
- After changes: run lint + the relevant tests before declaring done.
- Bug fixes: reproduce first (`/fix`), then fix, then prove the repro passes.
- Never commit unless explicitly asked; use `/commit` when asked.

## Documentation

- Read `docs/INDEX.md` at the start of non-trivial work; drill into
  the per-directory indexes for areas you'll touch. Keep it honest: run
  `/sync-docs` after changes that alter structure or behavior.
- If `docs/` doesn't exist yet, run `/sync-docs` once to bootstrap it.

## Available skills

Run `/skills` to see all loaded skills. Key ones this kit ships:

- `/implement` — explore → plan → build → verify
- `/fix` — repro-first bug fixing
- `/commit` — scoped commit with hygiene checks
- `/sync-docs` — update `docs/` after structural changes
- `/handoff` — write a session handoff doc
