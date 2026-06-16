# Claude Code — Jarvis Kit

Project-specific context lives in `ProjectCLAUDE.md`.

@ProjectCLAUDE.md

## Workflow

- Before non-trivial changes: plan first (use the `planner` agent or `/implement`).
- After changes: run lint + the relevant tests before declaring done.
- Bug fixes: reproduce first (`/fix`), then fix, then prove the repro passes.
- Never commit unless explicitly asked; use `/commit` when asked.

## Documentation

Docs are the first source of truth for any task — every agent in this repo
(main session and subagents alike) reads the docs relevant to its issue
before gathering information any other way. This saves tokens and gives a
clear, curated picture instead of a raw grep dump.

- **Traverse the index to the leaves.** Start at `docs/INDEX.md`, follow the
  links down the hierarchy into the per-directory indexes for the areas
  you'll touch, and collect what you need there. Re-traverse as often as the
  work requires — multiple passes, multiple branches.
- **Grep / free exploration is the fallback, not the opener.** Only after
  you've traversed the relevant index paths and *still* lack the answer, or
  you spot a contradiction between the docs and the code, are you free to
  gather information however you like (grep, read source, etc.).
- **State the confusion explicitly** whenever you hit that fallback: name the
  gap or contradiction in your output so it can be reflected back into the
  docs. A missing or wrong doc is a finding, not just a detour.
- Keep it honest: run `/sync-docs` after changes that alter structure or
  behavior. If `docs/` doesn't exist yet, run `/sync-docs` once to bootstrap.

## Available skills

Run `/skills` to see all loaded skills. Key ones this kit ships:

- `/build-feature` — full feature pipeline: research → grill → plan/experiment → TDD → review → smoke test
- `/implement` — explore → plan → build → verify
- `/fix` — repro-first bug fixing
- `/commit` — scoped commit with hygiene checks
- `/sync-docs` — update `docs/` after structural changes
- `/handoff` — write a session handoff doc
