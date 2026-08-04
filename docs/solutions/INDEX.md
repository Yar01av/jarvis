# Captured lessons

Hand-maintained store of gotchas, dead-ends and decisions from past work —
separate from any `/sync-docs` output. Check it when a task smells like
something this repo has hit before. Written by `/build` at phase 8, curated by
`/refresh-solutions`.

- [Bash dry-run and `set -e` traps](gotchas/bash-dry-run-and-set-e.md) — predicting
  chained mutations, `set -e` footguns that kill a script mid-run, Windows/Git Bash
  divergences (`python3` stubs, CRLF vs `grep -x`), and testing a dry run so it
  cannot silently drift from the real path
