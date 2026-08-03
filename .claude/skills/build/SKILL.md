---
name: build
description: Full delivery pipeline for any deliverable — research → go/no-go → grill → plan/experiment loop → validation-first build (TDD for code, the same discipline for every other medium) → docs → independent review → smoke test → user testing → commit → kit retrospective. The main session orchestrates; every work phase runs in a dedicated subagent. For a contained change that needs no signed-off plan, independent review or durable record, use `/implement` instead. A composite deliverable — parts validated differently — is handled here, by naming each part's check additively in one contract.
argument-hint: "<deliverable description, or existing slug to resume> [--from <phase or name>] [--to <phase or name>] [--brain <fable|opus|sonnet>]"
disable-model-invocation: true
---

Build the following deliverable end to end: $ARGUMENTS

You are the **orchestrator**. Delegate every work phase to its named agent;
run only the interactive gates yourself (subagents can't talk to the user).
**Know your roster before you start: skim the Agent-tool's available-agents list
(it comes with a description per agent; `.claude/agents/` is the backing registry)
so you know which specialist agents *this project* ships beyond the named phase
agents — a visual/GUI, plots, decks, or other domain agent. When a phase's work
matches one, delegate to it instead of hand-rolling; the roster is discovered each
run, so a newly-added agent needs no change here.**
The design doc `docs/designs/<feature-slug>.md` is the shared spec: agents
read it — never assume an agent saw this conversation. **Agents return
results as their final message; you write them into the design doc.** Don't
have agents write the doc themselves: isolated/parallel agents would race or
(in worktrees) silently lose the write. After each phase, check off its box
in the design doc's phase checklist, which is also the resume mechanism.
The doc's authority is scoped: it is the source of truth for *decisions and
progress*; git and the working tree are the source of truth for *code state*
— never infer tree coherence from the doc (see the atomicity caveat below).

**A subagent's file edits are not atomic.** When a subagent returns `failed` or
terminates early (spend/usage limit, API error, crash, context exhaustion), treat
any files it was editing as possibly left in an incoherent, half-done state.
Before building on its work, inspect `git diff` and restore a coherent tree —
revert to the last-good state or finish the edit yourself. **A green test suite is
not proof of tree coherence:** a partial edit can pass the whole suite yet be
broken (a re-parented-but-ungridded widget, a half-applied refactor, colliding
layout, or anything the tests don't cover). This applies to every delegated phase,
not one.

**Checkpoint commits give that recovery a ref to stand on.** At phase 0, ask
once: *"this run makes `wip(<slug>)` checkpoint commits on the feature branch,
reconciled at phase 12 — OK?"* On consent, commit `wip(<slug>): <what>` after
seeding the design doc, after phase 6 (validation red), after each phase-7
milestone lands (a module green, a draft assembled), and after each batch close-out (phases 9/11 and the pre-12 full
close-out) — logging each SHA as an event in the close-out ledger. Stage
explicitly (`git add <paths>`), never `git add -A`: concurrent spike worktrees
and stray files must not ride along. The atomicity recovery above then becomes
concrete: `git diff <last-checkpoint>`, restore from it. Reconciliation is the
**orchestrator's** job at phase 12, not `/commit`'s (that skill neither
squashes nor amends — see phase 12 for the mechanism); squash-or-keep is the
user's call there. A run that ends before phase 12 (`--to`, a review halt, an
abandon) leaves the chain live — say so and offer to reconcile on the spot.
After any early reconcile, set the ledger header's `base` to the new HEAD: a
later phase-12 squash must never rewind past an already-reconciled commit.
If the user declines checkpoints, run without them; the delta-review and
recovery steps below fall back to dirty-diff mechanics (weaker — say so when
it bites).

**Experimentation is a floating capability, not a fixed phase.** Whenever
any phase surfaces a falsifiable uncertainty — research claims an unproven
library fit, the go/no-go hinges on an unverified capability, the plan
rests on an assumption — dispatch `experimenter` agents *then and there*
and loop back to the phase that raised the question with the verdicts.
Expect multiple back-and-forth cycles across the pipeline; phase 4 is just
where the loop is most common, not the only place it's allowed. All
verdicts accumulate in the design doc's `## Experiments`. One tree caveat for
every worktree-isolated spike: a worktree sees only **committed** state,
whatever it branches from. The kit's baseline settings.json pins
`worktree.baseRef: "head"` (branch from the session's HEAD) — **confirm the
pin exists in this project's settings** (a pre-existing install won't have it
until `install.sh` re-runs) or the spike silently branches from the default
branch instead. Either way, a spike whose verdict depends on uncommitted work must
get the relevant diff inlined in its prompt, run after a checkpoint commit
(see Checkpoints above), or run non-isolated with the orchestrator aware it
may touch the tree. A verdict tested against the wrong tree is worse
than no verdict — it steers the architecture with false confidence.

**Fixing a defect found after green is one protocol, wherever it surfaces** —
phase 9's review, phase 10's smoke, phase 11's user testing. **Reproduce
first:** an observed failure is this pipeline's red, and a fix without one is a
guess. When the cause isn't obvious — non-deterministic, hard to reproduce,
"works here but not there" — dispatch **`debugger`** before touching code; it
root-causes in its own context (minimal repro, instrumentation,
hypothesis-falsification) and returns the cause plus a proposed fix, so the
bisecting odyssey never floods yours. **When no reliable repro can be made** —
the defect is genuinely probabilistic — don't let that quietly cancel the red:
say so, stand the fix on the closest deterministic evidence instead (the
debugger's falsification trail, plus a regression check at whatever level *is*
deterministic — the unit that mishandles the race, not the race), and record in
the design doc that the repro is probabilistic. Then fix, keep the checks green,
log a `code-change` event, and take the review the surfacing phase prescribes:
phase 9 re-reviews at the same scope, 10 and 11 use the two-speed delta review.

**The contract's *checked by* is a delegation, not orchestrator work** — one
exception: a mechanical grep/compare you can run inline. Rendering a
thing and *looking* at it — a GUI, a layout, a deck, a plot, a diagram — never
qualifies, and is not hand-rolled with throwaway screenshot scripts. **Check the project's
available agents** (per the roster note at the top) and delegate to
whichever fits, with an *encapsulated spec*
(target + reference/palette + which screen/state + what to check) since it can't
see this conversation; it returns artefacts + a critique + a verdict. **If none
fits, don't assume one exists** — capture at least one rendered view yourself and
inspect it, never silently skipping the *look*.

**Concretizing an interface's shape is a floating capability too, not a UI-specific
one.** Whenever a decision settles the *shape* of something a human or another
system will directly perceive or consume — a UI control, a CLI command's output,
an API request/response, a config schema, a file or data format — prose is a poor
medium to confirm it in. "A dropdown plus a token field" reads as complete and
unambiguous prose while quietly assuming exactly one of the thing being
configured — the kind of gap that surfaces only once the control exists and
someone asks "what about two?" Whenever such a decision arises — most often at
phase 3 (the grill) or phase 4 (the plan) —
produce the smallest concrete instantiation that fits the medium before treating
the decision as settled: a rendered mock or ASCII sketch for a UI, an example
request/response for an API, a sample invocation + output for a CLI, an example
file for a config/data format. Confirm the instantiation itself (an
`AskUserQuestion` `preview`, or a throwaway render checked with a specialist agent
per the paragraph above — a hands-tier dispatch; the judgment sits at the
gate that confirms it, not with the renderer) rather than a prose description alone — cheapest done
inline, without a full build/QC cycle. Not every decision needs this — only ones
where the concrete shape is genuinely load-bearing (a stakeholder will directly
see or use it); a return type of "a boolean" needs no mock. Pulling one cheap
instantiation forward catches a wrong shape before any code exists, not after a
costly rebuild.

Hard rule for the whole pipeline: **never modify `.claude/` or the
kit-managed `CLAUDE.md` in this project.** Improvement ideas for those are
collected and presented to the user as suggestions only.

## Model tiering (orchestrator)

The base policy — the `sonnet` → `opus` → `fable` ladder, why hands-tier
doesn't drop quality (plan removes judgment + escalation + brain review), and
the `model`-param mechanism — lives in **CLAUDE.md → Model tiering**. This
section adds only what's specific to this pipeline.

- **The table below is the single tier source.** Phase bodies may repeat a
  tier for emphasis, never contradict it; a dispatch with no row runs at the
  nearest analogue in the table — and say so when you reach for one.
- **Gates and `/commit` run at the session model** (2 Go/no-go, 3
  Requirements, 5 Plan sign-off, 11 User testing — and 12's `/commit`, a
  Skill the orchestrator invokes inline, out of the Agent-tool `model`
  param's reach); the user controls that with `/model`.

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
reviews — phase 9 and phase-11 deltas) run at `fable` =
`brain-top`; the *sort-of-hard* (researcher (1), debugger (11),
kit-retrospective (13)) drop one rung to `opus` = `brain-mid`. Announce the rung
and recommend the drop; the user vetoes for full ceiling. At ceiling `opus`,
top = mid = opus; at `sonnet`, the whole run is hands (escalation still
applies) — and the brain-review net is gone: flag that at the affected
gates rather than pretend the guarantee holds (CLAUDE.md's rule), loudest
where a delta review is a batch's only review.

**Escalation is exempt from the ceiling.** The ladder climbs
sonnet → opus → fable per blocked unit whatever the run's ceiling — the
ceiling prices the plan, not the rescue. One attempt per rung; a unit
still blocked after `fable` (its two failures above hands) is a plan
problem — kick it back to the plan gate.

**Experimenter dispatches are decided per experiment, wherever they fire —
the experiment loop floats across phases 1–4.** Before dispatching, tell
the user what each spike is and **recommend a tier** — hands for a small,
self-contained spike; brain when the verdict will steer the architecture,
and that brain recommendation means **brain-top** (the verdict feeds the
brain-top planner; recommend brain-mid only for evidence-gathering closer
to research than architecture) — then
let them confirm or override.

| Phase | Agent | Tier |
|---|---|---|
| 1 Research | researcher | brain-mid |
| 1–4 Experiments (floating) | experimenter | per-experiment (recommend, then confirm) |
| 4 Architecture | planner | brain-top |
| 6 Validation red | the contract's *checked by* (default test-writer) | hands — a rubric run is a check, not the review |
| 7 Build green | implementer / fitting specialist / general-purpose | hands |
| 8 Docs | librarian | hands |
| 9 Review | the contract's *review* + code-reviewer + maintainability-reviewer | brain-top |
| 10 Smoke + render-and-look | general-purpose / roster visual-QC | hands |
| 11 Delta review | code-reviewer | brain-top |
| 11 Diagnose (unclear cause) | debugger | brain-mid |
| 12 Ship-gate re-runs | librarian, then both reviewers | their own rows (8, 9) |
| 12 Commit | /commit | session model (see bullet above) |
| 13 Retrospective | kit-retrospective | brain-mid |

## 0. Setup (orchestrator)

- Derive a short `<feature-slug>` from the arguments.
- **This pipeline runs in the repo you were invoked from. It does not run
  cross-repo — refuse to.** A session is scoped to one repo: subagents inherit
  that working directory, `/commit` runs there, worktree isolation branches
  there, and every recovery `git diff` reads there. A run that aims its commits
  somewhere else has to hold that invariant across twelve phases and a dozen
  delegations, and it will lose it — an un-briefed librarian bootstraps the
  wrong `docs/` tree, a recovery revert wipes the wrong uncommitted work. So
  when the deliverable belongs elsewhere ("keep it out of this repo", a
  standalone project): **stop here.** Create the directory, `git init -b main`
  it, give it one real commit (README/`.gitignore`) — `git rev-parse HEAD`
  errors on an unborn HEAD and the ledger needs a base — then tell the user to
  start a session there and re-invoke. Setting that up is this phase's whole
  output; don't build from here.
- If `docs/designs/<feature-slug>.md` exists **in the working tree or on
  `feature/<slug>`** — a consented-checkpoint run commits the doc there and
  leaves the tree clean, so from `main` it's invisible; check
  `git show feature/<slug>:docs/designs/<feature-slug>.md` before
  concluding the run is fresh (an error there just means it isn't on that
  branch): make sure you're on
  `feature/<slug>` first (`git checkout`; recreate the branch if it's gone),
  then read the checklist **and the state sections** (`## Experiments`, open
  unknowns, `## User testing`, the close-out ledger including its
  checkpoint-consent header) — the boxes alone don't carry loop counters,
  checkpoint consent, or deferred close-out work. Tell the user where you're
  picking up. A fresh session typically starts on main — resuming without the
  checkout writes feature code to the wrong branch.
- Otherwise (a genuinely fresh run): **if the tree is dirty, stop and confirm
  before branching** — a branch cut over someone else's uncommitted work carries
  it along, and the checkpoint chain then commits it as yours. Then create
  `feature/<slug>` from the current HEAD
  and seed the design doc with this checklist (applying
  `--from`, below, before you start work):

  ```markdown
  # <Feature name>

  ## Phases
  <!-- [ ] todo · [x] done · [-] skipped (--from) -->
  - [ ] 1 Research
  - [ ] 2 Go/no-go
  - [ ] 3 Requirements (grill)
  - [ ] 4 Architecture (incl. experiments + validation contract)
  - [ ] 5 Plan sign-off
  - [ ] 6 Validation red
  - [ ] 7 Build green
  - [ ] 8 Documentation
  - [ ] 9 Review passed
  - [ ] 10 Smoke test
  - [ ] 11 User testing
  - [ ] 12 Committed
  - [ ] 13 Kit retrospective

  ## Close-out ledger
  <!-- Header: `Checkpoints: yes|no · base: <git rev-parse HEAD at phase 0>`.
       Then an append-only event log, one line each, in order:
       - checkpoint: <SHA> — <what>
       - code-change: <which agent / what>  (any dispatch that edits
         code or docs — anything the reviewers must see; the design doc
         itself is exempt, they receive it alongside the diff)
       - close-out: <agents> — scope full|delta — checkpoint <SHA|none>
         — deferred: <what>
         (scope names the pass's charter, never its diff size: phase-8/9
         and ship-gate passes are `full` — a phase-9 re-review included —
         phase-10/11 interim reviews are `delta`. The checkpoint field = the
         ref the pass diffed FROM — for the librarian, the ref it ran on
         — never the batch-close SHA, which lands on its own following
         `checkpoint:` line)
       Phase 12 reads THIS, not your memory of dispatch order. -->
  ```

- **Fresh runs only:** record the run base (`git rev-parse HEAD`) in the
  ledger header, ask the checkpoint-consent question (see Checkpoints in the
  preamble), and record the answer there too; on consent, make the first
  `wip(<slug>): seed design doc` commit now. A resumed run **reads** the
  recorded answer instead of re-asking — ask only if the header is absent,
  and on that resume-ask create the header then, with base := current HEAD.

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
  skippable.** The validate → build → review spine (6+) is mandatory — refuse
  to skip past it; that's where correctness is enforced — skip ideation if you
  must, never skip review. Skipping straight to 4 (planner)
  is the common, supported case. This holds **whatever the deliverable is**:
  a config, schema, workflow, or document with no test suite still runs the
  full spine — "there are no tests here" is never a reason to skip 6–9; the
  phase-4 validation contract defines what red / green / run mean for it.
- **No fake sections.** Don't fabricate a Requirements or Research section for
  a skipped phase. When you skip to the planner (4), pass it the feature
  description directly and instruct it to surface any missing context as
  **Open unknowns**. The phase 5 plan-gate is the safety net — the user catches
  a wrong abstraction there before any red is built.
- If a downstream phase turns out to genuinely need a skipped phase's output,
  say so and offer to run that phase now rather than guessing.

### Stopping early (`--to`)

`--to <phase>` runs the pipeline through the target phase and then **stops**
instead of continuing to commit/retrospective — e.g. `--to 5` for a plan-only
run (architecture + sign-off, no code), or `--to plan`. Combine with `--from`
for a slice (`--from 4 --to 5`). On reaching the target, check its box, tell
the user where you stopped and how to resume (`/build <slug>` picks up
at the next unchecked phase), and stop — do not run later phases. `--to` may
land before the validate/build spine (a plan-only run is fine); it just defers the
spine to a later resume, it never skips it. A stopped run leaves a
consented checkpoint chain live — handle it per Checkpoints above.

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
phases). Require each empirical uncertainty to come back as a **directly
dispatchable one-question brief**: the question, the smallest spike that
yields a verdict, and enough self-contained context to run without this
conversation — phase 3 dispatches the grill-independent ones verbatim into
background spikes, so a brief that needs follow-up questions wastes the slot.
Spike uncertainties **now** when the build/buy/drop call or the
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

**First, use the grill's dead time: dispatch the independent spikes now.**
The interview is usually the longest wall-clock stretch of the run, and every
agent is idle during it. Partition phase 1's empirical uncertainties: those
that are **independent of grill outcomes and self-contained** (their brief
needs nothing the interview could change) get dispatched *before* the first
question — present the spike list with a per-experiment tier recommendation
("while I grill you, these spike in the background — OK?"), then launch one
`experimenter` per uncertainty, background, `isolation: worktree` (mind the
committed-state caveat above). Verdicts land while the interview runs; write
each into `## Experiments` as it arrives. Uncertainties the grill might
reshape stay undispatched — a spike against requirements that are about to
move is the one waste case, and the user confirming the list bounds it.

Invoke `/grill-me`, seeded with the research section and its *decisions for
the human* (the empirical uncertainties are not grill material — they wait
for the experimenter or are already spiking in the background). Distill
the interview into `## Requirements`: scope,
acceptance criteria, edge cases, non-goals. **When the grill settles an
interface's shape**, settle it against a concrete instantiation per the
concretizing rule at the top; an `AskUserQuestion` `preview` is usually
the cheapest inline form.

## 4. Architecture ↔ experimentation loop

- **Plan** (`planner` agent): the delegation prompt must spell out the
  architecture-doc format — this *overrides the planner's default plan
  shape* — and the format follows the deliverable's medium: executable
  gets modules/classes and methods with explicit public vs internal
  marking, data flow, Mermaid diagrams (component + sequence where
  meaningful); other media get the shape that fits them (a section/slide
  outline with sources and assets for a document or deck, schema +
  provenance for data) — a planner fabricating modules for a PDF is the
  same over-heavy failure the contract below exists to prevent. Every
  plan, whatever the medium, ends with the **validation contract**
  (below) and **Open unknowns** —
  claims the plan rests on that need empirical verification.
  Pass the research phase's *empirical uncertainties* **and the verdicts
  already landed in `## Experiments`** (the phase-3 background spikes) into
  this prompt and require a disposition for each: resolved with cited
  evidence, needs a user decision (→ plan gate), or open unknown
  (→ experiment). None may silently disappear. With the grill-time spikes
  in, the first plan often starts with its biggest unknowns already
  answered instead of opening the loop cold.
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

### The validation contract (planner output — phase 5 gates it)

The plan states not only what gets built but how it will be **proven** —
TDD's discipline shed of its literal form: red (phase 6) → build to green
(phase 7) → review (phase 9), whatever the medium. The
contract is authored here, before the gate, because an over-heavy scheme
originates in the plan's mandated shape (a 25-test plan for a 20-page PDF
traced to a format clause demanding a test list; by phase 6, the gate that
could have struck it had already passed). Plain markdown bullets under
`## Deliverables` in the design doc — resist YAML and schemas. Four fields:

- **medium** — what the deliverable is in validation terms (executable,
  rendered pages, a live UI, a registered workflow, content, data), plus
  how it ships: long-lived vs run-to-completion. Phases 10–11 key the
  hand-over on that tag; a change inside an existing app tags the
  vehicle it ships in.
- **red** — the observable failure to see *before* building; concrete,
  never "tests fail". Two kinds, split by one question — *can the check
  run before the thing exists?* **Observable-first** (yes — typically
  executable: literal TDD) and **authored-first** (no — rendered or
  assembled media, content, data: the rubric is authored here, gated at
  5, and its first run against the first draft *is* the red).
- **checked by** — the check and who runs it; a tool plus its operating
  agent counts (`pytest — test-writer authors the red`). Tests are the
  deliverable's red and check, never a deliverable of their own.
- **review** — who reviews the result once green (phase 9 hosts it),
  named now so a check is never mistaken for the review.

**House shapes are the project's, not the run's.** If ProjectCLAUDE.md
has an `## Artifact shapes` section, a deliverable whose medium is
listed there inherits that shape: it constrains the plan and seeds the
red/rubric, so a shape violation fails a check instead of surfacing as
taste at review. No section, or no line for this medium — author freely.

```markdown
## Deliverables
- API rate-limiter — medium: executable (long-lived: ships in the running service)
  - red: pytest — 429 past the limit, pass under it — observed failing first
  - checked by: pytest — test-writer authors the red
  - review: code-reviewer (phase 9)
```

**One deliverable, one contract — but a contract may owe more than one
check.** When parts of the deliverable are validated differently (a PDF
read by an agent, built by a script exercised by tests), name **each** of
those checks here — extra `red` / `checked by` lines in the same contract,
never extra nodes, orderings or loops. They are **additive: a
whole-artifact check never discharges a part's.** In the run that forced
this rule, a rendered PDF's visual review displaced the code review, so
the build script was reviewed by nobody and shipped a bug a rendered page
cannot show by construction. One medium throughout — a couple of Python
modules — means one check and no fuss. (A large build whose independent
parts should run *concurrently* is a different problem, parked in the
experimental `/tree-build` and unvalidated; here siblings build
sequentially.)

## 5. Plan sign-off (orchestrator, gate)

The user reviews the architecture before any red is built. Catching a
wrong abstraction here is 10x cheaper than after red→green. **The validation
contract is a gate artifact in its own right**: present the contract
with its checks verbatim, not summarized — the user resizes or
strikes checks here, while a wrong-sized scheme still costs nothing. **If the plan
introduces or changes a stakeholder-facing interface**, the sign-off
artifact includes its concrete instantiation (per the concretizing rule
at the top), not just the module/data diagram. Apply revisions
(re-entering the loop above if they're structural) until signed off. Record
the sign-off and the revisions applied in the design doc — one or two lines,
decision-grade, never a transcript.

## 6. Validation red (per the phase-4 contract)

The contract — authored at 4, signed at 5 — already says what red means
and which kind this deliverable's is (a check that "runs" pre-existence
but can only fail for the wrong reason — a grep over files that don't
exist yet — counts as authored-first):

- **Observable-first**: dispatch the *checked by* agent now and require
  actual observed output in the report — spot-check it; a red asserted
  rather than observed proves nothing. Tests fail **for the right reason**
  (missing implementation, not typos/import errors); a toolchain-validated
  artifact's pre-change run fails for real (schema rejection, unresolved
  reference, missing output key — the concrete toolchain is
  project-specific; it lives in ProjectCLAUDE.md, not here).
