---
name: build-feature
description: Full feature pipeline — research → go/no-go → grill → plan/experiment loop → TDD → docs → independent review → smoke test → user testing → commit → kit retrospective. The main session orchestrates; every work phase runs in a dedicated subagent.
argument-hint: "<feature description, or existing feature slug to resume> [--from <phase 1-13 or name>] [--brain <fable|opus|sonnet>]"
disable-model-invocation: true
---

Build the following feature end to end: $ARGUMENTS

You are the **orchestrator**. Delegate every work phase to its named agent;
run only the interactive gates yourself (subagents can't talk to the user).
The design doc `docs/designs/<feature-slug>.md` is the shared spec: agents
read it — never assume an agent saw this conversation. **Agents return
results as their final message; you write them into the design doc.** Don't
have agents write the doc themselves: isolated/parallel agents would race or
(in worktrees) silently lose the write. After each phase, check off its box
in the design doc's phase checklist, which is also the resume mechanism.

**A subagent's file edits are not atomic.** When a subagent returns `failed` or
terminates early (spend/usage limit, API error, crash, context exhaustion), treat
any files it was editing as possibly left in an incoherent, half-done state.
Before building on its work, inspect `git diff` and restore a coherent tree —
revert to the last-good state or finish the edit yourself. **A green test suite is
not proof of tree coherence:** a partial edit can pass the whole suite yet be
broken (a re-parented-but-ungridded widget, a half-applied refactor, colliding
layout, or anything the tests don't cover). This applies to every delegated phase,
not one.

**Experimentation is a floating capability, not a fixed phase.** Whenever
any phase surfaces a falsifiable uncertainty — research claims an unproven
library fit, the go/no-go hinges on an unverified capability, the plan
rests on an assumption — dispatch `experimenter` agents *then and there*
and loop back to the phase that raised the question with the verdicts.
Expect multiple back-and-forth cycles across the pipeline; phase 4 is just
where the loop is most common, not the only place it's allowed. All
verdicts accumulate in the design doc's `## Experiments`.

**Visual/UI work is delegable too — use a visual agent if the project has one,
don't assume it does.** When a feature is visual (a desktop GUI, a rendered
layout, a styling change), the design-exploration and visual-QC loop — render the
thing, *look* at it, iterate against a reference — is not orchestrator work to
hand-roll inline (throwaway screenshot scripts, reading PNGs, cropping). **If the
project provides a visual agent** (e.g. a `gui-visual` agent, the way plots go to
`plot-builder` and decks to `deck-builder` where those exist), delegate it there
with an *encapsulated spec* (target file/app + visual reference/palette + which
screen/state + what to check) since it can't see this conversation; it returns
rendered PNGs + a critique + a verdict. **If there is no such agent, don't invent
elaborate tooling** — capture at least one rendered view yourself and inspect it
(never silently skip the *look*). Applies wherever the visual question arises — the
mock loop around phases 2–4 and the visual QC in phases 10–11.

Hard rule for the whole pipeline: **never modify `.claude/` or the
kit-managed `CLAUDE.md` in this project.** Improvement ideas for those are
collected and presented to the user as suggestions only.

## Model tiering (orchestrator)

The base policy — the `sonnet` → `opus` → `fable` ladder, why hands-tier
doesn't drop quality (plan removes judgment + escalation + brain review), and
the `model`-param mechanism — lives in **CLAUDE.md → Model tiering**. This
section adds only what's specific to this pipeline.

- **hands (`sonnet`):** test-writer (6), implementer (7), librarian (8), smoke
  poking (10), commit (12).
- **brain:** researcher (1), planner (4), reviewers (9), kit-retrospective (13).
- **gates run at the session model** (2 Go/no-go, 3 Requirements, 5 Plan
  sign-off, 11 User testing); user controls that with `/model`.

**This pipeline exposes a brain *ceiling* via `--brain`. Resolve in order:**
1. `--brain <fable|opus|sonnet>` if passed → the run's brain ceiling (the model
   for the hardest work).
2. Otherwise default **`opus`**. (No kickoff question — opus is the safe default;
   the user opts up to `fable` or down to `sonnet` when they know their budget.)
