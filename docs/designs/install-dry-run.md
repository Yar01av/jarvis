# install.sh --check (dry run)

Report exactly what a real install would overwrite, keep, add, or merge in a
target project — without writing anything.

**Why**: `install.sh` overwrites `CLAUDE.md` and the whole `.claude/skills` +
`agents` trees unconditionally, and merges kit-managed keys into an existing
`settings.json`. Today the only way to learn what an install changes is to run
it. A `--check` mode makes that inspectable first.

This is also the first real end-to-end `/build` run (the pipeline has been
hardened across several sessions but never executed a full run). Process
observations are collected as kit suggestions at phase 13.

Decided at phase 0: full run from phase 1; checkpoints on; home repo is this
one (the deliverable is `install.sh` itself, so no cross-repo question).

## Phases
<!-- [ ] todo · [x] done · [-] skipped (--from) -->
- [x] 1 Research
- [x] 2 Go/no-go
- [x] 3 Requirements (compressed — 4 decisions, not a full `/grill-me`)
- [x] 4 Architecture (incl. experiments + validation contract)
- [x] 5 Plan sign-off (approved with 2 revisions — see below)
- [x] 6 Validation red (observed: 12 failed / 16 passed, exit 1)
- [x] 7 Build green (28 passed, 0 failed, exit 0)
- [x] 8 Documentation (librarian dispatch stalled — done inline; **a librarian
      full pass is owed at the phase-12 ship gate**)
- [x] 9 Review passed (2/2 fix rounds used; 35/35 green. Round 2's changes get
      their independent look at the phase-12 ship gate, which is mandatory here
      anyway — see the note in the ledger.)
- [x] 10 Smoke test (real project; headline invariant holds, 4 UX defects found)
- [x] 11 User testing (green light given; both open decisions accepted as-is)
- [x] 12 Committed (squashed to one commit; ledger SHAs replaced by milestones)
- [x] 13 Kit retrospective (4 new items, 13–16 below)

## Close-out ledger
<!-- Header: `Checkpoints: yes|no · base: <git rev-parse HEAD at phase 0>`.
     Then an append-only event log, one line each, in order:
     - checkpoint: <SHA> — <what>
     - code-change: <which agent / what>  (code or docs; design doc exempt)
     - close-out: <agents> — scope full|delta — checkpoint <ref diffed FROM>
       — deferred: <what>
     Phase 12 reads THIS, not memory of dispatch order. -->

Checkpoints: yes · base: e429b38ff2a5e684b0616ff321c735ef8d2bc5f7

