---
name: build
description: Full delivery pipeline for any deliverable — research → go/no-go → grill → plan/experiment loop → validation-first build (TDD for code, the same discipline for every other medium) → docs → independent review → smoke test → user testing → commit → kit retrospective. The main session orchestrates; every work phase runs in a dedicated subagent. For a contained change that needs no signed-off plan, independent review or durable record, use `/implement` instead. A composite deliverable — parts validated differently — is handled here, by naming each part's check additively in one contract.
argument-hint: "<deliverable description, or existing slug to resume> [--from <phase or name>] [--to <phase or name>] [--brain <fable|opus|sonnet>] [--repo <absolute path of an outside repo>]..."
disable-model-invocation: true
---

Build the following deliverable end to end: $ARGUMENTS

You are the **orchestrator**. Delegate every work phase to its named agent;
run only the interactive gates yourself (subagents can't talk to the user).
**Know your roster before you start: skim the Agent-tool's available-agents list
(`.claude/agents/` is the backing registry) so you know which specialists *this
project* ships beyond the named phase agents — visual/GUI, plots, decks, other
domains. When a phase's work matches one, delegate instead of hand-rolling; the
roster is discovered each run, so a new agent needs no change here.**

**Delegation is the default for all work — and the rule that gets forgotten
covers the work that isn't a phase.** Phases route themselves; what silently
accretes inline is everything *between* them: chasing a defect, iterating a
rendered artefact, reading a transcript, probing an API, comparing candidates.
**Before any stretch longer than a few tool calls, ask: could this have been a
brief?** Three tests, any one means delegate:

- **Length** — more than a handful of calls, or any render→look→tweak loop. Each
  iteration burns main-thread context the rest of the run needs.
- **Parallelism** — stretches that don't share files run *concurrently* in the
  background while you keep working. **Long work is the strongest case for
  delegating, not the weakest**: 10 minutes done inline is 10 minutes of stalled
  pipeline; three dispatched together cost the slowest one. Dispatch, then
  continue — never idle waiting on a background agent.
- **Context economy** — anything whose *bulk* you don't need (logs, transcripts,
  renders, large diffs). Keep the conclusion, not the dump.

Inline is for gates, decisions needing this conversation's history, and edits too
delicate to brief. **When you keep something inline that passes a test, say why
in one line** — writing it is what stops the reflex. A ledger showing the
orchestrator authoring most of the work has drifted, whatever the reason.

**Your own output is the only thing here nobody reviews — so verify it.** The
reviewers are told a finding they haven't checked is a guess; the same holds for
you. Every claim about code in a dispatch brief or a doc you write is either
quoted from an agent's report, or read from the file *this turn*, or labelled
`unverified — confirm first`. **Never phrase a claim as prior intent** ("was
supposed to", "the plan said", "this used to") — hands tier can't tell your
verified claim from your guess and will implement to either. Two brief-writing
rules from the same root: **phrase a change as what must stop being true, not as
a line to delete** (a literal "delete this comment" removed a load-bearing
signature header), and **when a defect is a pattern, ask for a sweep, never hand
over a list** (an enumerated list guarantees the items you missed survive).

The design doc `docs/designs/<feature-slug>.md` is the shared spec: agents
read it — never assume an agent saw this conversation. **Point at sections
with line ranges, never say "read in FULL," once the doc has grown past a
skim — and never both inline the spec in the dispatch prompt and also
demand a full read; that pays for the same information twice.** The doc
only grows across a run (one build measured 6 full reads paying for an 85k-
char file each time, most of it already restated in the prompt itself) —
a dispatch late in a long run costs more than one early, for no benefit if
the agent only needs one section. Name the section(s) that actually matter
(`## Architecture`, `## Deliverables`) with an offset/limit `Read`, and
trust the prompt's own inlined spec for everything else. **Agents return
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
Before building on its work, inspect `git diff` (in every repo it touched) and restore a coherent tree —
revert to the last-good state or finish the edit yourself. **A green test suite is
not proof of tree coherence:** a half-applied refactor can pass the whole suite.
This applies to every delegated phase, not one.

**A stall (silence, not a returned `failed`) is a retry at the same tier, never
an escalation** — escalation is for *blocked*, a stall is for *stopped talking*.
This applies to any dispatch, not only phase 12's gate agents (a phase-7
implementer stalling mid-verification is the same case, not a different one).
On a stall: inspect the tree first, same as any other terminate-early (the
atomicity paragraph above), before deciding anything. Then either re-dispatch
the unfinished slice — narrowing the read set first, since an open-ended
dispatch that stalled once often completes at the same tier when given named
files and permission to answer "no change" — or, when the remaining work is
*verifying already-written code* (never writing new code), the orchestrator
may finish it directly at its own tier. Either way, log a `code-change` event
naming who actually finished the work — an orchestrator that completes a
stalled implementer's verification is a code-change event like any dispatch,
not a free pass.

