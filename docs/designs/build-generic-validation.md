# `/build` — generic, recursive validation

Handoff doc, written 2026-07-31 because the originating session ran out of context.
Scope: **the validation-contract / recursive-subloop feature only.** Peripheral work from
the same branch (skill rename sweep, `/implement` boundary) is done and not discussed here.

**Nothing is committed.** Branch `feature/build-generic-validation` (from `main` @ `40f34e8`),
10 files modified in the working tree. Main artifact:
`.claude/skills/build/SKILL.md`, 690 → 738 lines.

## What was asked for

> "Help me make it more generic so it can on the fly decide the specifics of the kind of
> validation it would do. The general loop stays that we want to have a scheme for validating
> before building and execute the validation after building (and so go in a loop like this).
> Yet, I want the specifics to be interpretted for particular context. If I ask for PDF it's
> different than when I ask for building a new evaluator feature then when I ask for a slide
> deck. At the same time, large features may even have a composite structure. With subloops.
> In this case, I asked for a PDF deliverable which in turn required a code deliverable. The
> code delivarable could benefit from having internal classical tests but the whole structure
> is eventually wrapped in an LLM visual inspection."

Plus: **"It's ok to say TDD but then make it clear that the literal meaning is applicable to
code but the principle can generalise."**

## What was built

**The validation contract, authored at phase 4, gated at phase 5.** Replaces phase 6's old
hardcoded two-"shape" enum (executable code / declarative artifact). Placement is
load-bearing: a retrospective traced an over-heavy 25-test plan for a 20-page PDF to
**phase 4's** mandated plan shape (the clause `a named test list (unit + integration)`), so a
fix at phase 6 would leave the generator intact. Phase 5 presents the tree as a gate artifact
in its own right — that gate, not an adjective, is what keeps schemes proportionate.

**Representation** — nested markdown bullets, three fields per node: **medium** (executable,
rendered pages, a live UI, a registered workflow, content, data), **red** (the observable
failure to see before building), **checked by**.

**The recursion:**

```
loop(node):
  red    — observe this node's stated failure, for real
  build  — a leaf: implement it.
           a parent: run loop(child) for each child, then assemble from them.
  green  — run this node's own check until it passes
  review — this node's medium-appropriate review
```

*"Phases 6/7/9 are the **root** invocation; the contract tree marks the nested ones, each
closing — green *and* reviewed — before its parent assembles."*

**Termination rule:** split a node only when a sub-part's validation medium differs from its
parent's. **Additive rule:** a parent's check never discharges a child's (grounded in the real
failure — an LLM page review displaced a code review, so a build script shipped a bug that a
rendered page cannot show by construction).

**Two kinds of red**, and this was a mid-course correction worth keeping: **observable-first**
(leaves, typically executable — literal TDD) and **authored-first** (composite parents,
rendered/assembled media: the rubric is fixed at 4/5 and run against the *first assembly*,
and that run's findings *are* the red — "not a deferral, not an exemption"). The second kind
is what lets TDD's discipline generalise to a thing that cannot fail before it exists.

## Validation — 4 read-only Fable agents, each given only `SKILL.md`

Three derived a contract for a different deliverable; one attacked the file. All four ran on
verified `claude-fable-5` (checked in the subagent `.jsonl`, not the `meta.json` param).

**What passed.** Plain code: no regression — one-node tree, literal TDD intact, *"the contract
costs ~nothing and buys the phase-5 strike-a-check gate. No paperwork smell."* Slide deck:
produced a deck-shaped scheme, *"I never felt pressure to pytest the deck."* Composite: the
nesting is followable — *"the loop block plus 'closing — green and reviewed — before its
parent assembles' fully determines it; I did not invent that."*

**What failed** — ranked by how many of the four found it.

### R1 — the child red step has no home. (4/4. Fix first.)

The loop says nested reds open *inside phase 7*. Phase 6 was then scoped to the root only:
*"this phase runs the **root** loop's red step (nested reds open inside phase 7, when their
loops do)."* But:

