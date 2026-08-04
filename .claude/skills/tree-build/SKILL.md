---
name: tree-build
description: "PARKED, unvalidated - do not invoke casually. Recursive variant of /build whose validation contract becomes a tree with nested per-node loops and parallel independent siblings. Blocked by a harness limit: Claude Code subagents cannot spawn subagents, so the nesting cannot recurse through delegation. Kept as a design record; use /build, which handles composite deliverables additively."
argument-hint: "<deliverable description, or existing slug to resume> [--from <phase or name>] [--to <phase or name>] [--brain <fable|opus|sonnet>]"
disable-model-invocation: true
---

Build the following composite deliverable end to end: $ARGUMENTS

> **PARKED — don't run this without a deliberate decision to resume the
> experiment.** The blocker is structural, not a wording bug: **Claude Code
> subagents cannot spawn subagents**, so the nested loops below never actually
> recurse through delegation. The orchestrator holds the whole tree itself,
> which buys bookkeeping and context pressure rather than recursion. Never
> validated end to end — the one pilot run stopped at phase 4. **Use `/build`**:
> it handles a composite deliverable additively (every part's check named in one
> contract, none discharging another).
>
> Kept as the design record, because the thinking survives the blocker: the
> per-node contract, the parallel-safety rules (disjoint file sets, shared seams
> to assembly, the file set scoping recovery), and the live-tree wiring. Revisit
> if the constraint changes — a harness where agents delegate, or a Workflow
> script driving phase 7 from the main session, which *can* fan out.

**This skill is `/build` run recursively.** Read
`.claude/skills/build/SKILL.md` first and run that pipeline: its phases,
gates, checkpoint/ledger machinery, model tiering, and hard rules apply
verbatim. The amendments below override what recursion touches — the
contract's shape, phases 6/7/9, and /build's sequential-only dispatch
rule: independent siblings may build in parallel — and add a live task
tree at phase 5. That speed, plus
failures contained node-by-node (every node closes green *and* reviewed
before its parent assembles), is why this variant exists. Status:
**experimental** — when a run teaches a lesson about the recursion
itself, capture it in `docs/solutions/` at phase 8.

## The contract is a tree (amends /build's contract section)

Same four fields, but per **node** (medium / red / checked by / review;
the ship tag on the top node). **Split a node for exactly two reasons:**

1. **Different validation medium** — a different kind of check, run by a
   different checker: a PDF (rendered pages, read by an agent) built by
   a script (executable, exercised by tests) splits; a chart PNG inside
   a deck doesn't split off its slide just because it *could* be
   inspected alone.
2. **Parallelizable independence** — same-medium parts (four Python
   modules, say) whose builds don't touch each other's files, when
   running them concurrently pays. The parent owns that safety call —
   see Parallel siblings below.

A split needs one of those reasons — nothing else justifies one. A
genuinely arguable split: author the smaller tree and let the phase-5
gate resize it.

```markdown
## Deliverables
- Dutch PDF manual — medium: rendered pages (run-to-completion artifact)
  - red: an agent reads the pages against the spec and reports defects
  - checked by: reviewer agent, batched ~7 pages
  - review: the root's — phase 9 runs it
  - built from:
    - build_pdf.py — medium: executable
      - red: pytest over the parsers, observed failing first
      - checked by: pytest — test-writer authors the red
      - review: code-reviewer, inside this node's phase-7 loop
    - handleiding.html + assets — medium: content
      - red: every UI label the doc quotes exists verbatim in gui.py
      - checked by: orchestrator (grep)
      - review: reviewer agent — editorial read of the source pages
```

Every node runs its own loop, nested where the tree nests:

```
loop(node):
  red    — observe this node's stated failure, for real
  build  — a leaf: implement it.
           a parent: run loop(child) for each child, then assemble.
  green  — run this node's own check until it passes
  review — this node's *review* agent reads the result
```

**A parent's check never discharges a child's.** In the run that forced
this rule, the rendered PDF's visual review *displaced* the code review:
the build script was reviewed by nobody and shipped a bug (every internal
link double-annotated) that a rendered page cannot show by construction.
That is why review is a per-node field, not a phase-9 afterthought.