3. **Mid-run override at any gate**, in plain language ("use fable for the
   planner this round", "reviewers on sonnet"). Honor it for that dispatch and
   note it in the design doc. This is the case-by-case lever — no new syntax,
   the user is already stopped at the gate.

**The ceiling is a ceiling, not a floor — spend it only where it pays.** When
the ceiling is `fable`, brain phases split: the *hardest* (planner (4),
reviewers (9)) run at `fable` = `brain-top`; the *sort-of-hard* (researcher (1),
kit-retrospective (13)) drop one rung to `opus` = `brain-mid`. Announce the rung
and recommend the drop; the user vetoes for full ceiling. At ceiling `opus`,
top = mid = opus; at `sonnet`, the whole run is hands (escalation still applies).

**Experimenter (phase 4) is decided per experiment.** Before dispatching, tell
the user what each spike is and **recommend a tier** — hands for a small,
self-contained spike; brain when the verdict will steer the architecture — then
let them confirm or override.

| Phase | Agent | Tier |
|---|---|---|
| 1 Research | researcher | brain-mid |
| 4 Architecture | planner | brain-top |
| 4 Experiments | experimenter | per-experiment (recommend, then confirm) |
| 6 Tests red | test-writer | hands |
| 7 Implementation | implementer | hands |
| 8 Docs | librarian | hands |
| 9 Review | code-reviewer + maintainability-reviewer | brain-top |
| 10 Smoke | general-purpose | hands |
| 12 Commit | /commit | hands |
| 13 Retrospective | kit-retrospective | brain-mid |

## 0. Setup (orchestrator)

- Derive a short `<feature-slug>` from the arguments.
- If `docs/designs/<feature-slug>.md` exists: make sure you're on
  `feature/<slug>` first (`git checkout`; recreate the branch if it's gone),
  then read the checklist. Tell the user where you're picking up. A fresh
  session typically starts on main — resuming without the checkout writes
  feature code to the wrong branch.
- Otherwise: warn if the working tree is dirty, create branch
  `feature/<slug>`, and seed the design doc with this checklist (applying
  `--from`, below, before you start work):

  ```markdown
  # <Feature name>

  ## Phases
  <!-- [ ] todo · [x] done · [-] skipped (--from) -->
  - [ ] 1 Research
  - [ ] 2 Go/no-go
  - [ ] 3 Requirements (grill)
  - [ ] 4 Architecture (incl. experiments)
  - [ ] 5 Plan sign-off
  - [ ] 6 Tests red
  - [ ] 7 Implementation green
  - [ ] 8 Documentation
  - [ ] 9 Review passed
  - [ ] 10 Smoke test
  - [ ] 11 User testing
  - [ ] 12 Committed
  - [ ] 13 Kit retrospective
  ```

- **Then (both branches), begin work at the first `[ ]` phase in the
  checklist.** This is the single control rule that routes every run — fresh,
  resumed, or skipped. Treat `[x]` (done) and `[-]` (skipped via `--from`)
  **identically: already handled — never execute or resume into them.** With
  no `--from`, the first `[ ]` is phase 1, so a normal run starts at Research.
  With `--from 4`, phases 1-3 are `[-]`, so you start at phase 4. Announce the
  starting phase to the user.

### Skipping the front phases (`--from`)

For a tight feature that needs little or no prior research, the user may pass
`--from <phase>` (a number `1-13` or a phase name like `plan`/`planner`) to
start partway in. **No new control path** — at seed time, mark every phase
*before* the target as `[-]` (skipped — never `[x]`, which would claim work
that never happened). The "begin at the first `[ ]` phase" rule above then
lands you on the target. Note the skip in the design doc so the record stays
truthful.

Guardrails:

- **Only the front phases (1-3: Research, Go/no-go, Requirements) are freely
  skippable.** The tests → implementation → review spine (6+) is mandatory —
  refuse to skip past it; that's where correctness is enforced (this mirrors
  CE's own "skip ideation, never skip review"). Skipping straight to 4
  (planner) is the common, supported case. This holds **regardless of
  deliverable shape**: a config / schema / workflow feature with no unit-test
  suite still runs the full spine — "there are no tests here" is never a reason
  to skip 6–9. See the *deliverable shape* note at phase 6 for how red / green /
  run generalize beyond executable code.
- **No fake sections.** Don't fabricate a Requirements or Research section for
  a skipped phase. When you skip to the planner (4), pass it the feature
  description directly and instruct it to surface any missing context as
  **Open unknowns**. The phase 5 plan-gate is the safety net — the user catches
  a wrong abstraction there before any test is written.
- If a downstream phase turns out to genuinely need a skipped phase's output,
  say so and offer to run that phase now rather than guessing.

### Stopping early (`--to`)

`--to <phase>` runs the pipeline through the target phase and then **stops**
instead of continuing to commit/retrospective — e.g. `--to 5` for a plan-only
run (architecture + sign-off, no code), or `--to plan`. Combine with `--from`
for a slice (`--from 4 --to 5`). On reaching the target, check its box, tell
the user where you stopped and how to resume (`/build-feature <slug>` picks up
at the next unchecked phase), and stop — do not run later phases. `--to` may
land before the test/impl spine (a plan-only run is fine); it just defers the
spine to a later resume, it never skips it.

## 1. Research (`researcher` agent)

Delegate: assess whether this should be built at all (existing libraries /
OSS / prior art), a light technical overview, and known pitfalls. Have the
agent read `docs/solutions/INDEX.md` first (if it exists) as the first stop for
prior art *within this codebase* — durable lessons captured by earlier runs
(phase 8) live there and may already answer an open question or flag a known
dead-end. The agent
returns findings with sources, a build / buy / drop recommendation, and open
questions split into *decisions for the human* (feed the grill) and
*empirical uncertainties* (track these — they must not get lost between
phases). Spike uncertainties **now** when the build/buy/drop call or the
upcoming grill would benefit from the answer (research ↔ experiment is a
loop, per the floating-experimentation rule); the rest carry forward to
planning. Write the result into the design doc under `## Research`.

## 2. Go/no-go (orchestrator, gate)

Present the recommendation to the user: **build / use library X / drop**.
Don't carry a guess into this gate: if the recommendation hinges on an
unverified claim, run the experiment first. Record the decision in the
design doc. On "drop", stop. On "library",
redirect: the remaining phases apply to the integration, not a from-scratch
build.

## 3. Requirements (orchestrator, interactive)

Invoke `/grill-me`, seeded with the research section and its *decisions for
the human* (the empirical uncertainties are not grill material — they wait
for the experimenter). Distill the interview into `## Requirements`: scope,
acceptance criteria, edge cases, non-goals.

## 4. Architecture ↔ experimentation loop

- **Plan** (`planner` agent): the delegation prompt must spell out the
  architecture-doc format — this *overrides the planner's default plan
  shape*: modules/classes and methods with explicit public vs internal
  marking, data flow, Mermaid diagrams (component + sequence where
  meaningful), a named test list (unit + integration), and **Open
  unknowns** — claims the plan rests on that need empirical verification.
  Pass the research phase's *empirical uncertainties* into this prompt and
  require a disposition for each: resolved with cited evidence, needs a
  user decision (→ plan gate), or open unknown (→ experiment). None may
  silently disappear.
- **Skepticism check**: a first-cycle plan with zero open unknowns on a
  non-trivial feature is a smell, not a green light — especially when
  research flagged uncertainties. Challenge it once ("which of these claims
  have you actually verified?") before accepting. Bias toward
  experimenting: an hour of spiking is cheaper than a wrong architecture.
- **Experiment** (`experimenter` agent, one per unknown, parallel when
  independent, `isolation: worktree`): each agent gets ONE question and
  answers it with the smallest spike that yields a verdict. Spike code never
  lands on the feature branch; you write the returned verdicts + evidence
  into `## Experiments`.
- **Loop**: re-run the planner with the experiment results. Cycle
  plan ↔ experiment as often as needed; summarize each cycle to the user.
  Unknowns that need a *user decision* rather than an experiment go to the
  plan gate instead.
- Exit when the plan has no blocking unknowns. Write the final architecture
  into `## Architecture`.

## 5. Plan sign-off (orchestrator, gate)

The user reviews the architecture before any tests are written. Catching a
wrong abstraction here is 10x cheaper than after red→green. Apply revisions
(re-entering the loop above if they're structural) until signed off.

## 6. Tests red (`test-writer` agent)

**First, classify the deliverable shape** — the spine (6→7, and the run in
10→11) is written for *executable code with a test suite*, but not every
feature has that shape. The spine is **mandatory for every shape** (per the
phase-0 guardrail); only the *form* of red → green → run changes, and you carry
the chosen shape through to phases 7/10/11. Name it in the design doc.

- **Executable code** — red/green is a test suite: a failing assertion /
  `NotImplementedError`, then passing. The STUB mechanism and the phase-7 sweep
  below apply. This is the default; the rest of this phase is written for it.
- **Declarative artifact** (config, IaC, schema, a workflow / pipeline
  definition) — there is no code unit to assert against, but there is still an
  observable red → green: exercise the artifact through its own toolchain
  (validate → register / apply → run) and assert on the *result*. Here "the
  planned test list" becomes the set of validation checks (the run's expected
  outputs / rejections), and "fail for the right reason" becomes "the pre-change
  run fails at validation." The STUB mechanism does **not** apply (no code
  symbols to stub), so the phase-7 sweep is N/A for this shape.

**Whichever shape: observe the red before you implement.** A spine that only
ever saw green proved nothing — for a declarative artifact that means running
the toolchain *before* the change and seeing the real failure (schema
rejection, unresolved reference, missing expected output key), not assuming it.
The concrete toolchain (how to validate / register / run) is project-specific —
keep it in ProjectCLAUDE.md, not here.

Delegate the planned test list: unit + integration tests against the
*public* interfaces from the design doc. Tests must fail **for the right
reason** (missing implementation, not typos/import errors). Require actual
run output in the agent's report; spot-check it.

*(Executable-code shape only — skip this paragraph for a declarative artifact.)*
When a planned public symbol doesn't exist yet, instruct the test-writer to
add a **minimal stub** for it (signature / dataclass shape only — a body that
raises or returns nothing, never real logic) marked `# STUB(<feature-slug>):`
so the red is an assertion / `NotImplementedError` failure rather than an
import-/collection-time error. Two guards: the stub must still leave the test
**failing** (a stub that accidentally satisfies a test makes the red fake),
and it stays minimal — the moment a stub grows logic, the test-writer has
started implementing. These markers are the contract the phase-7 sweep clears.

## 7. Implementation red→green (`implementer` agent, per module)

Delegate module by module in the planned order, each agent getting the
design doc plus which tests it must turn green. In the delegation prompt,
tell the implementer to **remove each `# STUB(<feature-slug>):` marker as it
fills that symbol in**, and to **delete — not leave defined — any planned
symbol it diverges from and no longer uses** (a dataclass/function the doc
named but the implementation routed around). Loop until the full suite
is green and every planned module is built. A wrong test comes back to you
as a finding — never weakened silently. Architecture deviations get written
back to the design doc; it must end truthful.

Implementers run at **hands (`sonnet`)** — safe here because the plan and the
red tests already hold the judgment (CLAUDE.md → Model tiering). **Escalation:**
an implementer that returns blocked — can't get its tests green, flags the
design doc as ambiguous, or hits repeated tool failures — is re-dispatched for
*that module* one rung up the ladder. Step up, don't thrash; a module that
fails twice above hands is a plan problem — kick it back to the plan gate.

**Multi-module fan-out (opt-in Workflow mode).** When the plan has several
modules, you may offer a Workflow-driven implementation instead of dispatching
them by hand: you (the brain) author a script that runs one `implementer` per
module **in sequence** (`for (const m of modules) await agent(prompt, {model:
'sonnet'})`), each with an exact, pre-written prompt, so the hand-off is
*deterministic* rather than improvised — that determinism is the win, not tokens
or speed (see CLAUDE.md → Model tiering).

**Sequential, not parallel — deliberately.** Implementers mutate the shared
working tree and run the suite to confirm green; concurrent modules would race
(half-written files, one agent's "green" invalidated by another's edit,
conflicts on shared `__init__`/import/registry files) — and "independent"
modules routinely still touch those shared files. Real parallelism would need
`isolation: worktree` plus a merge-back step this pipeline doesn't specify;
don't reach for it. Bake the escalation rule into the loop (a blocked
implementer re-runs one rung up). **Recommend the workflow only when modules are
many; skip it for one or two — and never run it without the user's OK** (a
workflow can spawn many agents). Un-annotated `agent()` calls inherit the
*session* model, so set `model: 'sonnet'` on every implementer explicitly or the
hands saving evaporates. Tests-still-green and the STUB sweep below apply
identically.

