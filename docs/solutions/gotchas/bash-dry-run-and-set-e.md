---
name: bash-dry-run-and-set-e
description: Traps hit while adding a dry-run mode to a bash installer — set -e footguns, dry-run prediction of chained mutations, Windows/Git Bash divergences, and how to test a dry run so it cannot silently drift
---

Captured from the `install.sh --check` build (see
`docs/designs/install-dry-run.md`). Every item below was *observed*, not
theorised.

## Designing a dry run

**A predicate that reads state an earlier step writes cannot be predicted from
the filesystem.** Our installer seeds `settings.json` at one step, and a later
step merges keys into *that just-written file*. A dry run writes nothing, so the
merge found no file, exited non-zero, and printed a scary "could not merge"
warning plus a `FileNotFoundError` traceback — on the most common case, a fresh
install. Fix: thread the *predicted* state (one variable holding the path the
predicate should read; in check mode it points at a temp copy of what the seed
would have written). Ansible documents the same limitation in its own check mode,
so treat it as inherent to dry runs rather than a local mistake.

**Steal rsync's invariant as your acceptance criterion.** Its man page says
dry-run output "is supposed to be exactly the same on a dry run and a subsequent
real run … if it isn't, that's a bug." Make that a literal test: run both, strip
the `would ` marker with a normalizer, assert byte equality — **and compare
stderr too**, because that is where a leaked traceback shows up.

**Make the invariant hold by construction, not by discipline.** One function is
the only place an action line is ever printed, and its sole mode-dependence is
the prefix; one function is the only place a mutation is gated. A label then
cannot drift from what actually ran. Keep check-only enrichment on a single
distinguishable marker (we used a `# ` prefix) so the normalizer needs exactly
one strip rule — and check first that no existing output already uses your
marker (six-space indentation was our first choice and it collided with existing
continuation lines).

**Never point a write-capable prediction at a real path.** A temp copy costs two
lines and removes the whole class of "the guard failed and we corrupted the
source".

## `set -e` footguns (all verified)

- **`(( X++ ))` returns 1 when X was 0** → `set -e` kills the script mid-run.
  Use `X=$((X+1))`.
- **A function whose body is `[[ cond ]] && cmd` returns 1 when the condition is
  false**, and that becomes the function's status, so a bare call to it dies.
  Add an explicit `return 0`.
- `diff -rq` returns 1 for "differs" and 2 for error; `cmp -s` and `grep -q`
  return 1 for no-match. Every one must sit inside `if` or capture `|| rc=$?`.
- An exit status that *means* something (ours: 9 = "already current") must be
  captured with `|| rc=$?`, never allowed to propagate.
- Not a trap, tested and disproven: `(( a || b )) && x=1` is safe. Only the
  post-increment form bites.

**A cleanup trap on a dual-purpose variable is a data-loss bug.** `rm -f "$VAR"`
on `EXIT` was proposed for a variable that *sometimes* holds a temp path and
sometimes a real project's `settings.json`. Keep temp paths in their own
variable that can never hold anything else.

## Windows / Git Bash divergences

- **`python3` may resolve on PATH and not be Python.** The Microsoft Store stub
  prints "Python was not found" and exits 49, so `command -v python3` succeeds
  while nothing works. Probe by *executing* (`python3 -c pass`) and fall back
  `python3 → python → py -3`.
- **msys `grep -qxF` matches lines that end `\r\n`; GNU grep on Linux does not**
  (the `\r` is part of the line, so `-x` fails). Any line-membership check
  against a possibly-CRLF file is therefore platform-dependent: **compute
  expected values with the same predicate the code uses, never pin a number**, or
  the test passes on Windows and fails on Linux.
- **`chmod +x` is unobservable** on these filesystems (mode reads 755 either
  way), so don't report it as a planned action — it would be permanent noise.
- CRLF in the working tree is often a `core.autocrlf` checkout artifact rather
  than repo content: check `git show HEAD:<file>` before concluding a rewrite
  inflated a diff.

## Testing an installer

- **`cp -R src dst` merges into an existing `dst` instead of refreshing it**, so a
  fixture reused across tests silently inherits earlier damage. Give every test a
  fresh instance.
- **Don't increment a counter inside `$( )`** — the subshell dies with its
  variable, so every "unique" path collides. Use `mktemp -d`; filesystem state
  survives the subshell. Our tell was "manifest grew from 43 to 43 entries" on a
  supposedly-fresh fixture.
- **Prove "nothing was written" with a manifest**, not by eyeballing: path, type,
  sha256, size *and* mtime before and after, diffed. mtime matters because an
  identical-content `cp` leaves the hash unchanged.
- Guard the harness with a sandbox rail that refuses any path outside the scratch
  directory, refuses the repo and its ancestors, and re-verifies a manifest of
  the repo at the end. An installer test that escapes its sandbox damages the
  machine it runs on.
- **`Only in <target>` is not a change** when the tool never deletes: reporting it
  as one makes the dry run cry wolf on every real project. Report it separately
  (we used `STALE`) and exclude it from the change tally.
- **Byte-compare only files the tool unconditionally overwrites.** For
  keep-if-exists files, mirror the tool's own conditional instead — otherwise
  every project that legitimately diverges gets reported as "would overwrite"
  forever.