## Live tree (phase 5 addition)

When the contract is signed, materialize the tree in the harness task
panel: one task per node (TaskCreate), created depth-first with the
tree drawn in the subjects (`pdf`, `├─ build_pdf.py`, `└─ content`),
wired with `blockedBy` — every parent blocked by its children,
dependent siblings by their dependency — so the tracker itself shows
what may run and enforces the parent's safety call. Flip statuses at
loop transitions: in_progress when a node's loop opens, completed only
when it closes (green *and* reviewed — the same moment as its
checkpoint). The panel is the user's live view of parallel progress;
keep it truthful over pretty.

## Phase 6 (amended scope)

Open every observable-first red in the tree — root or nested alike; depth
doesn't matter, only whether the check can fail for the right reason
before its artifact exists. For authored-first nodes, confirm their
rubrics stand frozen; they open inside their node's phase-7 loop. The box
means both are done. Base sentences scoped to "the deliverable" apply per
node here — the STUB mechanism to executable *nodes*, whatever the root's
medium.

## Phase 7 (amended: per node, bottom-up)

A leaf builds as /build's phase 7 says. A parent runs each child's loop
in full first — red (confirm the phase-6 red still stands, or run the
authored-first rubric against the first draft now), build, green, review
— and assembles only from closed children. **Review is per node**: the
node's *review* agent at brain-top, same isolation as phase 9 (the
artifact or diff plus the design doc, nothing else); its blockers worked
off before the node counts as closed; a node nobody reviewed is not
closed, whatever its checks say. Nested reviews follow phase 9's
mechanics (findings shown to the user verbatim, max 2 fix rounds, then
hand the open findings over) but log no `close-out` event — that
vocabulary belongs to phases 9/11/12; the node-close checkpoint is their
ledger trace. Assembly is the parent's own build step,
dispatched to the agent fitting its medium; the parent's green and review
then run on the assembled result — except the root, whose review phase 9
hosts, once, never in both places. Siblings close in dependency order;
independent siblings may run in parallel (next section). Checkpoint
`wip(<slug>): <node> green` as each node closes, staging that node's
paths only.

## Parallel siblings (overrides /build's sequential-only rule)

/build forbids concurrent implementers because they share one working
tree. Here the **parent decides if parallel is safe, and owns what makes
it safe**: the plan names each child's file set; siblings run
concurrently only when those sets are disjoint, and every shared seam
(registry files, `__init__`, lockfiles, generated indexes) belongs to
the parent's assembly step, never to a child. Where disjointness can't
be established, use `isolation: worktree` and merge at assembly — or
keep those siblings sequential, /build's default. Present the parallel
plan at the phase-5 gate (which siblings run concurrently, why that's
safe); dispatch parallel children as background agents; as each closes,
re-run its green against the shared tree before its checkpoint — a
sibling may have landed meanwhile, and explicit staging keeps each
checkpoint scoped to its own node.

**The named file set scopes everything about its node**: the build
dispatch, the re-green (the node's own checks, never the full suite),
the checkpoint staging, a nested review's diff (`git diff <the
node-relevant checkpoint> -- <its paths>`, never the run base), and
above all recovery — a failed or blocked child is inspected and
restored through its own paths only; never reset the shared tree while
siblings run. Nested reviews are read-only: they may run concurrently
with sibling builds, findings serializing at the orchestrator. The
worktree fallback presupposes the checkpoint chain — a worktree sees
only committed state (/build's spike caveat, doubly so here) — so with
checkpoints declined, sequential is the only fallback; merging a
worktree child back is the parent's assembly work, conflicts included.

## Phase 9 (amended: the root's close-out)

The contract-review half of /build's phase 9 is the **root node's**
review — children were already reviewed inside their phase-7 loops. Both
code reviewers still run on the accumulated diff: per-node reviews saw
modules, not the assembled seams.

## Tiering (adds one row to /build's table)

| Phase | Agent | Tier |
|---|---|---|
| 7 Nested node review | the node's *review* agent | brain-top |

Nested reviews belong to the brain-top set in /build's ceiling split;
everything else tiers exactly as /build's table says.
