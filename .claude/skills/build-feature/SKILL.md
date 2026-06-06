---
name: build-feature
description: Full feature pipeline — research → go/no-go → grill → plan/experiment loop → TDD → docs → independent review → smoke test → user testing → commit. The main session orchestrates; every work phase runs in a dedicated subagent.
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
  ```

## 1. Research (`researcher` agent)

Delegate: assess whether this should be built at all (existing libraries /
OSS / prior art), a light technical overview, and known pitfalls. The agent
returns findings with sources, a build / buy / drop recommendation, and open
questions for planning. Write its result into the design doc under
`## Research`.

## 2. Go/no-go (orchestrator, gate)

Present the recommendation to the user: **build / use library X / drop**.
Record the decision in the design doc. On "drop", stop. On "library",
redirect: the remaining phases apply to the integration, not a from-scratch
build.

## 3. Requirements (orchestrator, interactive)

Invoke `/grill-me`, seeded with the research section and its open questions.
Distill the interview into `## Requirements`: scope, acceptance criteria,
edge cases, non-goals.

## 4. Architecture ↔ experimentation loop

- **Plan** (`planner` agent): the delegation prompt must spell out the
  architecture-doc format — this *overrides the planner's default plan
  shape*: modules/classes and methods with explicit public vs internal
  marking, data flow, Mermaid diagrams (component + sequence where
  meaningful), a named test list (unit + integration), and **Open
  unknowns** — claims the plan rests on that need empirical verification.
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

## 7. Implementation red→green (`implementer` agent, per module)

Delegate module by module in the planned order, each agent getting the
design doc plus which tests it must turn green. Loop until the full suite
is green and every planned module is built. A wrong test comes back to you
as a finding — never weakened silently. Architecture deviations get written
back to the design doc; it must end truthful.

## 8. Documentation

Run `/sync-docs` to update the codebase map in `docs/`. Finalize the design
doc (decisions taken, deviations). Update any feature-level docs this
project keeps (check ProjectCLAUDE.md / existing `docs/` conventions).

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

Hand the running instance to the user and wait. Issues found go back to
phase 7 (and 9 if the fix is substantial). Don't nudge; the user decides
when this phase is done.

## 12. Commit (orchestrator)

On user approval, invoke `/commit` on the feature branch: implementation,
tests, docs, and the design doc. Merging/PR is the user's call — say so and
stop.
