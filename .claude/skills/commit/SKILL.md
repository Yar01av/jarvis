---
name: commit
description: Stage and commit current work as one or more well-scoped commits with clear messages. Invoke ONLY when the user explicitly asked to commit (or a user-initiated workflow like /build-feature reached its commit phase with user approval) — never spontaneously.
argument-hint: "[optional: message hint or scope]"
allowed-tools: "Bash(git status) Bash(git diff *) Bash(git log *) Bash(git add *) Bash(git commit *)"
---

Commit the current work. Context hint (may be empty): $ARGUMENTS

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
4. Commit message:
   - Subject ≤ 72 chars, imperative mood, says *what and why* — not "fix stuff".
   - Body only when the why isn't obvious from the diff.
   - Match the repo's existing convention from step 1.
5. Show `git log --oneline -n <count>` of what was created.

Never push, never amend existing commits, never commit with `--no-verify`
unless explicitly told to.
