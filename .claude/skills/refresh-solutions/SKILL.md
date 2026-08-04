---
name: refresh-solutions
description: Curate the docs/solutions/ knowledge store — prune stale lessons, merge duplicates, repair the index — so it stays signal-dense as the codebase moves. Companion to /build's phase-8 capture.
argument-hint: "[--apply to skip the confirmation gate] [optional: category to focus on]"
disable-model-invocation: true
---

Keep `docs/solutions/` — the captured-lessons store that `/build`
phase 8 writes and phase 1 reads — honest and signal-dense. Lessons rot: the
code a gotcha warned about gets refactored away, two runs capture the same
insight, the index drifts from the files. Left alone the store becomes noise
and the next feature stops trusting it. This skill is the curation pass.

If arguments name a category, scope the pass to `docs/solutions/<category>/`:
$ARGUMENTS

**Destructive-op rule:** deleting or merging docs is irreversible. Present the
full proposal and get the user's confirmation before touching content — unless
`--apply` was passed. Index/frontmatter repairs are safe and apply directly.

## 0. Precondition

If `docs/solutions/` doesn't exist, there's nothing to curate — say so and
stop. The store is born on the first qualifying `/build` run.

## 1. Inventory

Enumerate `docs/solutions/**/*.md` (exclude `INDEX.md`). For each, read the
frontmatter (`name`, `description`) and body. Note its category, the symbols /
files / constraints it references, and its claimed lesson.

## 2. Staleness check

A lesson is **stale** when the thing it describes no longer holds: the file or
symbol it warns about is gone, the constraint was lifted, the gotcha was fixed
at the root so it can't recur, or it now contradicts current code. Verify
against the actual codebase — `grep`/read the referenced symbols; don't guess
from the prose. Classify each doc **keep / stale / uncertain**, with a
one-line reason. Uncertain stays (curation is conservative — only prune what
you can show is dead).

## 3. Duplicate / overlap

Group docs by topic. Two docs covering the same lesson → propose a **merge**:
the survivor keeps the richer body, absorbs anything unique from the other,
and the loser is removed. Near-overlap that's genuinely distinct stays
separate — note it but don't force a merge.

## 4. Index integrity

Rebuild `docs/solutions/INDEX.md` so every live doc has exactly one
`- [title](category/slug.md) — hook` line and no line points at a deleted or
renamed file. Fix malformed frontmatter (missing `name`/`description`) in
place. Leave the root `docs/INDEX.md` alone — the store is reached via the
phase-1 read and the CLAUDE.md docs-first note, not a root-index link
(`/sync-docs` would drop a non-source link anyway).

## 5. Report

Output what changed and why: kept N, pruned M (each with its dead-reference
reason), merged K pairs, index/frontmatter repairs applied. For pruned/merged
content, this is the confirmation gate (step's destructive-op rule) unless
`--apply`. Keep the report tight — the point is a trustworthy store, not a
ceremony.
