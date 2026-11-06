# Claude Code — Jarvis Kit

Project-specific context lives in `ProjectCLAUDE.md`.

@ProjectCLAUDE.md

## Workflow

- Before non-trivial changes: plan first (use the `planner` agent or `/implement`).
- After changes: run lint + the relevant tests before declaring done.
- Bug fixes: reproduce first (`/fix`), then fix, then prove the repro passes.
- Never commit unless explicitly asked; use `/commit` when asked. One
  exception: `wip(<slug>)` checkpoint commits inside a user-approved
  `/build` (or `/tree-build`) run (consented at its phase 0) — they stay on the feature
  branch, and the orchestrator reconciles them at phase 12 (squash-or-keep,
  the user's call) before `/commit` runs. The same exception covers
  `construct(<slug>)` checkpoint commits that `board.py checkpoint` makes inside
  a user-approved `/construct` run (consented at its step 0). They go on the run's
  `construct/<slug>` branches, are never pushed, and `board.py rollback` prints how
  to undo them.

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
- **If `docs/INDEX.md` doesn't exist, there is no tree to traverse** — skip
  the traversal entirely and go straight to the fallback; don't burn lookups
  rediscovering the absence. Note "docs tree missing" once in your output
  instead.
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
  something the team may have hit before. `/build` writes it (phase 8)
  and reads it (phase 1); `/refresh-solutions` curates it.
- Keep it honest: run `/sync-docs` after changes that alter structure or
  behavior. If the project keeps a `docs/` tree that was never bootstrapped,
  run `/sync-docs` once to bootstrap it — but some repos deliberately keep
  none (see `ProjectCLAUDE.md`); don't create the tree against that choice.

## Available skills

Run `/skills` to see all loaded skills. Key ones this kit ships:

- `/build` — delivery pipeline for any deliverable (code, doc, deck, workflow, dataset): research → grill → plan/experiment → validate → build → review. TDD literally for code; the same discipline generalised for everything else — define the observable failure first, see it, then build
- `/tree-build` — **parked, unvalidated** — recursive `/build` (per-node subloops, parallel siblings); blocked because subagents can't spawn subagents. Kept as a design record; `/build` covers composite deliverables
- `/construct` — delivery by a team: the main session leads agents through a Kanban board of cards, with file and resource locks, a run branch, a checkpoint commit per card, a rollback plan and a live viewer. Single-lane by default; parallel lanes when you ask for them
- `/board` — bring a `/construct` run's live board viewer back up
- `/implement` — explore → plan → build → verify
- `/fix` — repro-first bug fixing with fail-on-revert proof and docs close-out
- `/commit` — scoped commit with hygiene checks
- `/sync-docs` — update `docs/` after structural changes
- `/refresh-solutions` — curate the `docs/solutions/` lessons store (prune stale, merge dupes, fix index)
- `/handoff` — write a session handoff doc
- `/grill-me` — stress-test a plan via relentless one-question-at-a-time interview
- `/explain-skill` — explain another skill's source in depth
- `/write-a-skill` — author a new skill properly
- `/caveman` — ultra-terse response mode


## Verification

**My time is the scarcest resource in the loop.** Every question, every "want
me to check X?", every turn that ends waiting on me costs more than minutes of
your tool calls. So: if you *can* verify something yourself in reasonable time
(rough bar: a few minutes of reads, greps, script runs, API/MCP calls, a small
spike), **do it first — don't offer to do it.** "I could verify this if you
like" / "shall I check?" is the wrong move when the check is cheap; run the
check and come back with the answer. Use every means available: docs,
`docs/solutions/`, memory, source, git history, running the code, the MCP
servers, the project's own APIs (read-only), a browser session, subagents in
parallel.

Low-level technical sub-questions are yours to decide — don't escalate them.
What matters is that the code is safe, reliable and clean. When an assumption
underneath a decision feels flimsy, **verify it** rather than asking or quietly
accepting it. Grade the verification to its cost: a source read beats a spike
beats a guess, and a one-minute read is almost never worth a round trip to me.

Only stop and ask when:

- the decision is genuinely mine — scope, semantics, risk appetite, anything
  outward-facing (sending, publishing, writing to live/customer systems,
  repointing a prod label);
- verifying would itself be a side-effecting or irreversible action;
- the check is truly expensive (long runs, lots of spend) — then say what it
  would cost and recommend whether it's worth it;
- you're blocked on something only I have (VPN down, a login, a missing
  secret) — and then ask once, precisely, after exhausting the alternatives.

If a check is denied or blocked, try the other legitimate routes before
coming to me. When something stays unverified, say so plainly instead of
letting it pass as settled.
