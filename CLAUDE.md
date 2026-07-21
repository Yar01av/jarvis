# Claude Code — Jarvis Kit

Project-specific context lives in `ProjectCLAUDE.md`.

@ProjectCLAUDE.md

## Workflow

- Before non-trivial changes: plan first (use the `planner` agent or `/implement`).
- After changes: run lint + the relevant tests before declaring done.
- Bug fixes: reproduce first (`/fix`), then fix, then prove the repro passes.
- Never commit unless explicitly asked; use `/commit` when asked.

## Model tiering

Cross-cutting policy for every skill that delegates work. Goal: spend the
expensive model only where a wrong call is costly; let cheaper models do the
mechanical work the plan already de-risked.

Three-rung ladder: **`sonnet` (hands) → `opus` (mid) → `fable` (top)**.

- **hands = `sonnet`** — mechanical work where the spec/plan already holds the
  judgment (writing tests to a named list, implementing a specified module,
  docs, commit). This is the default tier for delegated *execution*.
- **brain = `opus`/`fable`** — judgment work where a wrong call is expensive
  (research, architecture/planning, review, root-causing). Which of the two
  depends on the run; a skill that exposes a `--brain` flag resolves it, else
  default `opus`.
- **Gates and orchestration run at the session model** (what `/model` is set
  to). The orchestrator is itself a brain; it delegates the hands work.

**Why hands-tier doesn't drop quality — three nets:**

1. **The plan removes the judgment.** A brain produces a detailed enough plan
   (module shapes, named tests as executable spec) that execution is mechanical.
   Sonnet gets only the *basic* part; the hard thinking already happened.
2. **Escalation.** A hands agent that returns **blocked — couldn't get its
   assigned tests green**, **flags the spec/design as ambiguous**, or **hits
   repeated tool failures** is a signal, not a verdict. Re-dispatch *that unit*
   one rung up the ladder (sonnet → opus → fable). Escalation is per-unit and
   bounded — step up, don't thrash.
3. **Brain review.** Correctness-critical review runs at brain tier so a subtle
   hands-tier slip gets caught before it ships — this is the **last** phase to
   economize on. If a run's brain is forced all the way down to `sonnet`, that
   third net is gone; flag it rather than pretend the guarantee still holds.

**Mechanism:** the delegating orchestrator passes the resolved model as the
Agent tool's `model` param (or, in a Workflow script, per `agent()` call). This
overrides an agent's `model: inherit` frontmatter. **Agents stay
model-agnostic** — the tier is the *caller's* call, made where the run's budget
context lives, so the same agent serves a cheap run and an expensive one.

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
- **Captured lessons live in `docs/solutions/`** (its own `INDEX.md`) — a
  hand-maintained store of gotchas, dead-ends, and decisions from past work,
  separate from the `/sync-docs` tree. Check it when a task smells like
  something the team may have hit before. `/build-feature` writes it (phase 8)
  and reads it (phase 1); `/refresh-solutions` curates it.
- Keep it honest: run `/sync-docs` after changes that alter structure or
  behavior. If `docs/` doesn't exist yet, run `/sync-docs` once to bootstrap.

## Available skills

Run `/skills` to see all loaded skills. Key ones this kit ships:

- `/build-feature` — full feature pipeline: research → grill → plan/experiment → TDD → review → smoke test
- `/implement` — explore → plan → build → verify
- `/fix` — repro-first bug fixing
- `/commit` — scoped commit with hygiene checks
- `/sync-docs` — update `docs/` after structural changes
- `/refresh-solutions` — curate the `docs/solutions/` lessons store (prune stale, merge dupes, fix index)
- `/handoff` — write a session handoff doc