- **Phase 6's body still assumes it runs every red** — *"Dispatch **each** red to its node's
  *checked by* agent"*, the tier row *`6 Validation red | per node's checked by (default
  test-writer)`* (`test-writer` is a *leaf's* agent), the checkpoint *"once **this phase's
  reds** are observed"*, and the whole STUB paragraph addressed to a phase-6 test-writer.
- **Phase 7 never instructs running a child's red at all** — it goes straight to *"Dispatch
  `implementer` for executable nodes"*. This is the critic's find and the worst of it: *"An
  agent following 7 literally builds every child without ever observing its red."*

So for a composite root, phase 6 has nothing to execute (yet must tick a box and commit
`wip(<slug>): validation red`), and the reds it disowned are never picked up. Two defensible
readings of when box 6 is checked.

**Proposed fix:** define red-opening once, in the loop description; have **phase 7 explicitly
run red → build → green → review per child**; make phase 6 *"open every red that can run
before its artifact exists"* (for a composite root: confirm the rubric is frozen, nothing
more) and say what the box and checkpoint mean when that set is empty.

### R2 — the loop's fourth step isn't in the contract. (2/4.)

`loop(node)` has red / build / green / **review**, but a node carries only medium / red /
checked-by. So nested reviews are never authored, never gated at phase 5, and never tiered —
the example smuggles one into checked-by (*"checked by: test-writer, then code-reviewer"*) and
the tiering table's only review row covers phase 9, i.e. the root. Who reviews a child inside
phase 7, at what tier, under phase 9's "no implementation context" isolation rule, is
guesswork. An orchestrator either invents a reviewer or skips the step — and skipping it
collapses straight back into the displaced-review failure the additive rule exists to prevent.
**Proposed fix:** a fourth per-node field (`review: <agent>`) plus one tiering line for nested
reviews.

### R3 — phase 9's identity conflict. (1/4, material.)

Header and body hardcode the pre-contract pair — *"## 9. Review loop (`code-reviewer` +
`maintainability-reviewer`, parallel)"*, *"only the diff and the design doc"* — while four
lines later claiming *"**This is the root node's review, not the only review**"*. If the root's
medium is rendered pages, its medium-appropriate review is a page read by its *checked by*, not
two code reviewers on a diff. The stray *"batch a multi-page artifact review (~7 pages each)"*
line betrays the seam: it describes a review the phase's declared agents cannot perform on a
diff. Divergent outcomes: either children's code is reviewed twice at brain-top, or for a
rendered root the code diff is never reviewed at 9 at all. **Proposed fix:** one sentence —
phase 9 = the root node's contract review **plus** both code reviewers on the accumulated diff
regardless of root medium.

### R4 — the two-kinds dichotomy fails on non-executable leaves. (2/4.)

It's typed on two axes that disagree: *observable-first (leaves, typically executable)* vs
*authored-first (composite parents, rendered/assembled media)*. Slide copy (content leaf) and a
data extract (data leaf) are **leaves whose checks cannot run pre-existence** — neither
category fits. *"A data leaf falls between the definitions."* **Proposed fix:** re-type on the
single axis that matters — *can this check run before the artifact exists?* — and drop the
leaf/parent framing, which is only a correlation.

### R5 — "validation medium" granularity is undefined. (2/4.)

The termination rule stands entirely on this term, and the medium list gives no way to decide
whether a chart PNG differs from a deck slide. One agent split anyway and caught itself:
*"that is splitting by check, not by medium, which is exactly what the rule forbids me to
freelance."* Another: *"two-to-three defensible trees from one rule."* **Proposed fix:** define
it (a different medium = a different kind of check *and* checker), or bless the ambiguity
explicitly and name phase 5 as where it resolves.

### Smaller, one agent each

- **R6 — sibling order unstated.** "Bottom-up" fixes depth, not order among siblings.
- **R7 — a parent's own assembly is three words** (*"then assemble from them"*): who performs
  it once children are green is unstated.
- **R8 — phases 10/11 consume a distinction the contract no longer produces.** Both attribute
  "long-lived app vs run-to-completion artifact" to *"the contract's top node"*, but no field
  encodes it — medium `executable` covers a daemon and a one-shot CLI alike. The deleted shape
  enum's ghost: the consumers survived, the producer didn't.
- **R9 — phase 4's plan format is still code-shaped**, unconditionally: *"modules/classes and
  methods with explicit public vs internal marking, data flow, Mermaid diagrams"*. For a PDF or
  a deck the planner must fabricate modules — which is the very failure mode the contract
  section's own anecdote condemns. Condition the format on node medium.

### Bloat, if length needs funding (3/4 mention some)

The checkpoint/ledger machinery is threaded through the preamble, phase 0's ledger block, phase
9's ordering aside and phase 12's gate, each partly restating the others — *"makes the loop
model harder to see on first read than it deserves to be."* Roster discovery is stated three
times (preamble, the checked-by paragraph, phase 10 — the last nearly verbatim). The
concretizing paragraph (~23 lines) states its cardinality trap three times and is
re-instructed at phases 3 and 5. Roughly 40–60 lines are recoverable without losing a rule.

## Recommended order for the next session

1. **R1** — it sits in the exact case the feature was built for, and it is a genuine break
   (child reds unrunnable), not just ambiguity.
2. **R2 + R3** together — both are "who reviews what, at which level", and fixing them apart
   will re-open the seam.
3. **R4 + R5** — the two definitional gaps; cheap wording, high leverage on tree quality.
4. R6–R9 as wording passes. Fund any length growth from the bloat list.

Re-run the same four-agent test after fixing: three contract derivations (code / deck /
composite) plus one adversarial read, each given only `SKILL.md`. That harness found every
defect above and cost four Fable dispatches.

## Round 2 — fixes applied and re-validated (2026-07-31, follow-up session)

R1–R9 all applied to `SKILL.md` (738 → ~800 lines; preamble bloat cuts funded ~15 of
the growth). The same four-agent harness re-ran on the fixed file: three Fable
derivations (FastAPI middleware / QBR deck / the composite Dutch PDF) + one Fable
adversarial read, each restricted to `SKILL.md`.

**Core verdicts — the R-fixes held.** Composite: *"no path was found by which a node
closes with nobody reviewing it"*; child reds open correctly (pytest at 6,
authored-first inside 7); build script reviewed at 7 (module) *and* 9 (assembled
seams), rationale cited. Plain code: tree collapses to one node; *"the contract adds
one classification decision and a few lines."* Deck: deck-shaped scheme, root read at
9 + code reviewers on the diff; only honest residue (the worked example's gravity
toward including an executable child). R1–R5 held under maximally literal reads;
R6–R9 consumed as intended.

**Round-2 findings, fixed in the same pass:**

- Root review 7-vs-9 double-run ambiguity (3/4) → explicit root exception in phase
  7's assembly step + single-node degenerate-case note.
- long-lived/run-to-completion tag scoped to executable tops but consumed for every
  top (4/4, incl. the example violating its own spec) → tag required on every top
  node whatever its medium; changes inside an existing app tag the ship vehicle.
- No builder/assembly fallback for non-executable nodes (3/4) → `general-purpose` at
  hands; "a missing specialist changes the builder, never removes a loop step."
- Review-step fallback missing ("reviewer agent" maps to no registry identity — the
  one residual displacement path found) → `general-purpose` at brain-top with the
  node's rubric.
- Mixed-tree phase-6 box literally omits rubric confirmations (2/4) → box = all reds
  observed AND all confirmations recorded.
- The one-question test misclassifies pre-existence greps (fails, but for the wrong
  reason) → "and fail for the right reason" wired into the question.
- checked-by tool-vs-agent + green-step owner (2/4) → field def names tool + operating
  agent; green bullet names who re-runs (builder for executables, else checked-by).
- Nested-review findings had no protocol (1/4) → blockers worked off before "closed";
  node checkpoint moved from green to close (green *and* reviewed), preamble aligned.
- Phase-9 first-pass diff base undefined (1/4) → run base first pass, last reviewed
  checkpoint on re-reviews.
- Preamble's absolute "checked by is a delegation" vs the example's orchestrator grep
  (2/4; was parked) → inline-mechanical exception scoped, render-and-look excluded.

Not fixed by design: "does the tree contain a script node at all" is a plan judgment
the phase-5 gate owns (the tie-breaker sentence covers it); unit-vs-integration
split pressure resolved by the same tie-breaker.

**Agreed next steps (user-approved direction, deferred until after this lands):**
per-project artifact shapes via a `## Artifact shapes` section in `ProjectCLAUDE.md`
(one line per medium, optional pointer to a style/template doc; skill carries only
the lookup rule at phase 4); live tree display via harness tasks (one task per
contract node at phase 5, DFS order, indented subjects, `blockedBy` = child-before-
parent; statuses flipped at loop transitions), Workflow-orchestrated phase 7 as the
later upgrade path for a genuinely drawn tree UI and safe parallel siblings.