- **Authored-first**: nothing can run yet. Confirm the rubric stands
  frozen in the signed contract; its first run — at phase 7, against the
  first draft — is the red, and its findings are worked off before green.
  Not a deferral, not an exemption: fixed before building, run at the
  earliest possible moment, never saved for the end. The motivating PDF's
  red was the first page review's findings — callout badges sitting on
  the controls they pointed at, which no assertion could catch.

Check the box on the red observed (or the rubric confirmed — say which),
then with checkpoint consent commit `wip(<slug>): validation red` and log
the SHA in the ledger.

*(Applies wherever the contract has an executable check — a rendered
deliverable built by a tested script included; skip only when it has none.)*
When a planned
public symbol doesn't exist yet, instruct the test-writer to add a **minimal
stub** for it (signature / dataclass shape only — a body that raises or
returns nothing, never real logic) marked `# STUB(<feature-slug>):` so the
red is an assertion / `NotImplementedError` failure rather than an
import-/collection-time error. Two guards: the stub must still leave the test
**failing** (a stub that accidentally satisfies a test makes the red fake),
and it stays minimal — the moment a stub grows logic, the test-writer has
started implementing. These markers are the contract the phase-7 sweep clears.

## 7. Build green

Dispatch `implementer` for an executable deliverable, the roster
specialist that fits for other media (per the preamble), and
`general-purpose` when none fits — a missing specialist changes the
builder, never skips the phase. The dispatch gets the design doc plus
which checks it must turn green and runs the check to green itself; you
log the `code-change` ledger event per dispatch (the phase-12 ship gate
reads these — agents never write the design doc, per the preamble). For
an authored-first contract, the rubric's first run happens here against
the first draft — its findings are the red, worked off until the check
passes. In the delegation prompt, tell the implementer to **remove each
`# STUB(<feature-slug>):` marker as it fills that symbol in**, and to
**delete — not leave defined — any planned symbol it diverges from and no
longer uses** (a dataclass/function the doc named but the implementation
routed around). A wrong check comes back to you as a finding — never
weakened silently. Architecture deviations
get written back to the design doc; it must end truthful. With checkpoint
consent, commit `wip(<slug>): <module> green` as each module or draft
lands and log
each SHA in the ledger — those SHAs are what the atomicity
recovery diffs against (delta reviews diff from batch-close lines, per
phases 9/11).

