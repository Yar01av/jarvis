---
name: build-feature
description: Full feature pipeline — research → go/no-go → grill → plan/experiment loop → TDD → docs → independent review → smoke test → user testing → commit → kit retrospective. The main session orchestrates; every work phase runs in a dedicated subagent.
argument-hint: "<feature description, or existing feature slug to resume>"
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

**Experimentation is a floating capability, not a fixed phase.** Whenever
any phase surfaces a falsifiable uncertainty — research claims an unproven
library fit, the go/no-go hinges on an unverified capability, the plan
rests on an assumption — dispatch `experimenter` agents *then and there*
and loop back to the phase that raised the question with the verdicts.
Expect multiple back-and-forth cycles across the pipeline; phase 4 is just
where the loop is most common, not the only place it's allowed. All
verdicts accumulate in the design doc's `## Experiments`.

Hard rule for the whole pipeline: **never modify `.claude/` or the
kit-managed `CLAUDE.md` in this project.** Improvement ideas for those are
collected and presented to the user as suggestions only.

## 0. Setup (orchestrator)

- Derive a short `<feature-slug>` from the arguments.
- If `docs/designs/<feature-slug>.md` exists: make sure you're on
  `feature/<slug>` first (`git checkout`; recreate the branch if it's gone),
  then read the checklist and resume at the first unchecked phase. Tell the
  user where you're picking up. A fresh session typically starts on main —
  resuming without the checkout writes feature code to the wrong branch.
- Otherwise: warn if the working tree is dirty, create branch
  `feature/<slug>`, and seed the design doc with this checklist:

  ```markdown
  # <Feature name>

  ## Phases
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

## 1. Research (`researcher` agent)

Delegate: assess whether this should be built at all (existing libraries /
OSS / prior art), a light technical overview, and known pitfalls. The agent
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

Delegate the planned test list: unit + integration tests against the
*public* interfaces from the design doc. Tests must fail **for the right
reason** (missing implementation, not typos/import errors). Require actual
run output in the agent's report; spot-check it.

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

**Before checking this box, sweep for leftover scaffolding:**
`grep -rn 'STUB(<feature-slug>)' <source dirs, excluding docs/>`. Any hit
means a stub was implemented but not cleaned, or a planned symbol was
abandoned in place — resolve it (finish or delete) now. The reviewers
receive the diff in phase 9 and treat a dangling stub on shipped code as a
finding, so an unswept marker just becomes a review blocker. Use the exact
slug token from phase 6 — one-character drift makes the grep silently match
nothing, and a no-op gate reads as "covered" when it isn't.

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

Start the software with the run command from ProjectCLAUDE.md (ask the user
if there is none). Exercise it broadly — the new feature's main flow, the
behavior adjacent to it, logs/console for anomalies. A general-purpose agent
may do the poking; the app itself runs from the orchestrator (background
Bash) so it survives into the next phase. Report what was tried and what was
observed.

## 11. User testing (orchestrator, gate)

Hand the running instance to the user and wait. Every issue the user finds
re-enters the **implement → document → review** loop (phases 7 → 8 → 9) as
one unit — code fix, docs brought current, fresh review — so docs and review
never lag the code. No "trivial vs substantial" triage: every change makes
the full loop. The user decides through their own testing when the loop is
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
