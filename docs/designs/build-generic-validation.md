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
Tiering: `debugger`, ship-gate re-runs, floating experiments (phases 1–2), phase-10
render-and-look, and phase-11's delta reviewer are untiered or only tiered in phase
bodies; the `/commit` "hands" row is unimplementable via a Skill call (F4, F5).
Protocol drift: three incompatible fix disciplines across 7/9/11, with the debugger
path dropping red entirely (F7); phase-11's checklist audit unticks boxes with no
re-entry rule (F9); "batch" and the fix-round cap's reach in phase 11 undefined
(F12). Flags/interface: `--from` on a resume slug undefined (F14); smoke outputs
consumed at 11 but preserved nowhere (F17); sonnet-ceiling flag duty not restated at
the ceiling paragraph (F18); phase-10 poking optional vs delegate-everything (F19);
resume branch recreation names no source ref (F20); phase 12 is interactive but
absent from the gates list (F22). Bloat re-confirmed and extended: tier bullets vs
table, roster ×2, concretizing ×3, reconcile-offer ×3, never-modify ×3, escalation
×3, displaced-review anecdote ×2, ~7-pages ×2, ship-gate reminders ×3.