Implementers run at **hands (`sonnet`)** — safe here because the plan and the
observed reds already hold the judgment (CLAUDE.md → Model tiering). **Escalation:**
an implementer that returns blocked — can't get its checks green, flags the
design doc as ambiguous, or hits repeated tool failures — is re-dispatched for
*that unit* one rung up the ladder (ceiling-exempt, one attempt per rung —
see Model tiering). Step up, don't thrash; a unit still blocked after
`fable` is a plan problem — kick it back to the plan gate.

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
modules routinely still touch those shared files. Real parallelism —
independence proofs, worktrees, merge-back — is an unsolved problem here,
sketched in the parked `/tree-build`; don't hand-roll it. Bake the phase-7
escalation rule into the loop.
**Recommend the workflow only when modules are
many; skip it for one or two — and never run it without the user's OK** (a
workflow can spawn many agents). Un-annotated `agent()` calls inherit the
*session* model, so set `model: 'sonnet'` on every implementer explicitly or the
hands saving evaporates. Tests-still-green and the STUB sweep below apply
identically.

**Before checking this box, if the phase-6 STUB mechanism was used, sweep
for leftover scaffolding:**
`grep -rn 'STUB(<feature-slug>)' <source dirs, excluding docs/>`. Any hit
means a stub was implemented but not cleaned, or a planned symbol was
abandoned in place — resolve it (finish or delete) now. The reviewers
receive the diff in phase 9 and treat a dangling stub on shipped code as a
finding, so an unswept marker just becomes a review blocker. Use the exact
slug token from phase 6 — one-character drift makes the grep silently match
nothing, and a no-op gate reads as "covered" when it isn't. (In a run that
introduced no stubs, don't run a grep that can only ever match nothing and
mistake it for a passed gate — confirm the green from the contract's
checks instead.)