**Before checking this box, if you used the STUB mechanism in phase 6
(executable-code shape), sweep for leftover scaffolding:**
`grep -rn 'STUB(<feature-slug>)' <source dirs, excluding docs/>`. Any hit
means a stub was implemented but not cleaned, or a planned symbol was
abandoned in place — resolve it (finish or delete) now. The reviewers
receive the diff in phase 9 and treat a dangling stub on shipped code as a
finding, so an unswept marker just becomes a review blocker. Use the exact
slug token from phase 6 — one-character drift makes the grep silently match
nothing, and a no-op gate reads as "covered" when it isn't. (For a declarative
artifact no stubs were introduced, so there is nothing to sweep — don't run a
grep that can only ever match nothing and mistake it for a passed gate; instead
confirm the green run from phase 6's validation checks.)

## 8. Documentation

Not optional, and not foldable into review. Split by *information source* —
code-derived docs go to the specialist; conversation-derived state stays with
you, because only you hold the context to write it:

1. **Code-derived docs (`librarian` agent).** Delegate: bring the `docs/`
   codebase map current (it invokes `/sync-docs`) and update the
   feature-level docs this project keeps to match existing conventions. The
   librarian reads the code directly, so it needs none of this conversation —
   but it also can't write what isn't in the code. Write its returned report
   into the design doc and act on its flags.
