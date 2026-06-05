---
name: sync-docs
description: Build or update the hierarchically indexed codebase documentation in .claude/docs/ — bootstraps the full tree on first run, then updates only the parts touched by commits since the last sync.
argument-hint: "[optional: area to focus on, e.g. a directory]"
disable-model-invocation: true
---

Keep `.claude/docs/` — the agent-facing codebase map — in sync with the code.
If arguments were passed, treat them as a scope hint and prioritize that area:
$ARGUMENTS

## The doc tree

- Root index: `.claude/docs/INDEX.md`. One node per significant source
  directory: `.claude/docs/<relative-dir-path>/INDEX.md`, mirroring the source
  tree. The mirroring matters — it's what makes incremental updates cheap
  (changed path → doc node is a pure path mapping).
- Each index holds: a short description of what the directory is for, the
  **non-obvious** facts (entry points, boundaries, what talks to what,
  invariants), and one-line links to child indexes. No file listings, no
  restating code — if a fact is obvious from reading the directory, it doesn't
  belong here. Half a page per node is the ceiling.
- "Significant" = a directory a new senior dev would need oriented on.
  Enumerate via `git ls-files` (respects `.gitignore`, so vendored/generated
  dirs drop out for free); additionally skip anything listed under Boundaries
  in CLAUDE.md, and never document `.claude/docs/` itself. Shallow repos may
  need only the root index — don't manufacture depth.
- The root index frontmatter tracks freshness:

  ```markdown
  ---
  synced-commit: <full sha of HEAD at last sync>
  ---
  ```

## 1. Determine mode

- `.claude/docs/INDEX.md` missing → **bootstrap** (step 2).
- Present → read `synced-commit` and run
  `git diff --name-only <synced-commit>..HEAD -- . ':!.claude/docs'`.
  The exclusion is load-bearing: without it, the previous sync's own doc
  commit makes the diff non-empty forever and every run churns.
  - Diff empty → docs are current. Say so, do step 4 (self-heal) anyway, stop.
  - `synced-commit` missing/invalid (e.g. after a history rewrite) → treat as
    bootstrap, but preserve still-accurate existing content.
- Note: sync covers committed work only. If the working tree is dirty, mention
  that uncommitted changes won't be reflected until committed.

## 2a. Bootstrap (first run)

- Map the repo: top-level layout, entry points, how the pieces connect. For
  repos with several distinct areas, delegate exploration per area to parallel
  `Explore` agents and synthesize; small repos, just read.
- Write the node indexes bottom-up, then the root index: a one-paragraph
  project orientation plus one-line links to each child node — the root must
  stay cheap to read in full, since every session reads it.

## 2b. Incremental update

- Map each changed path to its doc node: the nearest ancestor directory that
  has an `INDEX.md`. Dedupe to a set of affected nodes.
- For each affected node, re-read the directory (not just the diff — the diff
  says *where*, the directory says *what's true now*) and rewrite the node.
  Unchanged-but-still-true content stays; don't churn prose for its own sake.
- New significant directories → add a node + a link line in the parent index.
  Deleted directories → remove the node and its link line. Renames → treat as
  delete + add.
- If a change altered cross-cutting facts (architecture, boundaries, entry
  points), update the root index too.

## 3. Stamp

Set `synced-commit` in the root index frontmatter to the current `HEAD` sha
(`git rev-parse HEAD`).

## 4. Self-heal the CLAUDE.md reference

Check that `CLAUDE.md` tells future sessions to read the docs. If a
"Documentation" section referencing `.claude/docs/INDEX.md` is missing, add:

```markdown
## Documentation

- Read `.claude/docs/INDEX.md` at the start of non-trivial work; drill into
  the per-directory indexes for areas you'll touch. Keep it honest: run
  `/sync-docs` after changes that alter structure or behavior.
```

If an equivalent reference already exists (any wording), leave it alone.

## 5. Report

Summarize: mode (bootstrap/incremental/no-op), nodes added / updated /
removed, the new `synced-commit`, and whether CLAUDE.md was healed. If the
diff was large and some areas got shallow treatment, say which — silent
truncation reads as "covered everything."