## 8. Documentation

Not optional, and not foldable into review. Split by *information source* —
code-derived docs go to the specialist; conversation-derived state stays with
you, because only you hold the context to write it:

1. **Code-derived docs (`librarian` agent).** Delegate: bring the `docs/`
   codebase map current (it invokes `/sync-docs`) and update the
   feature-level docs this project keeps to match existing conventions. The
   librarian reads the code directly, so it needs none of this conversation —
   but it also can't write what isn't in the code. Write its returned report
   into the design doc, act on its flags, and log the ledger pair for
   this pass: a `code-change` for the librarian's edits (doc changes are
   part of the diff the reviewers must still see) and its event — `close-out: librarian —
   scope full — checkpoint <SHA it ran on|none> — deferred: none`. Scope
   `full` is load-bearing: the librarian saw the whole tree, and the
   phase-12 gate discriminates on exactly that word.
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

## 9. Review loop (contract review + `code-reviewer` + `maintainability-reviewer`)

Two halves, both mandatory **whatever the medium**:

- **The contract's review**, run by its *review* agent,
  medium-appropriately: for an executable deliverable it coincides with
  the code review below; for rendered/assembled media it's the read of
  the whole — batched across agents for a multi-page artifact (~7 pages
  each; a single agent handed 20+ full-page images stalls without
  returning).