2. **Finalize the design doc (orchestrator).** Decisions taken, deviations
   from the plan — this is conversation-derived rationale the librarian
   doesn't have, and the design doc is your resume state, so you own it. If
   the librarian flagged a stale design/rationale doc, fix it here.
3. **Compound durable lessons → `docs/solutions/` (orchestrator writes).**
   The whole point of the pipeline compounding: a non-obvious lesson this run
   surfaced should make the *next* feature cheaper. A solution doc is
   **conversation-derived** — only you hold the failed-experiment / gotcha
   context — so by this phase's own source-split rule, *you* write it, not the
   librarian (which stays code-only). Capture is **conditional, not
   automatic**: write a doc **only when the run produced a genuinely reusable
   lesson** — a failed experiment worth not repeating, a gotcha, a non-obvious
   fix or constraint (much of it already sits in `## Experiments` and the plan
   deviations). A routine build writes nothing — `docs/solutions/` must stay
   signal-dense, not a per-feature log. When it qualifies, write
   `docs/solutions/<category>/<slug>.md` with minimal frontmatter
   (`name`, `description`). Keep categories light (e.g. `gotchas/`,
   `patterns/`, `decisions/`); don't invent a deep taxonomy.

   **The store self-indexes — `/sync-docs` deliberately skips `docs/` itself,
   so don't expect the librarian to pick these up.** You maintain it: append a
   one-line pointer (`- [title](category/slug.md) — hook`) to
   `docs/solutions/INDEX.md` (create it the first time, MEMORY.md-style). Don't
   wire it into the root `docs/INDEX.md` — that file is sync-managed and would
   drop a non-source link on the next sync; cross-agent discovery rides on the
   CLAUDE.md docs-first note instead.

   **Retrieval:** the phase 1 `researcher` delegation reads
   `docs/solutions/INDEX.md` first (already instructed), so future runs find
   prior lessons without a grep. `/refresh-solutions` is the companion skill
   that keeps the store curated and the index honest over time.