## Round 5 — split /build vs /tree-build + compression (2026-07-31, same session)

User direction, now a standing principle (also saved to session memory): don't
patch instructions for every one-off failure — little things will keep going
wrong; keep complexity proportional; quarantine experimental machinery.

- The recursion (contract tree, nested subloops) moved out of `/build` into a new
  **`/tree-build`** skill (102 lines): a delta over `/build` that instructs reading
  `.claude/skills/build/SKILL.md` as the base and amends only the contract section
  and phases 6/7/9, plus one tiering row (nested node review, brain-top).
  Single-sourced — no duplicated pipeline text to drift.
- `/build` is flat again: one deliverable, one medium, one contract — the four
  fields survive (medium + ship tag, red with observable-/authored-first split,
  checked by, review), and a composite deliverable triggers an explicit
  "recommend `/tree-build` and stop" routing rule. 867 → 786 lines while keeping
  all ledger/tiering hardening. Bloat harvested: concretizing re-explanations at
  phases 3/5 → pointers, reconcile-offer ×3 → 1 (preamble owns it), phase-13
  never-modify restatement → pointer, fan-out escalation restatement, phase-11
  ship-gate reminder dupe, phase-9 tree bullet, tree example → tree-build.
- CLAUDE.md (skills list + the wip-commit exception naming both skills) and
  README updated.