- **Both code reviewers on the accumulated diff, in parallel — always**,
  even when the deliverable renders: the code that produced it ships too.
  The diff's base: the ledger's run base on the first pass, the
  last reviewed checkpoint on re-reviews. Launch both as fresh subagents
  with only the diff and the design
  doc — no implementation context. That isolation is the point: they check
  the work, not the intentions.
- **Show the user each review summary** (verbatim findings, not your gloss).
- Fix blockers and should-fixes per the fix protocol above, then
  re-review. **Max 2 fix rounds**; if the third review still
  has blockers, stop and hand the open findings to the user (live
  checkpoint chain handled per Checkpoints above).
  Annotate the round on the checklist box (`- [ ] 9 Review passed (fix
  round 1/2)`) — the annotation, not the box state, carries the count (on a
  phase-11 re-entry the box is already `[x]`); it lives in the design doc,
  not your memory, and **resets per batch**.
- **A fix that changes the basis of a prior measurement** (a re-crop, a
  re-render, a renumbering) invalidates verification of everything derived
  from that basis, not just the items edited — so the re-review covers the
  same scope as the review that found the defect; a spot-check is not a
  re-review. (A fix round that re-cropped 6 images was reported complete
  after 3 pages were checked; re-verification found 7 misplaced badges.)