**Reconciled at phase 12 by squashing** (the user's call), so the eleven `wip`
checkpoint commits this run made no longer exist. Their SHAs have been replaced
with `milestone:` lines describing what each one held, and the `close-out`
events' `checkpoint` fields now name the milestone they diffed from rather than
an orphaned hash. The `base:` above still resolves — it is the parent of the
squashed commit. **Nothing here points at a commit that isn't there**; the
trade is that the per-phase recovery refs are gone, which only mattered while
the run was live.

- milestone: seed design doc
- milestone: research, go/no-go, requirements
- code-change: test-writer — tests/check-mode.sh (28 tests, harness)
- milestone: validation red observed, 12 failing
- code-change: implementer — install.sh --check, strict parsing, hooks install,
  interpreter fallback, STALE reporting, gitignore trailing-newline fix
- code-change: orchestrator — corrected test_stale_… summary-line anchor
  (adjudicated: test was wrong, assertion substance unchanged)
- milestone: build green, 28/28
- code-change: orchestrator — docs/solutions/gotchas/bash-dry-run-and-set-e.md
  + docs/solutions/INDEX.md (new store)
- code-change: orchestrator — README.md (--check, exit codes, strict parsing)
  + ProjectCLAUDE.md (test command; corrected the "no docs/ tree" claim).
  **The `librarian` dispatch stalled (watchdog, 600s, no edits written — tree
  verified clean before proceeding), so no `close-out: librarian` event exists
  for phase 8. That is deliberate: the phase-12 ship gate requires each of the
  three agents to have a `full`-scope close-out postdating the last
  code-change, so it will force the librarian pass then rather than let an
  un-run agent pass silently.**
- milestone: docs
- close-out: code-reviewer + maintainability-reviewer — scope full — checkpoint
  the run base — deferred: none  (review pass 1)
- code-change: implementer — fix round 1 (exit-3 ERR trap + `set -Eeuo`, WARN
  cause discrimination, prediction-incomplete gating, scoped chmod, version
  probe, manifest mode bits, 4 tests, harness refactors, comment corrections)
- code-change: orchestrator — README exit code 3 / hooks / `--link` caveat;
  ProjectCLAUDE test-count unpinned
- milestone: fix round 1, 32/32
- close-out: code-reviewer + maintainability-reviewer — scope full — checkpoint
  the run base — deferred: none  (review pass 2; no blockers, one should-fix)
- code-change: implementer — fix round 2 (BASHPID-guarded mode-aware ERR trap,
  pseudo-evidence comment removed, restored `act`/`emit`/`tree_scan` comments,
  apply-mode `^would ` assertion, artifact-name collisions, abort-test
  decoupling, mechanical failure-message sweep, doc corrections) + 3 tests
- milestone: fix round 2, 35/35
  <!-- Lesson from this line's history, kept because it generalises: it once
       carried a SHA written in the same commit it named, then `--amend`ed —
       which orphaned that very commit. A ledger line naming a SHA must be
       written in a FOLLOW-UP commit, never via amend. (Moot now that the
       squash replaced SHAs with milestones, but the trap is real.) -->
  <!-- Note for phase 12: both close-out events above PREDATE the fix-round-2
       code-change, so the ship gate will correctly refuse until both reviewers
       (and the still-owed librarian) run again on the final tree. That is the
       gate working, not a bookkeeping error — 2/2 fix rounds are spent, so a
       third pass here could only hand findings to the user anyway, and the ship
       gate is the designed place for that look. -->
- code-change: implementer — phase-10 smoke-test fix round: incomplete
  merge-prediction now forces exit 2 (never 0) with a non-contradictory
  trailer even when `WOULD` is 0; `--link --check`'s SKIP trailer no longer
  promises a plain re-run fixes it (says "resolve the skipped paths first,
  then re-run" instead); the unknown-flag usage error now echoes the
  rejected flag (`Unknown option: <flag>`). 3 tests added
  (`test_exit_2_when_merge_prediction_incomplete`,
  `test_link_check_skip_trailer_says_resolve_manually`,
  `test_unknown_flag_error_names_the_flag`) — 38/38, `SAFETY PASS`.
- milestone: phase-10 fixes; final 38/38 re-run by the orchestrator
- code-change: librarian — README.md: `STALE` no longer framed as
  deprecation-only (it flags anything the kit doesn't currently ship, including
  project-local additions), the `--link` exit-0 condition corrected to require
  **both** trees skipped, the merge-warning text corrected to the real
  "no working python: tried python3, python, py -3", and a newly-traced gap
  documented — under `--link --check` the `skills`/`agents` trees are never
  stale-scanned at all, only `hooks/` is
- close-out: librarian — scope full — checkpoint the phase-10-fixes milestone — deferred: none
- close-out: code-reviewer — scope full — checkpoint the post-librarian tree — deferred: none
  (**SHIP**, no blockers, two should-fix)
- code-change: orchestrator — its two should-fix items applied verbatim:
  `${BASHPID:-$$}` fallback (BASHPID is bash 4.0+; on bash 3.2 `set -u` made
  the trap body itself fatal → exit 1 after a partial write, i.e. the very bug
  the trap exists to prevent), and the `prediction incomplete` marker
  documented as **stdout** in both `install.sh`'s header and README — it had
  said stderr, which is the one string advertised as machine-readable. Plus the
  header's stale note now records that `--link` scans only `hooks/`.
- milestone: ship-gate code fixes
- close-out: code-reviewer — scope full — checkpoint the ship-gate-fixes milestone — deferred: none
  (**SHIP holds**; resumed rather than re-dispatched, and it re-verified all
  three trap paths on bash 5.2 *and* a bash-3.2 proxy)
- code-change: orchestrator — README exit-code list reflowed (the reviewer's
  cosmetic nit; the enumeration had been interrupted mid-list)
- milestone: README reflow + ship-gate ledger
- close-out: **general-purpose (maintainability scope)** — scope full —
  checkpoint the final tree — deferred: none. Verdict: nothing blocks a commit; all
  findings are open items.
  <!-- GATE DEVIATION, stated plainly: the dedicated `maintainability-reviewer`
       failed THREE times without doing any work — an API stall, then two
       watchdog stalls, across opus and fable. The third died fetching the test
       list, so the fourth attempt pre-supplied that data inline, narrowed the
       read set to 130 lines, and substituted a `general-purpose` agent, which
       finished in three minutes. So the gate is satisfied in SUBSTANCE (an
       independent agent examined the maintainability dimension of this exact
       tree) but not in LETTER (the named specialist never ran). Logged under
       the agent that actually did the work — relabelling it
       `maintainability-reviewer` would erase which specialist saw what, which
       is the one thing this ledger exists to record. The user's call whether
       that suffices. -->
- code-change: orchestrator — two of its findings applied (comment text only,
  no functional change): `act()`'s header still carried the same "can never
  drift from what ran" over-claim that had been narrowed in `emit()`, and
  contradicted itself one clause later — now "can never drift from the
  mutation it was written for … NOT proof that mutation succeeded", with the
  brittle literal `"COPY .claude/hooks/ …"` dropped so a rename can't stale
  it. Also closed its Q2 gap: the header now explains **why a failed
  prediction is exit 2 and not 3** (`settings_merge` runs as `… || rc=$?`, and
  the left of `||` is exempt from the ERR trap), with a warning to keep that
  wrapper — the invariant most likely to be broken by a future edit.
  <!-- Ship-gate pass. The phase-8 dispatch stalled and was never logged, so
       the gate correctly forced this. It was not a formality: three real README
       inaccuracies were found, two of them introduced by the orchestrator. -->

## Research

## Research

**Verdict: build it inline. Nothing to buy** — the prior art here is a
convention, not a dependency. ~40–60 lines against a 135-line script.

**Conventions.** Two distinct spellings with different meanings: `-n` /
`--dry-run` (rsync, make, stow, apt) means *simulate and narrate*; `--check`
(`git apply --check`, `ansible --check`) means *validate, report, and signal via
exit code*. Per-action prefixed lines are the norm — content diffs are a
separate composable flag (`ansible --check --diff`), not the default. Every
mature tool distinguishes "nothing would change" from "changes pending", via a
summary line and/or exit code.

**The invariant worth stealing, verbatim from the rsync man page:** dry-run
output "is supposed to be exactly the same on a dry run and a subsequent real
run … if it isn't, that's a bug." That is this feature's acceptance criterion,
and it is directly testable.

**Two structural traps, both verified by the researcher:**

1. **Chained mutation.** The real run seeds `settings.json` at an early step,
   and the merge step then reads *that just-written file*. A dry run writes
   nothing, so the merge reads a missing file, exits 1, and prints
   `WARN could not merge` — a **false warning on the most common case** (fresh
   install). Rule: any predicate reading state an earlier step writes must
   consume the plan, not the filesystem. Ansible documents the same limitation
   for check mode.
2. **Arg parsing swallows unknown flags.** `MODE="${2:-copy}"` means anything
   in `$2` that isn't literally `--link` selects copy mode, so
   `install.sh <dir> --chekc` performs a **real install, silently**.

**Implementation pattern: single code path with mutations behind an
argv-taking guard** (`run() { if $CHECK; then :; else "$@"; fi; }`).
`get.docker.com` is prior art for the shape, but its string form
(`$sh_c "cp -R $a $b"`) is wrong here — this project's own paths contain spaces
("OneDrive - Blinqx"), so argv must survive unquoted. Three rules: only
mutations are gated (every predicate runs identically in both modes, which is
what makes the modes share one decision tree); the label is emitted by the same
helper that gates, so a label cannot drift from what ran; and the `.gitignore`
append needs its own helper, since redirection can't ride in argv. Rejected:
plan-then-apply (encoding 11 heterogeneous operations into a shell data
structure is a rewrite, and the interpreter loop becomes the new bug home) and
native dry-run flags (`cp`/`ln`/`mkdir` have none; `rsync` is absent here).

**Difference detection.** `diff -rq` per tree, `cmp -s` for the four single
files. Verified `cp -R` semantics: copies merge, changed files overwrite, files
removed from the kit persist forever, unrelated local files untouched. So
`Files … differ` → would overwrite, `Only in <src>` → would add, and
**`Only in <target>` is a no-op that must not be reported as a change**. CRLF is
not a noise source — both sides come from the same checkout, so EOL matches by
construction; `--strip-trailing-cr` would make `--check` *under*-report and is
rejected. No "would chmod" line: verified that mode is 755 either way under this
filesystem, so `chmod +x` is unobservable.

**Settings merge.** The existing heredoc already computes the prediction
(`sys.exit(0 if changed else 9)`). Reuse it: add `sys.argv[3]` = `check|apply`
gating only the `open(...,"w")`, keep the heredoc quoted, and wrap the whole
block in one shell function — a heredoc is stdin, so two call sites would mean
two copies, which is exactly the drift this feature exists to prevent.

**Environment (verified).** `bats`, `shellcheck`, `shellspec`, `rsync`, `jq` all
absent. `python3` is a Microsoft Store stub that exits 49 — the real interpreter
is `python` (3.13). Present: `diff`, `cmp`, `sha256sum`, `find`, `stat`, `git`.
So: plain-shell test harness, no dependencies; and `ProjectCLAUDE.md`'s
"check with `shellcheck` if available" is currently unenforceable here.

**Pre-existing bugs found** (5): `.claude/hooks/` is never installed though the
baseline `settings.json` wires a hook to it; `python3` resolves to a
non-interpreter here so the merge *always* warns; `--link` silently deep-copies
on Git Bash (and is non-idempotent across runs); stale kit files are never
removed from targets (`build-feature/` still lives in every installed project
after the rename); `install.sh` is CRLF in the working tree with no
`.gitattributes` pinning `*.sh eol=lf`.

**Docs gap** (flagged per CLAUDE.md's docs-first rule): `ProjectCLAUDE.md` says
"There is deliberately no `docs/` tree here", but `docs/designs/` now exists and
is git-tracked. There is no `docs/INDEX.md` and no `docs/solutions/`, so there
was no tree to traverse — but the flat claim is false and should become "design
docs only; no `/sync-docs` tree, no INDEX".

## Go/no-go

**Build**, with strict flag parsing in scope. No library to buy; the change is
additive to a script the kit already owns.

## Requirements

**Scope.**

- `--check` (aliases `--dry-run`, `-n`) reports what a real run would do and
  writes nothing.
- **Real flag parsing**: iterate `"$@"`, accept `--link` / `--check` / aliases,
  **reject unknown arguments with exit 1**. `--link --check` composes.
- **Output**: existing label vocabulary (`COPY/KEEP/LINK/SKIP/MERGE/OK/WARN/
  GITIGNORE`), each action line prefixed `would ` in check mode, per-tree counts
  rather than per-file lines, a mode header, and a summary
  (`N would change · M unchanged · K warnings`).
- **Exit codes**: `0` nothing would change · `2` changes pending · `1` usage or
  internal error. Documented in the usage header. **Corrected at phase 10**:
  `0` additionally requires the settings-merge prediction to have succeeded —
  an incomplete prediction (e.g. invalid JSON in the target's
  `settings.json`) forces exit `2` even when the tallied `WOULD` count is 0,
  so exit 0 never claims knowledge it lacks. Exit `3` (mid-run abort) was
  added later, at fix round 1 — see Architecture.
- **Also in scope** (agreed at the gate): install `.claude/hooks/`; interpreter
  fallback `python3 → python → py -3`; report stale target files as
  informational `STALE` lines (reporting only, never deletion).

**Acceptance criteria.**

1. Check mode writes nothing — before/after manifest identical, including no
   `.claude/` created in an empty target (catches the unguarded `mkdir -p`).
2. **Anti-drift**: check output equals real output minus the `would ` marker,
   for every fixture. This is the rsync invariant as a test.
3. Exit code matches state: 0 when current, 2 when changes pending, 1 on a
   usage error.
4. An unknown flag exits 1 and writes nothing.
5. A fresh (empty) target predicts the `settings.json` seed *and* reports keys
   already current — no false `WARN could not merge`.
6. `Only in <target>` never counts as a change; it surfaces as `STALE`.

**Edge cases**: CRLF `.gitignore` (the append guard must not double-add); absent
or stubbed `python3`; `--link` on Git Bash, where `ln -sfn` deep-copies — check
mode mirrors `install.sh`'s own output rather than correcting it; UTF-8 BOM in
`CLAUDE.md`; spaces in every path.

**Non-goals**: content diffs (`--diff`); deleting stale files; fixing `--link`
on Windows; pinning EOL via `.gitattributes`; adopting `bats`.

## Architecture

**Core idea: make the anti-drift invariant hold *by construction*.** One code
path; mutations behind an argv-taking guard; and **`emit` is the only place an
action line is ever printed**, its sole mode-dependence being a constant
`would ` prefix. A label therefore cannot drift from what ran, and the rsync
invariant is a property of the code rather than of discipline.

### Helper API (inserted after `set -euo pipefail`)

```bash
run()   { (( $# == 0 )) && return 0; [[ $CHECK == true ]] && return 0; "$@"; }
emit()  { if (( $1 )); then WOULD=$((WOULD+1)); else SAME=$((SAME+1)); fi
          if [[ $CHECK == true ]]; then printf 'would %s\n' "$2"
          else printf '%s\n' "$2"; fi; }
act()   { local line="$1"; shift; emit 1 "$line"; run "$@"; }   # report + gate together
same()  { emit 0 "$1"; }                                        # KEEP / OK / identical
note()  { [[ $CHECK == true ]] && printf '# %s\n' "$1"; return 0; }  # check-only
        # ^ the explicit `return 0` is REQUIRED: in apply mode the [[ ]] test is
        #   false, its status becomes the function's, and a bare `note …` call
        #   then kills the script under `set -e`. (Found during phase 7.)
warn()  { WARNINGS=$((WARNINGS+1)); printf '%s\n' "$@" >&2; }
gi_append()      # terminates an unterminated last line first (Spike A finding B)
settings_merge() # THE single call site for the embedded Python (heredoc = stdin)
resolve_python() # probes by EXECUTING (the Store stub resolves on PATH, exits 49)
tree_scan()      # check-only: find -print0 + per-file cmp -s → counts + STALE
copy_kit_file()  # unconditional-overwrite single file: cmp -s → same|act
usage()
```

Globals: `CHECK=false LINK=false WOULD=0 SAME=0 WARNINGS=0 HAVE_PY=false PY=()
MERGE_TGT="" MERGE_TMP="" TS_CHANGED=0`. (`MERGE_TMP` and `TS_CHANGED` were added
during the build — see phase 7; `MERGE_TMP` must stay separate from `MERGE_TGT`.)

One helper the plan didn't budget as its own function but the build needed:
`plan_settings_seed <report_keep>` — shared by the link and copy branches so the
seed decision and `MERGE_TGT` can't be set in one and forgotten in the other.

**Enrichment marker is `# `, deliberately not indentation** — `install.sh`
already emits six-space continuation lines (the npx warning), so an indent rule
would silently swallow real output.

**The script runs `set -Eeuo pipefail`, and the `E` is load-bearing.** Without
`errtrace`, an `ERR` trap set at top level **never fires for a failure inside a
function** — and nearly every mutation here runs through `run()` /
`copy_kit_file()`. The mid-run-abort trap (exit 3) added at phase 9 would have
been silently inert without it; proven empirically before and after.

**Trap table** (the script dies without these):
`X=$((X+1))` never `(( X++ ))` (returns 1 when X was 0 — the likeliest
implementation slip, and it would kill a real install mid-run); `settings_merge`
via `rc=0; … || rc=$?` (rc 9 *is* the unchanged signal); `cmp -s` and
`grep -qxF` always inside `if`; the interpreter probe inside `if`.
**Corrected at phase 9:** an earlier version of this table claimed a zero-arg
`"$@"` fails under `set -e` and so `run` must return early. That is false —
verified, it returns 0. Any empty-argv guard in `run` is `set -u` hygiene for
bash ≤ 4.3, not a `set -e` trap; don't cite it as one.

### Argument parsing (replaces the positional `TARGET`/`MODE`)

A `while (( $# ))` / `case` loop: `--link` and `--check|--dry-run|-n` set
independent booleans (so they compose, order-free), `-*` is rejected with usage
and exit 1, a second positional is rejected. The existing validations (empty or
non-directory target, refusing the kit repo) stay unchanged after the loop. The
loop is a pure predicate — identical in both modes.

### Flow (M = mutation, gated · P = predicate, never gated · E = check-only)

| # | Step | Kind | Check-mode output |
|---|---|---|---|
| 0 | parse, resolve target, refuse kit repo, `resolve_python` | P | — |
| 0b | mode header | E | `# CHECK mode — nothing will be written · target: …` |
| 1 | `mkdir -p .claude` | M | — (gated; AC1 catches it) |
| 2 | link branch: `SKIP` (stderr) or `act "LINK …" ln -sfn` | P+M | `would LINK …` |
| 3 | copy branch: `tree_scan` ×2 then one `emit` then `cp -R` ×2 | P+M+E | `would COPY  .claude/skills/ + .claude/agents/` + count/STALE notes |
| 4 | `plan_settings_seed` (both branches) | P+M | `would COPY`/`would KEEP` + sets `MERGE_TGT` |
| 5 | `copy_kit_file` statusline + gated `chmod` (silent) | P+M | `would COPY  .claude/statusline.sh …` |
| 6 | **NEW** hooks tree: `tree_scan`, `emit`, `cp -R`, `chmod -R +x` | P+M+E | `would COPY  .claude/hooks/ …` + count note |
| 7 | merge: rc 0 → `MERGE`, 9 → `OK`, else → `WARN` | P (write gated) | `would MERGE`/`would OK`/`WARN` |
| 8 | `copy_kit_file` CLAUDE.md | P+M | `would COPY  CLAUDE.md …` |
| 9 | ProjectCLAUDE.md seed-if-missing | P+M | `would COPY`/`would KEEP` |
| 10 | gitignore loop ×3 via `act … gi_append` | P+M | `would GITIGNORE  added …` |
| 11 | npx preflight | P | identical (stderr) |
| 12 | `Done. …` | — | identical |
| 13 | summary + exit | E | `# N would change · M unchanged · K warnings — …` |

`chmod` stays gated but **silent**: mode is 755 either way here, so "would
chmod" would be permanent noise. `tree_scan` is the one deliberate exception to
"predicates run in both modes" — it feeds no decision (the tree COPY line is
unconditional, Spike A finding D), only enrichment, so running it in apply mode
would be ~23 wasted `cmp` calls.

### Predicting the two unpredictable lines

**(a) The settings line.** One variable, `MERGE_TGT`, holds the path the merge
predicate reads, set in a single `plan_settings_seed` function shared by both
branches so it cannot be forgotten in one. When the seed would fire, check mode
points `MERGE_TGT` at the *baseline the seed would copy* — merging the kit's keys
into a copy of itself yields `changed == False` → rc 9 → the real run's
`OK … already current` line, with no false WARN and no traceback. Exact, not
approximate, and verified three ways: identical copy → rc 9; target missing the
kit key-groups → rc 0 (`MERGE`); missing file → rc 1 + traceback.
`settings_merge`'s third argument (`check|apply`) gates the `open(…,"w")`.

**(b) The `GITIGNORE` line.** Unpredictable *only because of the bug*. Fixing it
(`gi_append` terminates an unterminated last line before appending) removes the
cause: an append can no longer alter another line, so the three `grep -qxF`
predicates become mutually independent and reading the filesystem is exact. No
threading needed once the bug is gone.

### Output contract

```bash
normalize() { grep -v '^# ' | sed 's/^would //'; }
```

Applied identically to both streams in both modes → byte equality. On real
output both rules are no-ops, so the normalizer is symmetric and cannot mask a
genuine difference. Two constraints every future line must respect: **no action
line may contain the target path** (the harness compares two different fixture
copies), and **stderr lines never carry `would `** (they describe present
environment state, not a projected action).

Literal expected output, empty target, `--check` (exit 2). **Note the count notes
precede the action line they annotate** — `tree_scan` prints before `emit` runs;
an earlier version of this block showed them after, which never matched the code
(corrected at phase 9). Harmless to the invariant, since `normalize` strips
`# ` lines either way:

```
# CHECK mode — nothing will be written · target: /tmp/fx/empty
#   skills: 0 would overwrite · 12 would add · 0 identical · 0 stale
#   agents: 0 would overwrite · 10 would add · 0 identical · 0 stale
would COPY  .claude/skills/ + .claude/agents/
would COPY  .claude/settings.json (baseline — adjust per project)
#   predicted against the baseline settings.json this run would seed
would COPY  .claude/statusline.sh (kit-managed usage tracker)
#   hooks: 0 would overwrite · 1 would add · 0 identical · 0 stale
would COPY  .claude/hooks/ (session hooks wired via the kit baseline)
would OK    .claude/settings.json kit-managed keys already current
would COPY  CLAUDE.md (kit-managed — do not edit; put project context in ProjectCLAUDE.md)
would COPY  ProjectCLAUDE.md (from template — fill in the project-specific sections)
would GITIGNORE  added .claude/settings.local.json
would GITIGNORE  added CLAUDE.local.md
would GITIGNORE  added .claude/worktrees/
Done. Open the project and run /skills to verify everything loaded.
# 9 would change · 1 unchanged · 0 warnings — re-run without --check to apply (exit 2)
```

Already-current target (exit 0): same shape with `would KEEP` for
`settings.json` and `ProjectCLAUDE.md`, all counts `identical`, and
`# 0 would change · 7 unchanged · 0 warnings — nothing to do (exit 0)`.
Note `would COPY .claude/statusline.sh` still prints with zero counted changes —
the line is honest that the installer's *intent* is an unconditional copy, while
`copy_kit_file` skips the `cp` entirely when the bytes already match — in either
mode. ("Change" means content, not mtime; an earlier version of this paragraph
wrongly said the real run performs the `cp` regardless. Corrected at phase 9.)
`Done.` prints in
both modes, which is the price of the strict invariant; the summary immediately
clarifies.

**Exit codes**: `0` nothing would change (or apply completed) · `2` check mode
with `WOULD > 0` · `1` usage error · `3` mid-run abort (added at fix round 1 —
see Review). Counters move only inside `emit` and `warn`, one site each, in
the same function that prints — a count cannot drift from the lines shown.
**Corrected at phase 10**: the "prediction incomplete" suffix is keyed on the
merge's own return code (`rc`), not on `$HAVE_PY` — a working interpreter that
fails to parse the target's `settings.json` is just as incomplete a prediction
as no interpreter at all, and previously landed in the WARN arm without
forcing anything. Now an incomplete prediction **forces exit 2**, even when
`WOULD` is 0 (the trailer changes from "nothing to do" to "re-run without
--check to apply" in that case too, so the two never contradict each other) —
so exit 0 never claims knowledge it lacks, and the README's
`--check || install` gate always retries rather than silently treating an
unresolved merge as a no-op. The stale `(python3 missing?)` WARN text becomes
`(no working python: tried python3, python, py -3)`.

### Test harness — `tests/check-mode.sh`

Plain bash, zero dependencies. Runs with `set -u` but **not** `-e`/`pipefail`
(it's a runner with explicit accounting, and `grep -v` legitimately returns 1
when it filters everything).

**Safety rail**: every removal goes through `sandbox_rm`, which aborts unless the
path is a proper descendant of a scratch dir whose name contains
`jarvis-check-mode.`, is not the kit or an ancestor of it, and has ≥3
components. The kit is manifested before the first test and re-checked at the
end.

**Fixtures**, each built once into `pristine/` and `cp -R`'d fresh per test:
`empty`, `current` (one real install), `stale` (+ `build-feature/` and a local
skill), `divergent-settings` (kit keys intact plus a project-only entry — the
Spike B case where the installer says KEEP but `cmp` says differ),
`missing-kit-keys`, `invalid-json` (kit keys current but the file itself is
syntactically broken JSON — added in fix round 1 for the WARN
cause-discrimination fix), `partial`, `gitignore-crlf`, `gitignore-noeol`.

**Assertion 1 — no writes**: manifest (`find -print0` → per entry `D`/`L`/`F`
with sha256, mtime, size, and permission bits) before and after; `diff` must be
empty. mtime and size are included so an identical-content `cp` is still
caught; permission bits so a silent `chmod` is too; a newly created `.claude/`
shows up as a new `D` line, which is AC1 exactly.

**Assertion 2 — anti-drift**: instantiate the fixture twice, `--check` into one
and a real apply into the other, then compare normalized stdout **and stderr**.
Comparing stderr is load-bearing — it's what catches the `FileNotFoundError`
traceback Spike A found leaking.

**Finding C handling**: the CRLF fixture's gitignore expectations are **computed**
by running the installer's own predicate against the pristine fixture, never
pinned — msys grep matches CRLF lines (0 adds here) while GNU grep on Linux does
not (3 adds there). Its load-bearing assertions are the two
platform-independent ones: anti-drift equality, and convergence in one apply run.

### Implementation steps

1. `tests/check-mode.sh` skeleton (rail, `manifest`, `normalize`, runners,
   `expected_gitignore_adds`, fixture builders, empty `TESTS=()`).
2. All test functions + populated `TESTS`; **run it and record the red.**
3. `install.sh` header: usage gains `[--check]`, exit-code table. Doc-only.
4. Globals + helper block + `usage()`. Nothing calls them; `bash -n` passes.
5. The parse loop; keep both existing validations; call `resolve_python`.
   → parsing/usage tests go green.
6. Route existing steps through `run`/`act`/`same`/`warn`/`copy_kit_file`,
   preserving every line's exact text and order; add header, summary, exit.
   → no-write, exit-code, most anti-drift tests.
7. `settings_merge` wrapper + `plan_settings_seed` with `MERGE_TGT`.
   → the settings-prediction tests.
8. `gi_append` wired through `act` + the soundness comment.
   → the gitignore tests.
9. Hooks step + `tree_scan` counts and `STALE` notes.
   → hooks, stale, count, enrichment tests.
10. `README.md`: document `--check`, the exit codes, that `.claude/hooks/` is now
    installed, and that `STALE` reports without deleting.
11. `ProjectCLAUDE.md`: replace "No build, no test suite" with
    `bash tests/check-mode.sh`; correct the false "deliberately no `docs/` tree"
    to "design docs only; no `/sync-docs` tree, no INDEX". (Not the
    `.template` — that seeds other projects.)
12. Full harness green + the two additive checks, then review.

`.claude/` is untouched throughout. Size: `install.sh` 135 → ~225 lines, above
research's 40–60 estimate because four separately-agreed items ride along.

### Risks

`(( x++ ))` under `set -e` killing a real install mid-run. **Writing into the
kit** — in check mode `MERGE_TGT` points at a kit path, defended twice (the
`argv[3]` write gate, `run`) and detected once (`git status --porcelain` empty
after the harness); the plan calls this the highest-severity failure mode. A
future line printed with a bare `printf` instead of `emit` silently breaking the
invariant — the reviewer brief is the real guard. Apply-mode output regressing
(the anti-drift tests prove check==apply, not apply==yesterday; the phase-10
smoke and a pinned pre-change transcript cover it). `--link --check` always
reporting `would LINK` because the real run always runs `ln -sfn` — mirroring
the installer rather than correcting it, as required.

**Deviation from research, flagged so review doesn't read it as drift**: the tree
predicate is `find -print0` + per-file `cmp -s` rather than `diff -rq`, because
`diff -rq` reports a source-only directory as *one* `Only in` line regardless of
how many files it holds (incommensurable with a per-file "identical" count) and
its output strings are locale-dependent. Same primitive research chose, applied
per file.

## Deliverables

- `install.sh --check` + the three agreed fixes + the trailing-newline fix —
  medium: executable (bash script and plain-shell test runner; run-to-completion)
  - red: on a pristine empty fixture, `install.sh <fixture> --check` **performs a
    real install today** (Spike A finding E), so `tests/check-mode.sh` prints
    `FAIL test_check_writes_nothing_empty_target: manifest grew 1 -> 26 entries`,
    `FAIL test_gitignore_does_not_corrupt_unterminated_last_line: expected 'p2',
    found 'p2.claude/settings.local.json'`,
    `FAIL test_unknown_flag_exits_1_and_writes_nothing: rc 0, manifest changed`,
    and `FAIL test_hooks_tree_installed_in_apply_mode: …caveman-sessionstart.sh
    missing after apply` — then exits 1. Observed for real before any line of
    `install.sh` changes.
  - checked by: `bash tests/check-mode.sh` → `0 failed`
  - checked by (additive): one `--check` then one real apply against a throwaway
    copy of an *actual* installed project, transcripts normalized and diffed —
    the rsync invariant outside the fixture set
  - checked by (additive): `git status --porcelain` empty in the kit after the
    full harness run — proof the `MERGE_TGT` substitution never wrote to source
  - review: `code-reviewer` at brain tier on the `install.sh` diff plus the
    harness, briefed on the `set -euo pipefail` trap table and on whether any new
    line breaks the "`emit` is the only printf" invariant

## Plan sign-off

Approved, with two revisions that override the plan above:

**Revision 1 — predict the merge against a temp copy, never a kit path.** The
plan pointed `MERGE_TGT` at `$SRC/.claude/settings.json` in check mode, guarded
by the Python write gate and `run`. Risk deleted instead of guarded:

```bash
MERGE_TGT="$(mktemp)"; cp "$SRC/.claude/settings.json" "$MERGE_TGT"   # trap cleanup on EXIT
```

Identical result (merging the kit's keys into a byte-identical copy still yields
`changed == False` → rc 9 → the `OK` line), but a failed guard writes to a
throwaway file rather than corrupting the kit. `test_check_never_writes_to_the
_kit_repo` and the `git status --porcelain` check stay as detectors.

**Revision 2 — the test list is trimmed from 44 to 28.** Both big assertions keep
their fixture breadth; what went are redundant parsing variants and detail tests
the anti-drift assertion already covers transitively. Phase 5 is where checks get
resized, and 44 tests for a 225-line script is the over-heavy shape this pipeline
exists to catch. **This list is the executable spec — implement verbatim:**

```
# parsing / usage
test_unknown_flag_exits_1_and_writes_nothing
test_refuses_kit_repo_as_target
test_check_and_link_compose

# writes nothing
test_check_writes_nothing_empty_target
test_check_writes_nothing_gitignore_noeol_target
test_check_never_writes_to_the_kit_repo

# anti-drift: normalized stdout AND stderr equality, check vs real apply
test_antidrift_empty_target
test_antidrift_current_target
test_antidrift_divergent_settings
test_antidrift_missing_kit_keys
test_antidrift_gitignore_crlf
test_antidrift_gitignore_noeol
test_antidrift_link_mode

# exit codes
test_exit_0_when_target_current
test_exit_2_when_changes_pending
test_apply_mode_still_exits_0

# the settings line (unpredictable line 1)
test_no_false_warn_could_not_merge_on_empty_target
test_no_python_traceback_on_stderr_empty_target
test_predicts_merge_when_kit_keys_missing
test_keep_settings_never_reported_as_overwrite
test_merge_succeeds_when_python3_is_a_stub

# the gitignore line (unpredictable line 2) + the corruption bug
test_gitignore_all_three_predicted_on_missing_file
test_gitignore_does_not_corrupt_unterminated_last_line
test_gitignore_converges_in_one_apply_run

# stale reporting
test_stale_entry_reported_and_not_counted_as_change

# in-scope fixes and the output contract
test_hooks_tree_installed_in_apply_mode
test_enrichment_lines_are_check_only
test_no_action_line_contains_the_target_path
```

Scope acknowledged at sign-off: `install.sh` 135 → ~225 lines, a new `tests/`
directory, and edits to `README.md` and `ProjectCLAUDE.md` (both of whose claims
— "No build, no test suite" and "deliberately no `docs/` tree" — become false
with this change).

## Validation red — observed

`bash tests/check-mode.sh` against the **unmodified** `install.sh`:
**16 passed, 12 failed**, harness exit 1, deterministic across three runs.
`git diff -- install.sh` empty; kit manifest re-checked and unchanged after every
run; no scratch dirs left behind.

The 12 failures, by cause:

- **`--check` doesn't exist** (4): unknown flag exits 0 instead of 1;
  `--link --check` performs a real link install (only `$1`/`$2` are ever read);
  check mode on an empty target grew the manifest **0 → 42 entries**; check mode
  rewrote a fixture's `.gitignore`.
- **No exit-code contract** (1): every invocation exits 0.
- **No interpreter fallback** (3): `python3` is the Store stub, so the merge warns
  unconditionally — including on a target a working predictor should call current
  — never predicts `MERGE` when kit keys are missing, and never succeeds.
- **The trailing-newline bug** (2): `p2` fused into
  `p2.claude/settings.local.json`; one apply run leaves
  `.claude/settings.local.json` unrecoverable as a standalone line.
- **Features absent** (2): no stale scanning at all; `.claude/hooks/` never
  installed, so `caveman-sessionstart.sh` is missing after apply.

Three failures reproduce the design doc's own predicted red lines almost
verbatim, which is the evidence that the harness observes the real installer
rather than an artifact.

**Seven of the 16 passes are vacuous, and this is load-bearing for phase 7.** All
`test_antidrift_*` currently pass only because `--check` is silently swallowed —
both invocations run the byte-identical real install, so of course they match.
That is Finding E restated, not evidence the invariant holds.
`test_no_python_traceback_on_stderr_empty_target` is likewise environment-vacuous
(the stub never runs real Python, so no traceback is reachable). **These become
the genuine test of the anti-drift invariant the moment `--check` exists, and may
well fail first.** Three further passes hold only because a feature is absent
(no `# ` lines exist yet; `KEEP` is coincidentally an existence check, not a
byte-compare). Genuinely meaningful today: the kit-write guard, the kit-repo
refusal, apply-mode exit 0, exit 0 on a current target, and no action line
carrying the target path.

**Harness bug found and fixed during authoring** (worth recording — it nearly
produced a fake red): `new_instance` incremented a counter inside a command
substitution, so the increment died with the subshell and every instance for a
fixture collided on one path; because `cp -R src dst` nests into an *existing*
`dst`, later tests silently inherited earlier tests' damage. The tell was
"manifest grew from 43 to 43 entries" on a supposedly fresh empty fixture. Fixed
with `mktemp -d` (filesystem-backed uniqueness survives the subshell).

### Spec defects found by the test-writer — resolved here

1. **`STALE` line format was contradictory. Resolution: stale entries are `# `
   enrichment notes, never bare action lines.** Requirements and AC6 say stale
   files "surface as `STALE`", while the Architecture section's literal output
   block shows only a lowercase `stale` count field inside a `# ` note. The
   binding constraint settles it: a real run prints **nothing** about stale
   files, so any non-`# ` stale line would appear in check output and vanish
   from apply output — breaking the anti-drift invariant by construction. So the
   format is `#   STALE <relpath>`, one per stale top-level entry, alongside the
   count field. The plan's step 3 already said "emits the count note then one
   STALE note per stale entry"; the sample output simply had no stale files in
   its fixtures, which is why none appeared. `test_stale_entry_reported_and_not
   _counted_as_change` therefore asserts on a `# `-prefixed STALE note — a
   clarification of the check, not a weakening of it: "reported, and not counted
   as a change" is unchanged.
2. **Orphaned `partial` fixture**: the Architecture section lists 8 fixtures but
   Revision 2's trim to 28 tests left `partial` with no consumer. Its builder
   exists and is deliberately never instantiated. Accepted as-is — inventing a
   29th test to justify a fixture is backwards.
3. The predicted red's `manifest grew 1 -> 26` was illustrative; the observed
   figure is `0 -> 42`. Not a defect — recorded so nobody pins the wrong number.

## Build — phase 7

Implemented at hands tier in one dispatch. **27 of 28 green; the single red was a
genuine test/spec contradiction, correctly escalated rather than silenced.**

**Adjudication (orchestrator).** `test_stale_entry_reported_and_not_counted_as
_change` asserted on `^[0-9]+ would change` — anchored to a leading digit — but
the summary line is `# N would change · …`, and that prefix is *structurally
forced*: `normalize()` strips `# ` lines, apply mode prints no summary at all, and
seven anti-drift tests require normalized check-stdout to equal apply-stdout. An
unprefixed summary would break all seven. One test's anchor against seven tests'
invariant: **the test was wrong**, and its anchor is corrected to
`^# [0-9]+ would change`. This is a clarification, not a weakening — the
assertion's substance ("stale reported, and not counted as a change") is
untouched, and the semantics were verified directly: two `#   STALE …` notes
emitted, and `would change` tallies equal between the `stale` and `current`
fixtures.

**Deviations from the plan, all reported rather than silent:**

1. **`MERGE_TMP` is a separate global from `MERGE_TGT`** — and this one matters.
   Revision 1's snippet implied trapping `MERGE_TGT` for cleanup, but that
   variable also holds the *real* target `settings.json` path on the
   keep-if-exists branch and on every apply run, so a blanket `rm -f
   "$MERGE_TGT"` on EXIT **would delete a real project's settings file**.
   `MERGE_TMP` only ever holds the mktemp path. The plan was wrong; the fix is
   correct.
2. **`note()` needs an explicit `return 0`** — a real defect in the plan's helper
   API, since `[[ … ]] && printf` leaves status 1 in apply mode and `set -e`
   would kill the script on a bare `note` call. Corrected in the Architecture
   snippet above.
3. **The hooks line was reworded** to `(session hooks wired via the kit
   baseline)`: `test_keep_settings_never_reported_as_overwrite` greps
   `COPY.*settings\.json`, which collided with the original parenthetical
   `(session hooks wired via settings.json)` — same line, unrelated file. The
   literal-output block above is updated to match. A tighter regex
   (`COPY +\.claude/settings\.json`) would be the better long-term fix.
4. `SKIP  .claude/$dir exists and is not a symlink…` routed through `warn()` so
   it counts toward `WARNINGS` — an interpretive call the flow table didn't
   settle, and **no test exercises the link-mode SKIP path**, so it is unverified
   either way.
5. **Size: 440 lines, not the ~225 estimated.** The implementer attributed this
   to per-helper doc-comments; **phase 9 measured that and it is wrong by ~3×.**
   Of 368 added lines only 87 are comments, and only ~64 of those are per-helper
   docs (21% of net growth) — delete every one and the file lands at ~376, not
   225. The real cause: five features were agreed *at the gate* (hooks step,
   `resolve_python`, `tree_scan`, the strict parse loop) plus `plan_settings_seed`
   which the plan never budgeted as a helper, and **nobody re-derived the estimate
   after scope grew**. The honest close-out line is "440 because five agreed
   features were never re-estimated", not "because of comments" — the wrong
   attribution is what would make the next reader delete the comments that *are*
   load-bearing.

**Apply-mode output delta — for reviewers, so this is not read as a regression.**
On this machine apply-mode stdout now *gains*
`OK    .claude/settings.json kit-managed keys already current`, and stderr
correspondingly *loses* the "Python was not found" banner and the
`WARN could not merge` line. Cause: the in-scope `python3 → python → py -3`
fallback means the merge step now actually runs where it previously failed
silently. Confirmed by diffing old-vs-new apply output directly. This is the
agreed fix surfacing, not drift.

**EOL note:** the stored blob was already LF (the CRLF in the working tree was a
`core.autocrlf` checkout artifact, not repo content), so the diff — 367
insertions, 61 deletions — is genuine and reviewable rather than a
whole-file rewrite.

A non-trap, raised and disproven: `(( a || b )) && x=1` is safe under
`set -euo pipefail` (verified across four variants); only `(( X++ ))`'s
post-increment truthiness is the hazard. Recorded so the trap table isn't
over-applied later.

## Review — phase 9

Both reviewers ran at brain-top on the accumulated diff plus this doc, with no
implementation context. The code reviewer independently re-ran the harness
(28/28, `SAFETY PASS`), reproduced every finding in throwaway targets, and
verified diff integrity (367/61 against a 134-line original — ~73 original lines
survived, so a genuine diff rather than a whole-file re-emit).

**Categories verified clean — recorded because a review that only lists problems
mis-prices the change.** No escape from the dry-run guard: all fourteen mutation
sites enumerated and each gated, the embedded Python's single write behind
`mode == "apply"`, and the only ungated check-mode write is the deliberate
`mktemp` copy — with `/tmp` entry counts identical before and after, proving the
EXIT trap fires. No missed `set -e` instance (including the confirmation that the
EXIT trap doesn't clobber the exit status). No bypass of the `emit` invariant. The
exit arithmetic is correct and warnings rightly don't influence it. The harness
sandbox rail is sound, and the two `install.sh` calls that bypass `run_install`
are both justified. No duplicated or parallel implementation introduced —
`settings_merge`, `gi_append` and `copy_kit_file` each *replaced* their
predecessors rather than sitting beside them.

**Blocker: the exit-code contract this change created is false in one row.**
`exit 1` is documented "always writes nothing", but `set -e` also exits 1 on a
mid-run failure *after* partial writes. Reproduced with one unwritable file in the
target's hooks dir: `skills/`, `agents/`, `settings.json`, `statusline.sh` written;
`CLAUDE.md`, `ProjectCLAUDE.md`, `.gitignore` absent. Since the README now ships
`--check || install` as a gate, a caller reading that table treats a half-install
as a no-op — and the new hooks step added an abort point *deeper* in the sequence
than the pre-existing one. Sub-finding: `act` emits *before* `run`, so apply-mode
printed a `COPY` line for a `cp` that then failed — the invariant is "check text
equals apply text", **not** "an action line corresponds to a mutation that
succeeded". Worth knowing when reading the guarantee.

**Should-fix:** the merge WARN asserts "no working python" for *any* non-0/9 rc,
so invalid JSON in a target's `settings.json` (reproduced with a trailing comma)
sends the user chasing a Python install; `— prediction incomplete` is gated on
`HAVE_PY` rather than on whether the prediction succeeded, so a broken
`settings.json` yields exit 0, "nothing to do", and **no settings line at all**,
defeating the gate exactly when a human should look; `chmod -R +x` recurses over
the *target's* hooks dir and silently promoted a project-local hook from 444 to
555, with no action line and no way for the harness to see it because
`manifest()` omits mode bits — so AC1 is weaker than it reads.

**Maintainability, headline finding:** the size attribution above was measured and
corrected (see phase 7 item 5). Three code comments state falsehoods, two of
which had propagated into this doc (both corrected above). About 25 of the ~64
comment lines are provenance or design-argument rather than constraint, with a
line-by-line verdict list; the reviewer's structural point is that the narrative
belongs in `docs/solutions/` and the inline comment needs only the one clause that
stops the next edit.

**Highest-value maintainability finding:** nothing in the code guards the output
contract. A future step written as `run cp …` plus a bare `echo "PRUNE …"` passes
all 28 tests — identical in both modes (anti-drift passes), writes nothing
(no-write passes) — yet never reaches `emit`, so the counter doesn't tick, the
summary says "nothing to do", exit is 0, and the advertised gate skips a needed
install. This doc had nominated *the reviewer* as the guard for that invariant,
which is a guard with a one-run lifetime. Also: six test failure messages are
frozen at the red phase and now assert falsehoods ("install.sh has no `--check`
exit-code contract yet") — stale *runtime output*, which hands a future debugger a
confident wrong diagnosis.

**Fix round 1** dispatched covering both reviews: the exit-code contract (a
distinct code 3 plus an honest header), WARN cause discrimination, the
prediction-incomplete gating, scoped `chmod` plus mode bits in `manifest()`, an
interpreter version probe, the output-contract guard test, the stale failure
messages, two coupled regexes, the dead `antidrift_check` parameter and its
hand-inlined duplicate, a `assert_no_writes` helper, the three false comments and
~25 lines of narration.

**Accepted without fixing** (recorded so they aren't rediscovered): renaming
`plan_settings_seed` (it does perform the copy in apply mode, so the `plan_`
prefix misleads) and `same` → `unchanged`; the sandbox self-check's cost for two
known-good paths; the ~20 hand-invented two-letter output-file suffixes in the
harness; and `--link --check` always exiting 2, which is spec-accepted but means
the README's gate never short-circuits under `--link` (one caveat sentence would
close it).

### Fix round 1 — outcome

**32 passed, 0 failed** (four tests added: mid-run abort, invalid-JSON WARN cause,
prediction-incomplete gating, and the output-contract guard). Every A/B/C item
done except where noted below.

**The implementer's own catch, and it saved the blocker's fix from being
useless: `set -euo pipefail` had to become `set -Eeuo pipefail`.** Without
`errtrace`, an `ERR` trap set at top level never fires for a failure *inside a
function* — and nearly every mutation runs through `run()` / `copy_kit_file()`.
The reviewer's literal snippet would have been silently inert for exactly the
scenario it was written to catch. Proven empirically before and after.

**Three reviewer claims the implementer corrected, with evidence:**

1. **The chmod repro was invalid on this platform, though the defect was real.**
   On Git Bash, `chmod 444` on any shebang-bearing file still reads `555`, so the
   cited "project hook went 444 → 555" would reproduce with or without the bug.
   The underlying defect was confirmed a different way: a *non*-shebang file
   stayed `444` after the fix and would have become `755` before it. Consequence
   worth carrying: `manifest()`'s new mode-bit field is **inert for
   shebang-bearing files on this machine** — the same category of
   platform-scoped canary as the CRLF fixture.
2. The blocker's fix snippet was incomplete (the `set -E` point above).
3. "No settings action line at all" was imprecise — `KEEP .claude/settings.json`
   prints unconditionally whenever the file exists, before and after. What was
   actually missing was the correct WARN cause and the incomplete-prediction
   suffix; both are fixed.

**Deliberately not fixed:** the "no action line for `chmod`" half of the chmod
finding, because the design already decided `chmod` stays gated but silent (mode
is unobservable here, so a `would chmod` line would be permanent noise).

**New latent asymmetry, recorded rather than fixed:** check mode can never abort
(mutations are gated before they run), so an *apply* run that hits the new abort
emits a stderr line the check run never emits. No fixture triggers it today, and
it is the same shape as the already-recorded "`act` emits before `run`" caveat —
the invariant is "check text equals apply text on a successful run". **Retracted
at fix round 2: the premise is false.** `plan_settings_seed`'s check-only
`MERGE_TMP="$(mktemp)"` + `cp` into it are real, ungated writes (to a scratch
file, never the target), so check mode can abort too — reproduced with a broken
`TMPDIR` — and the one fixed trap message was then wrong for that case: printed
twice (once in the command-substitution subshell `-E` hands the trap, once in
the parent) and claimed the *target* was partially written when nothing was.
Separately, `-E` also hands the trap to `tree_scan`'s process substitutions,
where `exit 3` only kills that subshell — reproduced by shadowing `find` to
exit 1 after running: the trap fired three times on a run that then completed
successfully with correct output and exit 2. Fixed: the trap message is
`$CHECK`-aware ("nothing was written" vs "target may be partially written"),
and a `BASHPID` guard stops it firing (printing) from any subshell — see
Review pass 2.

**Untested, reported honestly:** the interpreter probe's Python-2 rejection (no
Python 2 on this machine to falsify against — code-read only); the WARN's
"no working python" arm (only the invalid-JSON arm has a test); and the sandbox
self-check's positive case removes a path *nested under* the scratch root
rather than the root itself, so it doesn't exercise the case the new startup
assertion exists for. **No longer true, corrected at fix round 2:** this used
to also list the harness's final `sandbox_rm "$SCRATCH_ROOT"` unchecked return
status, reasoning it "would leak the scratch tree silently" on plain Linux with
an unmodified `/tmp`. That's unreachable now — the startup rail added in fix
round 1 (the "new startup assertion" referenced two sentences up) already
aborts before any fixture is built if `SCRATCH_ROOT` resolves to fewer than 3
path components, which is the only condition under which `sandbox_rm`'s own
shallow-path check would refuse and leak the tree.

**Docs updated by the orchestrator** (outside the implementer's file list):
README gained exit code 3, the `.claude/hooks/` mention, and a caveat that the
`--check || install` gate never short-circuits under `--link`; its changelog
prose was dropped; `ProjectCLAUDE.md` no longer pins a test count.

### Review pass 2 — after fix round 1

Both reviewers re-ran the suite themselves (32/32) rather than trusting the
report. **Code review: no blockers.** It verified `set -E`'s blast radius is
exactly the ERR trap and that every deliberate tolerance survives — a function on
the left of `||` doesn't fire ERR, so `settings_merge … || rc=$?` is safe and
rc 9 still means "unchanged"; `&&`-list non-final failures and `if`-guarded
predicates don't fire either. All four exit codes confirmed empirically, and the
exit-3 target was *genuinely* partial. It also hand-checked the interpreter
probe's previously untested arm (`env -i PATH=…` with no interpreter → correct
WARN, the incomplete suffix, and normalized check == apply on both streams) and
confirmed piping check output to `head -1` dies of SIGPIPE rather than through
the trap.

**The one should-fix is the trap itself, and it lies in two reproduced ways.**
(a) Check mode *can* abort — `MERGE_TMP="$(mktemp)"` and the copy into it are real
writes — and with `TMPDIR` pointed at a nonexistent directory it exits 3 printing
"target may be partially written" **twice** (once in the command-substitution
subshell that `-E` now hands the trap, once in the parent) with nothing written.
(b) `set -E` hands the trap to `tree_scan`'s process substitutions, where `exit 3`
kills only the subshell: with `find` returning 1 — what it does on an unreadable
directory — the trap fires three times while the run **completes** with correct
output and exit 2. So the message claims an abort that didn't happen and a partial
write that couldn't, and it does so **only in check mode** — a check-only stderr
line, which is exactly the divergence the rsync invariant forbids and which the
harness enforces on stderr. Fix adopted: a `BASHPID` guard to restore pre-`-E`
subshell behaviour plus a mode-aware message, using `_err_rc` rather than the live
global `rc` (read at the summary suffix).

**Maintainability verification:** every claimed item landed except two.
`test_every_check_line_is_prefixed_or_known` was verified empirically — a bare
`echo` action line injected into a synthetic kit turns the suite red with a
precise message, and only that test fails. Its hole: the same line written as
`printf 'would PRUNE …\n'` still passes, because `emit` is bypassed either way,
and apply mode then prints a literal `would …` line nothing objects to. And
**`act()` lost its whole comment** — the only helper without a signature header,
taking with it the caveat that `act` emits *before* `run`, so an action line is
not proof the mutation succeeded. Exit 3 made that observable. Meanwhile
`emit()`'s surviving comment still claims a label "can never drift from what
happened", which the abort path falsifies.

**Self-inflicted by fix round 1** (recorded because the cause is instructive): a
comment citing `(verified: 444 -> 555)` — a measurement this very doc retracts;
a README sentence promising the gate "installs only when something is actually
stale" when stale is deliberately uncounted, so a stale-only target exits 0 and
the gate does nothing; artifact filenames in the new shared helpers keyed on the
fixture alone, so three `empty` callers overwrite each other's captured output;
and a fixture-build abort that prints "see `<file>`" then deletes the tree
containing it.

**Three of the reviewers' kit suggestions are criticisms of how the fix-round
brief was written**, and they're correct — see Kit suggestions below.

### Fix round 2 — outcome

**35 passed, 0 failed** (three tests added: the `TMPDIR`-broken check-mode
abort, a PATH-shadowed `find` inside `tree_scan`'s process substitutions, and
running the output-contract guard against a second fixture). `git status
--porcelain` clean in the kit after the run; `SAFETY PASS`.

**The trap fix landed as the reviewer specified**, verified against both
repros before and after: `TMPDIR=/nonexistent-dir-xyz` now aborts check mode
exactly once, saying "nothing was written" (previously: twice, saying "target
may be partially written"); the PATH-shadowed `find` repro now completes
normally with correct output and exit 2 and prints no `ABORTED` line
(previously: three prints on a run that still completed). `$CHECK` was
already set (to `false`) before the trap is installed — no reordering needed.

**The false "check mode can never abort" premise is corrected in all three
places it was stated**: this doc (above, and in the "Untested" list's scratch-
tree-leak reasoning, now separately corrected as unreachable), `install.sh`'s
exit-3 header row, and `README.md`'s exit-code line — all three now say
check-mode-aborts-say-nothing-was-written / apply-mode-aborts-may-be-partial.
The README's "`--check || install`" gate description is also corrected: it
installs when something *would actually change*, not "is actually stale" —
stale entries are deliberately uncounted, so a stale-only target is a gate
no-op, now stated rather than implied.

**Comments retracted or restored, per item 4:** the `(verified: 444 -> 555)`
pseudo-evidence is dropped from the chmod comment, leaving the
platform-independent reason (re-moding a project-local hook, silently) intact.
`act()` regained its signature header and the "emits before run" caveat;
`emit()`'s comment now claims only "check text equals apply text on a
successful run" rather than a label "can never drift from what happened";
`tree_scan`'s comment regained "never called in apply mode" as the named
exception to "predicates run in both modes".

**Should-fix items, done:** `test_enrichment_lines_are_check_only` now also
asserts no `^would ` line in apply-mode stdout; the output-contract guard
(`test_every_check_line_is_prefixed_or_known`) now runs against both `empty`
and `current`; `assert_no_writes` and `antidrift_check` now derive their
artifact filenames from the full argument vector via a new `artifact_tag`
helper, and `assert_no_writes` surfaces stderr on both failure branches;
`build_fixture_current`'s abort now `cat`s its stderr inline instead of
pointing at a file it's about to delete; `test_midrun_abort_exits_3_and_says
_partial` no longer pins install.sh's exact step order (it asserts some
evidence of partial work plus the absence of the `Done.` line) and no longer
hardcodes the hook filename — a new `HOOK_SAMPLE_NAME`, derived from the kit's
own `.claude/hooks/`, is shared by both tests that needed it; the two present-
tense failure-message claims that survived round 1's enumerated list (the
hooks "is never installed" message and the two gitignore-fusing parentheticals)
are reworded to describe the violated expectation, found via a sweep of every
`fail "..."` message rather than a repeat of the same list; the fixture list
above now includes `invalid-json`, and Assertion 1 now mentions permission
bits; the two `return 0`s were evaluated rather than blindly restored — both
`resolve_python` and `tree_scan` already return 0 unconditionally on every
path, a structural property (an `if`/`fi` with no `else` exits 0 same as a
successful `break`; an `if`/`else` where both arms are plain assignments
exits 0 either way), checked against a reduced stand-in for each function's
control flow rather than the live functions themselves — so a one-line
comment on each records why, instead of dead code; the redundant
`if [[ -d ... ]]` split in the chmod loop
is collapsed (`chmod -R +x` is a no-op on a plain file); and one clause now
sits above the mutation sequence stating the idempotence requirement exit 3
imposes on every step, present and future.

**One should-fix intentionally left for the user, not silently dropped:**
renaming `plan_settings_seed`/`same` and the ~20 hand-invented harness output-
file suffixes were already "accepted without fixing" at phase 9 and are out
of this round's scope (a fix-round brief, not a fresh review); not revisited.

## Smoke test — phase 10

Exercised against a **real** installed project (`wfe-requests`) rather than
fixtures — its `.claude/`, `CLAUDE.md`, `ProjectCLAUDE.md` and `.gitignore` copied
to scratch (the only paths `install.sh` touches), preserving the real cruft:
extra `projects/`/`tools/`/`worktrees/` dirs, a `settings.local.json`, a
`statusline.py`, a CRLF `.gitignore`, 11 skills including the stale
`build-feature`, 13 agents including 3 stale, and a UTF-8 BOM on the kit's
`CLAUDE.md` the target's copy lacks. Original untouched and verified so.

**Transcripts preserved** (phase 11 hands these over):
`…/scratchpad/smoke/` — subdirs `real-check`/`real-apply`, `link-check1/2`,
`noseed-check`/`noseed-apply`, `abort-apply`/`abort-check`, `invalid-json*`,
`gitignore-noeol`, `local-extras*`, plus numbered `NN-*.stdout/.stderr/.exit`.

**What held.** The headline invariant — normalized check-vs-apply diff **empty on
both stdout and stderr** against real-world state, outside the fixture set. A
re-check of the applied copy exits 0 with the four pre-existing stale entries
still reported and still uncounted. `--dry-run` and `-n` are byte-identical to
`--check`; `--link --check` and `--check --link` differ only in the `# ` target
path line, so flag order is genuinely immaterial. All exit codes confirmed on real
state, with each abort message matching its mode. **Recovery works**: after
`chmod 644` on the offending hook, a re-apply converges and a follow-up check
reports nothing pending — the header's "safe to repeat" promise holds.
**The design's self-nominated worst risk came out clean**: forced onto the
`mktemp` seed-prediction branch with twin copies lacking `settings.json`, check
predicted `would OK … already current` (no false WARN), matched apply exactly, and
the kit's `git status --porcelain` was empty immediately after. Awkward states all
behaved: invalid JSON warns with the right cause and the incomplete suffix, a CRLF
`.gitignore` adds exactly one line, a no-trailing-newline `.gitignore` is not
corrupted, and project-local skills/agents survive apply byte-for-byte.

**Four defects, all invisible to the unit suite because it never ran the
documented workflow:**

1. **`--check` exits 0 when its own prediction is incomplete — breaking the gate
   the README sells.** On a target current except for invalid JSON in
   `settings.json`: `# 0 would change … nothing to do (exit 0) — prediction
   incomplete`. Running the advertised `--check || install` verbatim, the install
   never fired, so a script treats an unresolved settings merge as "nothing to do"
   and silently never retries. A phase-9 reviewer had recorded this as
   "[nit, no action needed]"; *executing* the workflow rather than reasoning about
   it is what promoted it. **Fixed at phase 10: incomplete prediction now exits 2.**
2. **`--link --check`'s trailer advises a fix that cannot work.** Alongside
   `SKIP .claude/skills exists and is not a symlink — resolve manually.` the
   trailer says `re-run without --check to apply` — which will not link those
   directories; only removing them will. **Fixed at phase 10.**
3. **The unknown-flag error doesn't echo the rejected flag** — the difference
   between diagnosing a typo and an unsupported option. **Fixed at phase 10.**
4. **`Done. Open the project and run /skills to verify everything loaded.` prints
   in check mode**, immediately above a summary saying nothing was installed. The
   design accepted this as "the price of the strict invariant"; the smoke read is
   blunter — it "reads as a lie on first encounter". **Deferred to the phase-11
   gate as a user decision** (below).

**Two implementation-time refinements to items 1 and 2, both verified by
reproducing before/after against the pre-fix code in a detached worktree:**

- **Item 1's first draft left a contradiction**: forcing exit 2 without also
  changing the trailer produced `nothing to do (exit 2)` on the invalid-JSON
  target — the exact defect class item 2 exists to kill, just self-inflicted.
  Fixed by giving the incomplete-prediction case the same trailer as
  `WOULD > 0` ("re-run without --check to apply"), since a plain re-run
  really is the correct action either way.
- **Item 2's fix is a trailer-wording change only, not an exit-code change** —
  as scoped. Consequence, verified directly: when *both* `.claude/skills`
  and `.claude/agents` already exist as real directories and nothing else is
  pending, the check now reads `resolve the skipped paths first, then re-run
  (exit 0)`. That 0 is correct, not a regression — a real run into that same
  target would equally just re-print the two SKIP warnings and change
  nothing, so "0 = nothing would change" still holds; only the trailer text
  needed correcting, not the exit semantics. The README's `--link` gate
  sentence is worded to match (a check "usually" reports pending work in
  link mode, with this one named exception).

**Also surfaced, deferred to phase 11: `STALE` mislabels project-local
additions.** A skill the kit has *never* shipped is flagged
`# STALE .claude/skills/our-custom-skill` beside genuinely deprecated entries, and
the README's definition ("no longer shipped by the kit") is wrong for that case.
The files survive untouched, so this is a naming/documentation defect, not data
loss — but the label asserts a history that didn't happen.

**Review of the phase-10 fixes** folds into the phase-12 ship gate rather than
taking a separate delta pass. The two-speed rule exists because the full pass is
normally deferred; here it is already *forced* (both reviewers' close-outs predate
fix round 2, and the librarian is owed), so it runs on the final tree within this
same session — an interim delta on a ~30-line fix would be redundant, not safer.

## User testing — phase 11

**Checklist audit, evidence per tick** (the phase's first duty — a box ticked on
inference goes back to `[ ]`):

| # | Evidence |
|---|---|
| 1 | `researcher` returned sourced findings + 6 answered questions; written into `## Research` |
| 2 | User answered "Build, with strict parsing" at the gate |
| 3 | Four decisions answered at the gate — labelled *compressed*, not a full `/grill-me` |
| 4 | `planner` returned the plan; written into `## Architecture` |
| 5 | User approved with 2 revisions, both recorded as overrides |
| 6 | 12 failed / 16 passed, exit 1, `git diff -- install.sh` empty — the red observed against the unmodified script |
| 7 | 28/28 (orchestrator re-ran it), then 32, 35, **38 — final tally re-run by the orchestrator, exit 0, `SAFETY PASS`** |
| 8 | README + ProjectCLAUDE + `docs/solutions/` written; **librarian never ran — owed at phase 12**, no close-out logged |
| 9 | Two review passes, two fix rounds, no blockers at pass 2; reviewers independently re-ran the suite |
| 10 | Real project exercised, headline invariant empty on both streams, transcripts on disk |

One tick did not survive the first pass: phase 7's final 38/38 was known only from
the agent that made the change (reviewers had verified 32 and 35). Re-run by the
orchestrator before hand-over — `38 passed, 0 failed`, exit 0.

Open decisions handed to the user (neither is a bug; both are visible choices):
the `Done.` line printing in check mode, and `STALE` labelling project-local
additions as though the kit had deprecated them.

**Outcome: green light, no issues raised.** Both open decisions therefore ship
as-is — `Done.` keeps printing in check mode (the strict-invariant tradeoff
stands) and `STALE` keeps its name. Recorded as *accepted*, not as forgotten: if
either grates in real use, the `Done.` fix needs a normalizer rule and the `STALE`
fix is a rename plus a README definition, both small and both already scoped
above.

## Kit suggestions

From the phase-9 reviewers. Suggestions only — `.claude/` is untouched by this
run; the user decides what to apply.

1. **The comment rule this run measured itself against isn't in the repo.** The
   reviewer grepped `CLAUDE.md`, `ProjectCLAUDE.md`, the template and all of
   `.claude/`: the "state a constraint the code can't show / never provenance,
   never why-the-change-is-correct" rule exists in neither. The shipped guidance is
   only "match comment density" (`.claude/agents/implementer.md`,
   `.claude/skills/implement/SKILL.md`), and the reviewer's own brief said the
   looser "explain why, not what" — which positively *licenses* the provenance
   comments this run produced. Putting the stricter wording into `CLAUDE.md` and
   `implementer.md` would prevent it at the point of writing.
2. **Provenance-in-comments has a specific cause**: the implementer had the design
   doc in context and wrote comments arguing against it ("deviation from the design
   doc's literal Revision 1 snippet", "not something this task revisits"). A line in
   `implementer.md` — *the design doc is not a reader of your code; plan revisions,
   spikes and "previously" belong in the ledger, not a comment* — targets it.
3. **`/build`'s red phase should mark failure messages as throwaway.** Six stale
   messages exist because the test-writer was asked for a *specific observed* red
   and dutifully encoded the pre-change diagnosis into permanent assertion text. A
   phase-7 line — *after green, re-read every failure message: it must describe the
   violated expectation, not the implementation that violated it* — closes a generic
   TDD-pipeline hazard.
4. **Re-derive the size estimate when the gate adds scope.** The ~225 predated four
   gate-agreed features and `plan_settings_seed`; nobody re-ran it, so the overshoot
   got attributed to the most visible thing on screen instead of measured.
5. **Phase 8 should require an invariant the design doc calls load-bearing to be a
   test or a code guard, not a reviewer brief.** This doc named the reviewer as the
   guard for the output contract — the finding most likely to cost real money here.

From review pass 2 — the first three are criticisms of how the orchestrator wrote
the fix-round brief, and they generalise beyond this run:

6. **Phrase fix-round items as what must stop being true, not as lines to delete.**
   "Delete the comment block at `act()`" was obeyed literally and took the helper's
   signature header and a load-bearing caveat with it. Intent survives
   over-application; a line number doesn't.
7. **Ask for a sweep, never a list, when the defect is a pattern.** Six stale
   failure messages were enumerated and fixed; the two not on the list survived,
   because an enumerated brief guarantees the tail is missed. "Grep every failure
   message for present-tense claims about the implementation" would have got all
   of them.
8. **The comment rule should forbid *evidence*, not just provenance.** Round 1
   replaced provenance comments with a measurement comment (`verified: 444 -> 555`)
   that the same commit's design doc retracts. Proposed wording: *an inline comment
   states a constraint that survives the next edit; measurements, repro transcripts
   and "verified: …" belong in the ledger or `docs/solutions/`, never in the code.*
9. **When collapsing tests onto a shared helper, derive artifact names from the
   full argument vector.** Parameterising a helper predictably makes several
   callers share one output path and silently destroy each other's post-mortem
   evidence.

From phase 12 — the ship gate met reality:

10. **Phase 12 has no guidance for a ship-gate agent that dies.** The librarian
    stalled at phase 8 and both reviewers then died to a mid-stream API error at
    the gate itself, having done no work. The rules that matter and aren't
    written down: **never log a close-out for an agent that didn't complete**
    (that is precisely how an un-run agent passes the gate silently), verify the
    tree before re-dispatching even when the agent was nominally read-only, and
    treat an infra death as a plain retry rather than an escalation — escalation
    is for *blocked*, not for *crashed*. Worth a clause in phase 12.
11. **Dispatching the gate's two reviewers in parallel is a false economy.** Each
    pulls a ~1900-line diff and was also asked to re-run a multi-minute suite;
    they failed simultaneously. Sequential, with the suite re-run marked optional
    when the orchestrator has already verified the tally on unchanged code, is
    both cheaper and more likely to finish. `/build` currently says phase 9's
    reviewers run in parallel and phase 12 inherits that shape without comment.
### From the phase-13 retrospective (items 13–16)

Presented as the agent returned them. It resolved its own evidence — 1940
transcript lines, 36 subagent records — and listed what it deliberately did not
inspect (the phase-6 test-writer and phase-7 implementer transcripts, the three
stalled dispatches' own records, and whether phase 11's per-tick audit claims
actually hold).

13. **[high] The concretizing gate instantiated the interface's *nominal* state
    only — and every phase-10 smoke defect lived in a state nobody instantiated
    or executed.** `.claude/skills/build/SKILL.md`, the concretizing paragraph
    plus one clause at phase 7. The rule was honoured well: the gate carried
    three `AskUserQuestion` previews (output shape, granularity, exit codes).
    All three showed the happy path and the already-current path. All three
    phase-10 defects were **degenerate or partial-knowledge states of the very
    interface that was gated**, and two were never executed until phase 10. The
    rule's own rationale indicts the outcome — *"prose is a poor medium to
    confirm it in… reads as complete and unambiguous prose while quietly
    assuming exactly one of the thing being configured"* — and the exit-0
    invariant sat in prose in this doc, twice, signed off at phase 5; the smoke
    brief had to quote it back at the code to prove the defect. **Proposed:** the
    instantiation must cover declared **failure and partial-knowledge** states,
    not just the nominal one — for a CLI, one sample per exit code the contract
    defines, including the "cannot determine" case. Plus a phase-7 exit
    precondition, *before* reviewers are dispatched: execute the documented
    interface once per declared state and paste the observed output into the
    design doc. Phase numbering stays stable; phase 10 keeps its breadth
    charter for the post-fix re-exercise.
    **Why it pays:** both fix rounds and the entire "max 2" budget were spent on
    comment and harness hygiene *before anything was exercised end to end*. The
    smoke fixes then landed as a `code-change` after the phase-9 full close-out,
    legitimately reopening the ship gate → librarian + both reviewers again →
    three of those dispatches died and one needed substituting. One cheap
    hands-tier execution pass at phase 7 collapses that entire tail.

14. **[high] The orchestrator is the only actor in the pipeline whose output is
    never checked at the time it is produced — and the kit already has the rule,
    applied to everyone else.** `code-reviewer.md` says *"Verify before you
    report. Open the file, check the claim. A finding you haven't verified is a
    guess."* There is no counterpart for the actor writing briefs, README prose
    and design-doc claims. Items 6 and 7 are symptoms; three further instances
    went unlogged: **(a)** a fabricated premise presented as prior intent — *"the
    parse loop **was supposed to** (`printf 'Unknown option: %s'`)"* — a string
    that existed nowhere, which the implementer had to refute; **(b)** three
    orchestrator-written README inaccuracies, two of them caught only at the
    ship gate, plus the `prediction incomplete` marker documented as stderr when
    it is stdout — the one string advertised as machine-readable; **(c)**
    **phase 9's "Show the user each review summary (verbatim findings, not your
    gloss)" was silently skipped on both passes** — narrative prose was
    presented instead, so the orchestrator's rendering was the only version in
    the room, and the mis-attributed size estimate survived a round longer than
    it needed to. **Proposed:** extend the verify-before-you-report rule to the
    orchestrator (a claim about code in a brief or a doc is quoted from an
    agent's report, or verified by reading the file that turn, or labelled
    `unverified` — and **never phrased as prior intent**); extend
    `implementer.md`'s escalation from design-doc ambiguity to **a false factual
    premise in the brief**, since hands tier cannot distinguish an
    orchestrator's verified claim from its guess and treats both as spec; and
    route code-derived reference tables the orchestrator writes (exit codes,
    flag lists, which stream a marker goes to) through the phase-8 librarian
    rather than discovering them at the ship gate.

15. **[medium] Phase 9 gives two contradictory rules for a re-review's diff base,
    and the run picked one silently.** *"The diff's base: the ledger's run base
    on the first pass, the last reviewed checkpoint on re-reviews"* versus the
    basis-invalidation rule's *"the re-review covers the same scope as the review
    that found the defect."* Both re-reviews recorded the run base, so every one
    re-pulled the whole diff. **Proposed:** default to the last reviewed
    checkpoint; escalate to the original scope only when the fix changed a
    *basis* other findings derived from; and require the ledger's `checkpoint`
    field to name which rule fired, so a deliberate full re-diff is
    distinguishable from an unexamined default.

16. **[medium] Resuming a completed reviewer to verify its own fixes worked, cost
    about one turn, and the skill never mentions it.** Every fresh re-review in
    this run cost 73–98 turns and 400–670 KB of transcript, and two died before
    doing any work; the resumed ship-gate reviewer came back in one turn having
    re-verified all three trap paths on two bash versions. Phase 9's *"Launch
    both as fresh subagents… that isolation is the point"* is right for a first
    pass and reads as governing re-reviews too. **Proposed:** name the resume
    path for the narrow case only — verifying that findings *the same agent
    authored* were applied as specified, where isolation isn't at risk because it
    is checking its own list. First passes, and any pass establishing `full`
    scope over an unseen tree, stay fresh dispatches. (Distinct from 12a, which
    is about narrowing a *fresh* dispatch after a stall.)

**The retrospective's own verdict on cost, quoted because it is the honest
summary of this run:** the plan gate, the ship-gate reviewers, the smoke test and
the librarian each caught something a normal session ships — a self-corruption
risk, a bash-3.2 trap regression, the exit-0 gate-contract bug, three README
errors. But *"two brain-tier reviewers × two passes, ~1000 subagent turns, to
churn comments — while all three behavioural defects sat unfound because nothing
had been executed outside the test harness. That contrast is the empirical case
for item 13: the expensive net was spent on the dimension the cheap net would
have covered, and the cheap net ran last."*

12a. **A tighter dispatch scope fixed the stalling librarian.** Its phase-8
    dispatch was open-ended and died on a watchdog; the phase-12 re-dispatch
    named three files, one section each, and explicitly blessed "no change" as a
    valid result — it finished in four minutes and found three real defects.
    Worth stating in the skill: when an agent stalls, narrow the read set before
    escalating the model.

## Open unknowns

1. **Does a real install into a OneDrive-*synced* target cause target-side byte
   drift that makes `cmp -s` report a difference the installer wouldn't act on?**
   Spike B's residual (its target was under `AppData\Local\Temp`, unsynced).
   Would need observation across an actual sync event. If it drifts, `--check`
   over-reports on synced targets — annoying, not corrupting.

Everything else load-bearing is closed with evidence: the three merge return
codes, the `python3` stub behavior, a quoted heredoc surviving a CRLF host
script, msys `grep -qxF` matching CRLF lines, kit tree sizes (12 + 10 + 1 files,
so per-file `cmp` is free), and every harness tool being present.

## Experiments

- **Spike A — verdict: TWO unpredictable lines, not one; 24 invocations, all
  exit 0.** Transcripts captured for four fixtures × two runs × two interpreter
  environments; regenerable by re-running the installer, so they are not pasted
  here.
  - **The settings line** (`MERGE`/`OK`/`WARN`) is unpredictable exactly when
    the seed branch fired earlier in the same run. F1 prediction **confirmed,
    and worse than expected**: a filesystem-reading dry run prints
    `WARN could not merge …` where the real run prints
    `OK … keys already current`, **and** leaks a `FileNotFoundError` traceback
    to stderr that the real run never emits. Proven by extracting the embedded
    merge program and running it both ways (rc=9 with the file, rc=1 without).
  - **`GITIGNORE added <pattern>` is the second unpredictable line** — not
    predicted. When the pre-run `.gitignore` lacks a trailing newline, an
    `echo >>` fuses onto the unterminated last line and breaks the *next*
    iteration's `grep -qxF`. Real run prints three lines where a
    filesystem-reading dry run predicts two.
  - **Pre-existing bug (new, finding B): the missing-trailing-newline case
    corrupts a line and takes two runs to converge.** `p1\np2` (no trailing
    newline) → run 1 fuses the appended pattern onto `p2`, permanently
    corrupting it; run 2 then re-adds two lines; run 3 is finally silent.
    Recommend fixing in scope: it destroys user data *and* fixing it removes
    the second unpredictable-line case, making `--check` simpler and honest.
  - **Finding C — my CRLF inference was wrong for this platform, and it makes
    one fixture unpinnable.** msys GNU grep 3.0 *does* match `grep -qxF` against
    CRLF lines, so fixture F2 emits **zero** `GITIGNORE` lines here and its
    `.gitignore` is untouched. On Linux GNU grep the `\r` is part of the line,
    `-x` fails, and the same fixture emits all three. **Pinning F2's transcript
    as expected output writes a test that fails on Linux** — so the CRLF
    fixture's gitignore expectations must be computed, not pinned.
  - **Finding D — the installer's output is blind to the skills/agents trees.**
    `COPY .claude/skills/ + .claude/agents/` is one unconditional line for both
    trees; F1 and F3 stdout are byte-identical despite F3 holding a stale
    `build-feature/` and an extra local skill. Good for prediction (no
    inspection needed) but **it conflicts with the per-tree counts chosen at the
    gate** — see the resolution the plan must carry, below.
  - Finding E confirms `install.sh <dir> --check` performs a real install today
    (output byte-identical with and without the flag), pinning pre-change
    behavior. Finding F: every path exits 0 today, including WARN, because the
    merge call sits in an `if` — so `set -euo pipefail` never propagates it.
  - Untested: `--link` mode, non-writable targets, `.claude` existing as a
    file, invalid JSON in `settings.json`.

**Design conflict to resolve at phase 5.** The chosen output shape annotates
action lines with per-tree counts, but the real run's action line carries no
counts — so strict "check output == real output minus `would `" cannot hold if
counts live *inside* the action line. Resolution the plan should adopt: action
lines stay byte-identical to the real run's (modulo the marker), and all
check-only enrichment — the mode header, per-tree count detail, `STALE` lines,
and the trailing summary — is emitted as clearly separable output (indented
detail lines and header/summary blocks) that the invariant test strips before
comparing. That keeps the counts you asked for *and* keeps the anti-drift test a
strict equality.
- **Spike B — verdict: byte-compare is sound for overwritten files, and must
  NOT be used for keep-if-exists files.** After a real install, `diff -rq` on
  `skills/` and `agents/` and `cmp -s` on `CLAUDE.md` (BOM) and `statusline.sh`
  all returned 0, and still did ~3.5 minutes later; sha256 unchanged, mode bits
  (755 vs 644) carried through `cp` correctly, no BOM/CRLF corruption
  (`core.autocrlf` never fires because the target isn't a git checkout).
  **But `settings.json` breaks the assumption by design**: the installer
  `KEEP`s an existing one and only merges kit-managed keys, so every real
  project legitimately diverges on permissions — a blanket `cmp -s` would
  report "would overwrite" on essentially every project while the installer's
  actual verdict is "leave it alone". Reproduced directly: added a
  project-specific key, re-ran the installer → `KEEP` (touched nothing), yet
  `cmp -s` on that file → exit 1. **Design consequence**: the byte-compare
  predicate applies only to files the installer *unconditionally overwrites*.
  For keep-if-exists files the check mirrors the installer's own conditional
  (missing → would create; exists → `KEEP`), with the merge prediction handled
  separately by the reused Python `changed` flag.
  *Residual risk, couldn't determine*: the spike's target lived under
  `AppData\Local\Temp`, which is not OneDrive-synced, so only the source side
  of the comparison was under sync. Target-side drift on a real install into
  another synced folder is untested; it would need observation across an actual
  sync event, not a few minutes of local idle.
- **Not dispatched**: whether a CRLF `.gitignore` breaks `grep -qxF` on GNU
  grep (needs a Linux box; recorded as a risk — if it does, Linux runs append
  duplicates and `--check` faithfully reports "would add" for a line already
  present). Whether `python3` works on other people's machines (a rollout
  question, not a build blocker — the fallback covers it either way).