- **Mid-round correction from the user:** `/tree-build`'s purpose is *speed and
  reliability*, not only mixed media — parallelism is the point, and same-medium
  splits (parallel Python modules) are in scope when the parent proves the
  children can't step on each other's toes. Split rule rewritten to exactly two
  reasons (different validation medium | parallelizable independence); new
  "Parallel siblings" section overrides /build's sequential-only rule — parent
  owns the safety call (child file sets named in the plan and verified disjoint,
  shared seams assigned to assembly never to a child, worktree isolation or
  sequential fallback otherwise, parallel plan presented at the phase-5 gate,
  background dispatch, re-green on the shared tree before each node's scoped
  checkpoint). /build's routing, fan-out note, and both descriptions updated to
  send composite *and* large-parallel cases over.
- Parallel-path probe (four parser modules + shared registry): **happy path fully
  executable by a literal reader** — correct tree, registry to assembly, all reds
  at 6, background builders, review → re-green → scoped checkpoint per close,
  root review deferred to 9; precedence clear both directions. Its structural
  gaps, fixed with one unifying rule: *the named file set scopes everything
  about its node* — build dispatch, re-green, checkpoint staging, nested-review
  diff, and recovery (a failed child restores through its own paths only; never
  reset the shared tree while siblings run); nested reviews declared read-only
  and concurrency-safe; worktree fallback gated on the checkpoint chain, merge =
  parent's assembly work. Base fix: the orchestrator logs `code-change` events
  (the old grammar had the dispatched agent writing the design doc, which the
  preamble forbids — latent sequentially, a four-way race in parallel). Left
  unpatched (anti-overfit): plan-gate kickback while siblings run (await them —
  a reading, not a rule), whole-suite re-green misread (derivable from the
  contract).

## Round 6 — deferred features landed (2026-07-31, same session)

- **Artifact shapes**: `## Artifact shapes` convention section in
  ProjectCLAUDE.md — one line per validation medium, optional pointer to a
  style/template doc; `ProjectCLAUDE.md.template` ships a commented stub.
  /build's contract section gained a five-line lookup rule: a listed medium's
  shape constrains the plan and seeds the red/rubric (a violation fails a check
  instead of surfacing as taste at review); absent section or medium = author
  freely. /tree-build inherits via the base. A project like wfe-requests can
  now pin Blinqx slide style + Python/pytest without touching any skill.
- **Live task tree**: /tree-build-only phase-5 addition — one task per contract
  node, created depth-first with the tree drawn in the subjects, `blockedBy` =
  children-block-parent + sibling dependencies, statuses flipped at loop
  transitions (in_progress at loop open, completed at node close). /build
  deliberately untouched: a single-contract run needs no tree panel.
- Both features are probe-untested by choice — the pending pilot run exercises
  them for real (give the pilot repo an `## Artifact shapes` section).

## Round 7 — recursion parked, /build refined (2026-08-03)

**`/tree-build` is parked, and the reason is structural**: Claude Code subagents
cannot spawn subagents, so its nested loops never recurse through delegation —
the orchestrator would hold the entire tree itself, buying bookkeeping and
context pressure rather than recursion. The pilot run (console tic-tac-toe,
`projects/tictactoe`, stopped at phase 4 by the user) never validated it end to
end. The file is kept as a design record with a PARKED banner naming the
blocker, and its description, CLAUDE.md and README all say so; revisit if the
constraint changes (agents that delegate, or a Workflow script driving phase 7
from the main session, which *can* fan out).