**Checkpoint commits give that recovery a ref to stand on.** At phase 0, ask
once: *"this run makes `wip(<slug>)` checkpoint commits on the feature branch,
reconciled at phase 12 — OK?"* On consent, commit `wip(<slug>): <what>` after
seeding the design doc, after phase 6 (validation red), after each phase-7
milestone lands (a module green, a draft assembled), and after each batch close-out (phases 9/11 and the pre-12 full
close-out) — logging each SHA as an event in the close-out ledger. Stage
**file-level pathspecs only** — never `git add -A`, and never a directory or glob
either: `git add docs/solutions/` is not "explicit", it *expands*, and it is how
thirty files from someone else's work stream ride into a checkpoint. **Print
`git diff --cached --stat` and read the file list before every checkpoint
commit** — that one habit is what actually catches this, since the rule alone
does not. The atomicity recovery above then becomes
concrete: `git diff <last-checkpoint>`, restore from it. **Never write a SHA
into the ledger via `--amend`** — that orphans the very commit the line names;
use a follow-up commit. Reconciliation is the **orchestrator's** job at phase
12, not `/commit`'s; squash-or-keep is the user's call there, and a squash means
rewriting the ledger's SHAs into milestone descriptions so nothing points at a
commit that no longer exists. A run that ends before phase 12 leaves the chain
live — say so and offer to reconcile. After any early reconcile, set the ledger
header's `base` to the new HEAD: a later squash must never rewind past an
already-reconciled commit. If the user declines checkpoints, the delta-review
and recovery steps fall back to dirty-diff mechanics (weaker — say so when it
bites). **With outside repos** (`--repo`, or a proposal the user accepted; see
phases.md §0 *Building in an outside repo*), all of this runs per repo as
`git -C "<path>"`, against each repo's own base, and the home is only branched
when the deliverable changes it.

**Experimentation is a floating capability, not a fixed phase.** Whenever
any phase surfaces a falsifiable uncertainty — research claims an unproven
library fit, the go/no-go hinges on an unverified capability, the plan
rests on an assumption — dispatch `experimenter` agents *then and there*
and loop back to the phase that raised the question with the verdicts.
Expect multiple back-and-forth cycles across the pipeline; phase 4 is just
where the loop is most common, not the only place it's allowed. All
verdicts accumulate in the design doc's `## Experiments`. One tree caveat for
every worktree-isolated spike: a worktree sees only **committed** state.
And `isolation: worktree` only worktrees the home: a spike on an outside repo's
code is isolated by a worktree you add in that repo (phases.md §0 *Isolation*).
The kit's baseline settings.json pins `worktree.baseRef: "head"` — **confirm
that pin exists in this project** (a pre-existing install lacks it until
`install.sh` re-runs) or the spike silently branches from the default branch.
Either way, a spike whose verdict depends on uncommitted work needs the diff
inlined in its prompt, a checkpoint commit first, or a non-isolated run. A
verdict tested against the wrong tree is worse than no verdict.

**Fixing a defect found after green is one protocol, wherever it surfaces** —
phase 9's review, phase 10's smoke, phase 11's user testing. **Reproduce
first:** an observed failure is this pipeline's red, and a fix without one is a
guess. When the cause isn't obvious — non-deterministic, "works here but not
there" — dispatch **`debugger`** before touching code, so the bisecting odyssey
runs in its context and not yours. **When no reliable repro can be made**, don't
let that quietly cancel the red: say so, stand the fix on the closest
deterministic evidence (the debugger's falsification trail plus a regression
check at whatever level *is* deterministic — the unit that mishandles the race,
not the race), and record in the design doc that the repro is probabilistic.
Then fix, keep the checks green, log a `code-change`, and take the review the
surfacing phase prescribes: 9 re-reviews at the same scope, 10 and 11 use the
two-speed delta.

**The guard test for a post-green fix is written by an agent told the symptom and
not the fix** — a `test-writer` given the observed failure and the file, with no
account of your diagnosis. A guard written by the fix's author tests the *fix's
own model of the bug*: it passes by construction and proves nothing. That is why
phases 6 and 7 are separate people, and a post-green fix needs the split *more*
than phase 7 does — it has no signed-off plan behind it and no red already
observed. Small edits (docs, ledger, a line inside a symbol a reviewer has read)
stay inline, but **anything changing how a symbol is called or wired is a hands
dispatch** — the reviewers saw the old call graph. Your own rule at the top
applies: your output is the only thing here nobody reviews.