- After each completed pass, append a close-out ledger event (field
  semantics per the phase-0 seed comment: **scope `full` or `delta`**, the
  event's checkpoint = the diffed-from ref) — then, with checkpoint
  consent, commit the batch-close checkpoint and log its SHA on its own
  following `checkpoint:` line; later delta reviews diff from that line.
  <!-- Three callers use these close-out mechanics: this full pass, the
       scoped deltas of phases 10–11, and phase 12's ship-gate runs — keep
       their scopes distinct; phase 12 discriminates on that field. -->
- Prompt/instruction improvement ideas from reviewers (e.g. "this LLM
  artifact keeps appearing — instruction X would prevent it") are collected
  under `## Kit suggestions` in your report to the user. Suggestions only —
  see the hard rule above.

## 10. Smoke test

Exercise the deliverable end to end — the contract's medium tag already says
what exercising means (start the app and poke it, a full toolchain run on
representative input, render and read). Breadth is what makes this a smoke
rather than a repeat of the run that turned phase 7 green: broader input,
more cases, the adjacent path. A long-lived app's *process* runs from the orchestrator
(background Bash) so it survives into phase 11; the poking itself is a
general-purpose agent's job, not yours. Anything rendered gets *looked at*, not just exercised — a
"checks pass" run is blind to layout, alignment, and styling defects;
delegate the render-and-look per the preamble's *checked by* delegation
rule — never silently skipping the look. Land the condensed result in the
design doc — what was exercised, what was observed, a few lines, never logs.
Keep the run's actual outputs on disk and say where: phase 11 hands them to
the user to inspect, and a discarded run has nothing to hand over.

## 11. User testing (orchestrator, gate)

First, audit your own checklist: re-read every `[x]` and name, one line
each, the observed evidence behind it — a phase ticked on inference rather
than execution goes back to `[ ]` (a run has ticked the smoke test PASSED
before the ship path was ever executed) — and you **execute it now, before
the hand-over**: an unticked box is work owed, not an annotation. Then hand
the deliverable to the user and wait. For a long-lived app that's the running instance; for a
run-to-completion artifact (per the contract's medium tag) it's
the run command + representative input so the user can exercise it themselves,
plus the last run's outputs to inspect — there's no persistent instance to hand
over. Every issue the user finds gets fixed **immediately** (per the fix
protocol at the top) so testing isn't blocked on documentation/review. The close-out is **two-speed,
deliberately** — every fix still gets reviewed, but only the ship gate pays
for the full pass:

- **Interim hand-backs get a scoped delta review**: one `code-reviewer` at
  **brain-top** (this is most interim batches' only review — never a tier to
  economize on), on the diff since the last reviewed checkpoint (dirty-diff
  mechanics if checkpoints were declined), its prompt carrying the prior
  round's findings
  to check the fixes against, and told explicitly that **doc staleness is
  known-deferred and not a finding this round** — without that line it
  re-reports the same stale-docs blocker every batch, by charter. No
  `librarian`, no `maintainability-reviewer` yet.
- **The full close-out — `librarian` + both reviewers — runs once, before
  phase 12** (the ship gate there enforces it). Deferral has a limit: force
  the full close-out — all three agents, librarian included — early when the
  accumulated delta stops being local: it adds a public symbol, touches more
  than one module, or spans three or more hand-backs.

Track the loop's state in the design doc, not your head: keep a short
`## User testing` list (issues found / fixed / last batch closed), log a
`code-change` ledger event per fix dispatch and a `close-out` event (scope
`delta`) per delta review, and — with checkpoint consent — commit the
batch-close checkpoint each time, logging its SHA on its own `checkpoint:`
line (the next delta diffs from it). What must never happen is
reaching phase 12 with code no reviewer ever saw, or with the full pass
older than the last code change.

The user decides through their own testing when the loop is
done; don't nudge. Once they're satisfied, phase 12's precondition is what
actually guarantees docs and review are current against the final code —
not a promise made here.

## 12. Commit (orchestrator)

**Precondition — the ship gate:** before committing, each of `librarian`,
`code-reviewer`, and `maintainability-reviewer` must **individually** have
seen the tree exactly as it now stands — conjunctive, per agent, never "some
reviewer ran recently". For a non-executable deliverable the contract's
*review* agent is a fourth member: its last whole-artifact read must
postdate the last change to the artifact — a re-render after the read
reopens it. Read the **close-out ledger**, not your memory of
dispatch order: for each of the three, its last **`full`-scope** close-out
event must postdate the last `code-change` event. A `delta` entry never
satisfies this gate — it saw a slice, was told to ignore doc staleness, and
ran before the final librarian pass. Run whatever is missing now, in this
order: **`librarian` first, then both reviewers on the post-librarian tree**,
each at its own phase tier (the ship gate is never the place to economize),
each on the accumulated diff since its last full pass — and close each run
out like phase 9 does: append its `close-out` event (scope `full`) and,
with checkpoint consent, commit the pre-12 checkpoint the preamble
promises, logging its SHA. A gate-filling librarian that edits docs logs
its `code-change` like any other dispatch — the reviewer runs that follow
it, on the post-librarian tree, are what close that edit. The phase-11 delta
reviews deliberately deferred these passes; this is where the deferral is
collected — and a `code-change` logged *after* an agent's last full pass
(a phase-9 fix round, a late doc edit) legitimately re-opens that agent's
gate: that is the gate working, not a ledger error. **If the ledger is missing or the ordering can't be established
from it (compaction, resumed session): don't guess — re-run all three on the
current tree** — recorded and checkpointed like the runs above, recreating
the ledger section first (fresh header, base := current HEAD) if it's
gone. One redundant close-out pass is the known cost of a crash; a
silently skipped ship gate is not. This is the one hard gate that catches a
phase-11 loop that batched fixes without ever looping back — skipping it is
how stale docs or an unreviewed change ships.

On user approval, close out the git state, then commit. With a consented
checkpoint chain the chain holds the bulk of the work, but either path may
still carry late uncommitted edits (docs, the design doc) —
reconciliation is yours, not `/commit`'s: ask squash-or-keep. On
**squash**, `git reset --soft <run base>` (the ledger header records the
base), which turns the whole committed feature into staged changes sitting
alongside those edits, then invoke
`/commit` as normal. On **keep**, the wip chain stands and `/commit` handles
the remaining uncommitted work. Without checkpoints,
invoke `/commit` on the dirty tree as before: implementation, tests, docs,
and the design doc. Merging/PR is the user's call — say so and stop.

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
instruction locations (`.claude/skills/build/SKILL.md`,
`.claude/agents/*.md`). The agent digests transcripts in its own context and
returns only a short list of suggestions, so the run's bulk never enters
yours. Hand over paths, never verdicts about them: the agent resolves its own
evidence — re-running that `find` and listing the subagents dir itself rather
than trusting a handed-over path — and never assert on its behalf that
evidence is absent; an agent that cannot find the record says so instead of
proceeding.

**Present the returned suggestions to the user verbatim** under
`## Kit suggestions` in the design doc (folding in any the phase-9 reviewers
already left there). Suggestions only — the hard rule at the top applies
even here. The user decides what to apply.
