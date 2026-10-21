---
name: commit
description: Stage and commit current work as one or more well-scoped commits with clear messages. Invoke ONLY when the user explicitly asked to commit (or a user-initiated workflow like /build reached its commit phase with user approval) — never spontaneously.
argument-hint: "[--repo <absolute path>] [optional: message hint or scope]"
allowed-tools: "Bash(git status) Bash(git diff *) Bash(git log *) Bash(git add *) Bash(git commit *) Bash(python tools/docs_lint.py*) Bash(git -C * status*) Bash(git -C * diff *) Bash(git -C * log *) Bash(git -C * add *) Bash(git -C * commit *)"
---

Commit the current work. Context hint (may be empty): $ARGUMENTS

**`--repo <absolute path>`** commits in that repo instead of the session's (an
outside repo of a `/build` run): every git command below runs as
`git -C "<path>"`, step 1's message style is that repo's, and the docs-lint step
applies only if that repo has `tools/docs_lint.py`, run there as
`cd "<path>" && python tools/docs_lint.py` (otherwise skip it and say so).

## Process

1. `git status` and `git diff` — review everything that changed. Also check
   `git log --oneline -5` to match this repo's message style (conventional
   commits, plain imperative, ticket prefixes — whatever it already uses).
2. **Scope check.** If the changes contain unrelated concerns (a feature + a
   drive-by fix + a config change), split into separate commits, each
   independently revertable. Stage selectively with `git add <paths>`.
3. **Hygiene check before staging:**
   - No secrets, API keys, tokens, connection strings, or `.env` content in
     the diff. If found: stop, warn, do not commit.
   - No debug leftovers (print statements, commented-out code, temp files).
   - No unintended files (build output, editor config, large binaries).
   - **Docs freshness** — if `tools/docs_lint.py` exists, run
     `python tools/docs_lint.py`. It is cheap, needs no credentials, and catches
     the drift nobody notices: a new doc committed without an index line, a
     `synced-commit` gone stale, a `/slash-command` or path that no longer
     resolves. Skip it only when the repo has no such script.

     **Blocking vs advisory:**
     - **Blocking — everything except `sync`.** As of 2026-08-11 `index`, `links`,
       `actions`, `commands`, `paths`, `frontmatter` and `wikilinks` are all at
       zero, so any FAIL among them is drift *this* commit is introducing. Stop,
       fix it, then commit. The common case is an orphaned doc: add its line to
       the store's index.
     - **Advisory — `sync` only.** It reports how far `docs/INDEX.md` has drifted
       from HEAD. That backlog is cleared by running `/sync-docs`, which is bulk
       work and a separate decision; blocking on it would stall every commit until
       someone did it. Report it, don't act on it.
     - **`PENDING` is never a reason to stop** — it means untracked work in
       progress, which is normal.
     - A doc that *legitimately* quotes stale content (a build narrative naming a
       path as it was, a review quoting a renamed command) opts out per check with
       `<!-- docs-lint: ignore paths -->`. Use that for documents about drift —
       never to silence real drift.
4. Commit message:
   - Subject ≤ 72 chars, imperative mood, says *what and why* — not "fix stuff".
   - Body only when the why isn't obvious from the diff.
   - Match the repo's existing convention from step 1.
5. Show `git log --oneline -n <count>` of what was created.

Never push, never amend existing commits, never commit with `--no-verify`
unless explicitly told to.