**A defect reported as "pre-existing" is a claim you must not accept on shown
work alone** — the burden is the *ref*, not the diligence. It is established only
by an A/B against the ledger's `base:`; a checkpoint or current HEAD already
contains the feature, and a "baseline" carrying this feature's own tests is not
one. Pass that SHA in the dispatch prompt so the agent has it. For an
intermittent failure, require the rep count on both refs, and treat overlapping
rates as **undetermined** — which escalates, rather than closing. Two traps that
make a false negative cheap here: a *second* nondeterminism can decide what each
arm even runs (tests that skip on a racing precondition), masking the defect in
the base arm; and a drifting failure rate makes any remembered number an invalid
denominator, so a control has to be measured in the same session. Getting this
wrong costs a whole phase — the diagnosis lands later, in its own dispatch,
instead of inside the fix round.

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
medium to confirm it in: it hides wrong cardinalities, defaults and orderings
behind sentences that read as complete. Whenever such a decision arises — most
often at phase 3 (the grill) or phase 4 (the plan) —
produce the smallest concrete instantiation that fits the medium before treating
the decision as settled: a rendered mock or ASCII sketch for a UI, an example
request/response for an API, a sample invocation + output for a CLI, an example
file for a config/data format. **Instantiate the declared failure and
partial-knowledge states too, not just the nominal one** — one sample per exit
code including "cannot determine", the error envelope, the rejection message.
A gate that previewed only the happy path is how a documented invariant
("exit 0 must never claim knowledge it lacks") gets signed off in prose and
violated in code. Confirm the instantiation itself — an `AskUserQuestion`
`preview`, or a throwaway render checked with a specialist agent (hands tier;
the judgment sits at the gate that confirms it, not with the renderer) — rather
than a prose description, cheapest done inline without a build/QC cycle. Only
where the shape is genuinely load-bearing: a return type of "a boolean" needs no
mock. One cheap instantiation forward catches a wrong shape before any code
exists.

Hard rule for the whole pipeline: **never modify `.claude/` or the
kit-managed `CLAUDE.md` in this project or in any outside repo of the run.** Improvement ideas for those are
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

## Phases

**The bodies live in [`phases.md`](phases.md), beside this file. Read a phase's section there
before starting that phase** — the lines below name phases, they do not specify them. A phase
run off this index alone will miss its gate, its dispatch contract, or its close-out.

Phase 0 seeds the design-doc checklist, which is also the resume mechanism: **begin work at the
first `[ ]` phase**, treating `[x]` (done) and `[-]` (skipped via `--from`) identically.

| # | Phase | Who | Note |
|---|---|---|---|
| 0 | Setup | orchestrator | slug, branch, seed the checklist + close-out ledger, checkpoint consent. Also `--from` / `--to`, and outside repos (`--repo`). |
| 1 | Research | `researcher` | build/buy/drop + pitfalls; reads `docs/solutions/INDEX.md` first |
| 2 | Go/no-go | orchestrator | **gate** |
| 3 | Requirements | orchestrator | **gate** — interactive grill |
| 4 | Architecture ↔ experimentation | `planner` (+ `experimenter`) | produces the plan **and the validation contract** |
| 5 | Plan sign-off | orchestrator | **gate** |
| 6 | Validation red | the contract's *checked by* | see the failure before building it |
| 7 | Build green | `implementer` / specialist | |
| 8 | Documentation | `librarian` + orchestrator | code-derived vs conversation-derived split; docs lint |
| 9 | Review loop | contract review + `code-reviewer` + `maintainability-reviewer` | max 2 fix rounds; launches 10 alongside |
| 10 | Smoke test | general-purpose / visual-QC | starts with 9, closes after it |
| 11 | User testing | orchestrator | **gate** |
| 12 | Commit | orchestrator + `/commit` | reconcile the checkpoint chain first (squash-or-keep is the user's call) |
| 13 | Kit retrospective | `kit-retrospective` | suggestions only — never edits `.claude/` |

The validate → build → review spine (6–9) is **mandatory whatever the deliverable is**; only
the front phases (1–3) are freely skippable. "There are no tests here" is not a reason to skip
6–9 — the phase-4 contract defines what red, green and run mean for that medium.