**`/build` is self-sufficient for composites again** — without regrowing a tree:
one deliverable, one contract, but *a contract may owe more than one check*.
Parts validated differently get extra `red` / `checked by` lines in the same
contract — "never extra nodes, orderings or loops" — and they are **additive: a
whole-artifact check never discharges a part's**, earned by the one-sentence PDF
anecdote. Concurrency is named as the parked open problem, so a reader hitting a
large parallelizable build learns it's known-hard rather than nothing.

**Pilot-proven fixes** (found by the real run, not by probes):

- **P1 greenfield**: phase 0 assumed a repo with history — `git rev-parse HEAD`
  errors on an unborn HEAD, so the ledger had no base. Phase 0 now says to
  `git init -b main` and make one real bootstrap commit before branching.
- **P2 deliverable outside the invoking repo**: unspecified, and dangerous — a
  bare `git commit` would have put `wip(tictactoe)` on the kit's own feature
  branch, on top of unrelated uncommitted work. First patched as a cross-repo
  capability, then **resolved by refusing the case instead of supporting it** —
  see the narrowing below.

**F7 — the three incompatible fix disciplines are one protocol now**, stated once
in the preamble and referenced from 9 and 11: reproduce first, `debugger` when
the cause isn't obvious, and — the case that made the old wording
self-contradictory — an explicit path when *no reliable repro can be made*: say
so, stand the fix on deterministic evidence at whatever level is deterministic
(the unit that mishandles the race, not the race), record the caveat. The
11-line phase-11 debugger paragraph collapsed into the pointer, so this shrank
the file.

**F9** — an unticked box at phase 11's audit is now work owed, executed before
the hand-over, not an annotation. **F17** — phase 10 must keep the run's outputs
on disk and say where, since phase 11 hands them over.

**Verification, then a narrowing.** A focused probe (two hostile phase-0 cases,
the fix protocol, the composite PDF without the sibling skill) confirmed three
areas clean: the unborn-HEAD trap "explicitly and correctly defused", the fix
protocol "genuinely single-sourced with a complete, non-colliding no-repro
path", and the composite mechanism working with both the script's code and the
rendered pages checked and reviewed, displacement "explicitly forbidden". It also
found the cross-repo support half-done, so a second probe traced every
git-touching phase for wrong-repo writes — and that probe killed the feature:

- Four HIGH/MEDIUM findings, all the same shape: cross-repo support is **one
  phase-0 sentence that has to hold across twelve phases and a dozen
  delegations**, and it doesn't. Bare `git diff` in the atomicity-recovery
  paragraphs (destructive — it reverts the *invoking* repo's uncommitted work),
  no delegation carrying the target path (a librarian running `/sync-docs`
  against the wrong repo), `isolation: worktree` having no repo parameter so the
  "point it at the target" branch isn't even executable, and no durable anchor
  after compaction (phase 12's ledger-recreation path then writes the wrong
  repo's HEAD as base, making `reset --soft` silently rewind it).
- **Resolution: `/build` refuses cross-repo runs rather than supporting them.** A
  Claude Code session is scoped to one repo — subagents inherit its cwd,
  `/commit` runs there, worktrees branch there, recovery diffs read there. Phase
  0 now detects the mismatch and stops: create and `git init` the target,
  bootstrap-commit it, tell the user to start a session there and re-invoke.
  One rule, one enforcement point, and all four findings dissolve because there
  is no second repo left to get wrong. Everything added earlier this round for
  the capability (the `git -C <home>` invariant, phase 12's `/commit` carve-out,
  the worktree caveat, the `home:` ledger field) was reverted.
- **Same lesson as parking the recursion, one layer down**: both were fights
  against harness-level scoping — no nested subagents, one repo per session. A
  skill that depends on an invariant the harness doesn't enforce will lose it.

Kept from the probe rounds regardless: the STUB gate now keys on the presence of
an executable *check* rather than the deliverable's medium (it silently skipped
stubs for a tested build script, colliding with phase 6's own right-reason
rule); phase 10 added to the close-out caller enumeration and the seed comment's
`delta` list; the frontmatter no longer routes composites to the parked sibling;
the dirty-tree case now stops rather than warns before branching; plus four
grammar/duplication seams from this session's editing (including an unresolvable
"CE" acronym).

Still open: P3 — phase 8's `docs/solutions/` has no home for a lesson about the
*skill* when the deliverable lives outside the kit (resolved ad hoc as
phase-13 kit suggestions). Deliberately unpatched per the anti-overfit rule: the
unnamed fixer agent, the debugger's phase-11-only row labels, "recreate the
branch" naming no ref, and the resume bullet's tangled-but-parseable sentence.

