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

## Parked — found in the same read, out of scope here

Pre-existing drift unrelated to this feature, recorded so it isn't lost: the `plan` token
resolves to phase 4 under `--from` but phase 5 under `--to`; `--to` is missing from the
`argument-hint` while `--from`'s advertised `1-13` range is mostly refusable and 4–5 is a gap;
the model-tiering bullets duplicate the table and one bullet predates the contract edit;
three small ledger/checkpoint gaps (phase-6 test-writer dispatches log no `code-change`, phase
8's librarian close-out has no scope, the promised pre-12 checkpoint is never instructed); and
the bold *"a node's checked by is a delegation, not orchestrator work"* contradicts the
flagship example's *"checked by: orchestrator (grep)"*.