Do not enter phase 9 with this box unchecked — the reviewers receive the
docs as part of the diff and treat stale or missing documentation as
findings, so skipping this phase just converts it into review blockers.

## 9. Review loop (`code-reviewer` + `maintainability-reviewer`, parallel)

- Launch both as fresh subagents with only the diff and the design doc —
  no implementation context. That isolation is the point: they check the
  work, not the intentions.
- **Show the user each review summary** (verbatim findings, not your gloss).
- Fix blockers and should-fixes with phase 6–7 discipline (tests stay
  green), then re-review. **Max 2 fix rounds**; if the third review still
  has blockers, stop and hand the open findings to the user.
- Prompt/instruction improvement ideas from reviewers (e.g. "this LLM
  artifact keeps appearing — instruction X would prevent it") are collected
  under `## Kit suggestions` in your report to the user. Suggestions only —
  see the hard rule above.

## 10. Smoke test

Exercise the deliverable end to end (per the *deliverable shape* chosen at
phase 6) and report what was tried and what was observed.

- **Long-lived app** — start the software with the run command from
  ProjectCLAUDE.md (ask the user if there is none). Exercise it broadly: the
  new feature's main flow, adjacent behavior, logs/console for anomalies. A
  general-purpose agent may do the poking; the app itself runs from the
  orchestrator (background Bash) so it survives into the next phase.
- **Run-to-completion artifact** (declarative workflow, batch job, one-shot
  script) — there is no persistent process to keep alive; "smoke" is a full
  end-to-end run through the real toolchain on representative input, checking
  the produced output + logs for anomalies. This may already be the same run
  that turned phase 6 green; if so, exercising a *broader* input here (more
  cases, the adjacent path) is what makes it a smoke test rather than a repeat.

For a **visual/UI** feature the smoke also includes *looking at the rendered
result*, not just exercising flows — a "tests pass / widget tree is right" check
is blind to layout, alignment, and styling defects. If the project has a visual
agent (e.g. `gui-visual`), delegate that render-and-look QC to it with an
encapsulated spec; if not, capture at least one rendered view yourself and inspect it.

## 11. User testing (orchestrator, gate)

Hand the deliverable to the user and wait. For a long-lived app that's the
running instance; for a run-to-completion artifact (per phase 6's shape) it's
the run command + representative input so the user can exercise it themselves,
plus the last run's outputs to inspect — there's no persistent instance to hand
over. Every issue the user finds re-enters the **implement → document →
review** loop (phases 7 → 8 → 9) as one unit — code fix, docs brought current,
fresh review — so docs and review never lag the code. No "trivial vs
substantial" triage: every change makes the full loop.

**Diagnose before you implement when the cause isn't obvious.** The loop starts
at "implement," which assumes you already know *what* to fix. When a user-found
issue's cause is unclear — especially a non-deterministic, hard-to-reproduce, or
"works here but not there" defect — do **not** start guessing fixes inline.
Dispatch the **`debugger`** agent first: it root-causes in its own context
(minimal repro, instrumentation, hypothesis-falsification) and returns the cause
+ a proposed fix, so the bisecting odyssey never floods the orchestrator's
context. *Then* enter implement → document → review with the diagnosis in hand.
(Same applies to a defect surfaced during the phase-10 smoke test.) Skip the
debugger only when the fix is genuinely obvious from the report.

The user decides through their own testing when the loop is
done; don't nudge. Only when they're satisfied do you proceed to commit —
with docs and review guaranteed current against the final code.

## 12. Commit (orchestrator)

On user approval, invoke `/commit` on the feature branch: implementation,
tests, docs, and the design doc. Merging/PR is the user's call — say so and
stop.

## 13. Kit retrospective (`kit-retrospective` agent)

The run is locked in — now reflect on the *pipeline that produced it*, not
the code (the phase-9 reviewers already owned the diff). Dispatch the
`kit-retrospective` agent to mine the raw run for kit-improvement ideas.

Your only job is to hand over paths — never a summary. A summary would let
you frame the run before the agent sees it; the agent reads the unfiltered
transcript precisely so it isn't influenced. Resolve this session's
transcript deterministically (concurrency-safe — session ids are unique, so
this works even with other sessions open in the same repo):

```bash
find ~/.claude/projects -maxdepth 2 -name "$CLAUDE_CODE_SESSION_ID.jsonl"
```

Pass the agent: that transcript path, its `<session-id>/subagents/` dir (same
path with `.jsonl` → `/subagents/`), the design doc path, and the kit
instruction locations (`.claude/skills/build-feature/SKILL.md`,
`.claude/agents/*.md`). The agent digests transcripts in its own context and
returns only a short list of suggestions, so the run's bulk never enters
yours.

**Present the returned suggestions to the user verbatim** under
`## Kit suggestions` in the design doc (folding in any the phase-9 reviewers
already left there). Suggestions only — per the hard rule at the top, never
modify `.claude/` or kit-managed files, even though in this repo the kit *is*
the product. The user decides what to apply.