## Parked — found in the same read, out of scope here

Pre-existing drift unrelated to this feature, recorded so it isn't lost: the `plan` token
resolves to phase 4 under `--from` but phase 5 under `--to`; `--to` is missing from the
`argument-hint` while `--from`'s advertised `1-13` range is mostly refusable and 4–5 is a gap;
the model-tiering bullets duplicate the table and one bullet predates the contract edit;
three small ledger/checkpoint gaps (phase-6 test-writer dispatches log no `code-change`, phase
8's librarian close-out has no scope, the promised pre-12 checkpoint is never instructed); and
the bold *"a node's checked by is a delegation, not orchestrator work"* contradicts the
flagship example's *"checked by: orchestrator (grep)"* (this last one fixed in round 2).

### Round-2 additions (adversarial read; pre-existing machinery, untouched this branch)

Ship gate / ledger — **F1, F2, F3, F11 fixed in round 3 (same session)**: phase 8 now
writes the exact typed event (`close-out: librarian — scope full — …`); phase 12
closes out its ship-gate runs with events + the pre-12 checkpoint and names the
legitimate librarian re-open after fix rounds as the gate working; the "tree is
already clean" claim replaced with "either path may carry late uncommitted edits";
the checkpoint-field semantics (diffed-FROM ref, never the batch-close SHA) moved
into the phase-0 seed comment, with phase 9 now pointing at it instead of restating.
A targeted Fable probe then audited the full write/read lifecycle (write table, read
table, simulated run with a fix round + two hand-backs): **mainline coherent — every
reader has a writer, the phase-12 gate decidable for all three agents, no orphan
preamble promise**. Its residue, fixed in the same pass: `code-change` widened to
doc-editing dispatches (librarian logs one; the design doc itself exempt), closing a
gate-escape where a gate-filling librarian's doc edits shipped reviewer-unseen;
`scope` defined in the seed comment as the pass's charter, never its diff size
(phase-9 re-reviews stay `full`); the librarian's checkpoint field = the ref it ran
on; phase 7 no longer claims delta reviews diff from per-node SHAs; the
ledger-missing fallback now records its re-runs and recreates the ledger section;
phase 11 logs the batch-close SHA line its own next delta depends on.
Tiering drift — **F4, F5, F18, F19 fixed in round 4 (same session, after commit
`baeaba8`)**: hands/brain bullets deleted — the table is the single tier source,
with a nearest-analogue rule for unrowed dispatches; rows added for floating
experiments (1–4), phase-7 non-executable builders, phase-10 render-and-look,
phase-11 delta review (brain-top) and debugger (brain-mid), and phase-12 ship-gate
re-runs (their own phase rows); `/commit` re-rowed as session-model with the
Skill-vs-Agent-param mechanism stated; ceiling paragraph folds delta reviews into
brain-top and debugger into brain-mid and states the sonnet-ceiling flag duty;
phase-10 poking made mandatory delegation. A targeted Fable probe then enumerated
all 23 dispatch kinds, derived every tier, and resolved two full runs (`--brain
fable`, ceiling `sonnet`): **coherent — single-source table holds, ceiling splits
match the rows exactly, no same-dispatch contradictions, mechanism claims sound**.
Its residue, fixed same pass: an experimenter "brain" recommendation defined as
brain-top (brain-mid only for research-like evidence gathering); escalation
declared ceiling-exempt with one attempt per rung and blocked-after-fable → plan
gate (phase 7 aligned); the concretizing render tiered hands in place; row 6
annotated "a rubric run is a check, not the review" to split it from brain-top
review reads.
Protocol drift: three incompatible fix disciplines across 7/9/11, with the debugger
path dropping red entirely (F7); phase-11's checklist audit unticks boxes with no
re-entry rule (F9); "batch" and the fix-round cap's reach in phase 11 undefined
(F12). Flags/interface: `--from` on a resume slug undefined (F14); smoke outputs
consumed at 11 but preserved nowhere (F17);
resume branch recreation names no source ref (F20); phase 12 is interactive but
absent from the gates list (F22). Bloat re-confirmed and extended (tier bullets vs
table resolved in round 4): roster ×2, concretizing ×3, reconcile-offer ×3, never-modify ×3, escalation
×3, displaced-review anecdote ×2, ~7-pages ×2, ship-gate reminders ×3.
