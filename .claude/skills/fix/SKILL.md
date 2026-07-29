---
name: fix
description: Bug-fix workflow — size it, reproduce first, root-cause, fix minimally, prove it with a fail-on-revert regression test, close out docs. Use for any bug report or failing behavior.
argument-hint: "<bug description, error message, or failing test>"
disable-model-invocation: true
---

Fix the following bug: $ARGUMENTS

Rules of engagement: **no fix before a reproduction.** A fix you can't watch go
from red to green is a guess.

**Size it first.** Before anything else, name the likely route out loud:
**revert** (a recent commit introduced it), **one-liner** (obvious minimal
change), or **systemic** (crosses modules or hides a design flaw). Ceremony
scales with the route — a one-liner skips the heavy machinery below — but
**investigation (steps 1–2) and proof (step 4) never scale down.** A revert
is a *mitigation*, not a fix: with the user's OK it may land first to stop
the bleeding (that OK **is** the step-2 gate, taken early), but steps 1–2
still run before anything is called fixed.

## 1. Reproduce

- Turn the report into a runnable repro: a failing test if at all possible,
  otherwise a minimal command/script that shows the broken behavior.
- If a stop-the-bleeding revert already landed, the bug no longer reproduces
  on the current tree — re-expose it (`git revert --no-commit <the-revert>`
  on a clean tree, or run the repro at the offending commit), capture the
  red, then discard the re-exposure before proceeding.
- Capture the exact error output. If you cannot reproduce, stop and report
  what you tried and what information is missing.

## 2. Root-cause

- Trace from the failure point backward. For non-obvious cases, delegate to
  the `debugger` agent.
- **Find the working analogue first**: when another code path does the same
  job correctly, diff the broken path against it before theorizing — the
  difference list usually contains the cause.
- State the root cause explicitly, with the evidence (code path, log line,
  commit). "Symptom patched" is not "bug fixed".
- **Gate (conditional):** if the chosen route is **revert** (destructive) or
  **systemic** (scope the user owns), state the root cause and the intended
  change and get the user's OK before any edit lands. A stop-the-bleeding
  revert takes this gate *before it lands* (per the sizing note); the
  post-diagnosis gate then covers the real fix. An obvious minimal fix needs
  no stop — the skill runs inline, the user is already watching.

## 3. Fix

- Minimal change at the root cause. Resist fixing adjacent things you noticed
  — list them at the end instead.
- The diagnosis is the judgment; once the root cause and the minimal change are
  clear, the edit is mechanical — **delegate it to a `sonnet` `implementer`
  subagent** (hands tier — CLAUDE.md → Model tiering), handing it the root
  cause, the exact change, and the failing repro it must turn green. A one-line
  fix isn't worth the hop; make it inline.
- **Counted escalation — this precedence is the loop bound, keep the count:**
  1. A dispatch that fails to go green → re-dispatch that fix **one rung up**
     the ladder (sonnet → opus → fable). A post-re-diagnosis attempt
     re-enters at the rung the last attempt used.
  2. A **second** failed attempt, *or* a fix that balloons past the root cause
     → the diagnosis was incomplete. Back to step 2 for re-diagnosis; do not
     escalate further. A bigger model on a wrong root cause is waste.
  3. A **third** failure → stop. Hand the user the hypothesis log: what was
     tried, what was ruled out, and where the evidence points. This is the one
     hard, unconditional halt in the skill. Attempts count across
     re-diagnoses and never reset — the third failure *overall* halts,
     whichever rule sent you back.
- If the same root cause has siblings (copy-pasted logic elsewhere), search
  for them and report; fix only if trivially the same.

## 4. Prove

Fail-on-revert, not just green: a regression test that never watched the bug
come back proves nothing.

- The repro from step 1 now passes — show the output.
- **Revert the fix — scoped to the fix's paths (`git stash push -u -- <fix
  files>`; `-u` so a newly added file stashes too), so the repro test stays
  on disk — and run the repro test alone: it must go red again with an
  assertion failure.** A collection or import error is not red; it means the
  revert took the test with it or broke the harness. Re-apply
  (`git stash pop`), run it — green. Only the repro test runs in this cycle,
  not the suite; the revert check exists to prove the test actually
  exercises the bug. **Revert route:** the "fix" is a commit, so the stash
  recipe doesn't apply — re-expose the bug instead (`git revert --no-commit
  <the-revert>` on a clean tree), watch the repro go red, discard the
  re-exposure, watch it pass.
- The surrounding test suite still passes — show the output.
- Keep the repro as a permanent regression test, named after the behavior
  (not the ticket number).

## 5. Close out (conditional)

- **Docs:** if the fix changed behavior or structure that `docs/` documents,
  run `/sync-docs` now (this is CLAUDE.md → Documentation's own rule; a fix
  is not done while the docs lie). A fix that touched no documented behavior
  skips this.
- **Durable lesson:** only when the run surfaced a genuinely reusable lesson —
  a non-obvious cause, a gotcha, a dead-end worth not repeating — write
  `docs/solutions/<category>/<slug>.md` and append its one-line pointer to
  `docs/solutions/INDEX.md`. Format and index rules live in `/build-feature`
  phase 8 (the canonical statement — in particular, never wire the store into
  the sync-managed root `docs/INDEX.md`). A routine fix writes nothing — the
  store must stay signal-dense.
- **Review (systemic route only):** dispatch `code-reviewer` on the diff
  before finishing; show its findings verbatim. One-liners and reverts skip
  this.

Finish with: root cause (one sentence), the route taken, the fix (files),
proof (repro red→green→revert-red→green + suite output), close-out actions
taken or skipped and why, and anything related you noticed but didn't touch.
