---
name: fix
description: Bug-fix workflow — reproduce first, root-cause, fix minimally, prove it with a regression test. Use for any bug report or failing behavior.
argument-hint: "<bug description, error message, or failing test>"
disable-model-invocation: true
---

Fix the following bug: $ARGUMENTS

Rules of engagement: **no fix before a reproduction.** A fix you can't watch go
from red to green is a guess.

## 1. Reproduce

- Turn the report into a runnable repro: a failing test if at all possible,
  otherwise a minimal command/script that shows the broken behavior.
- Capture the exact error output. If you cannot reproduce, stop and report
  what you tried and what information is missing.

## 2. Root-cause

- Trace from the failure point backward. For non-obvious cases, delegate to
  the `debugger` agent.
- State the root cause explicitly, with the evidence (code path, log line,
  commit). "Symptom patched" is not "bug fixed".

## 3. Fix

- Minimal change at the root cause. Resist fixing adjacent things you noticed
  — list them at the end instead.
- If the same root cause has siblings (copy-pasted logic elsewhere), search
  for them and report; fix only if trivially the same.

## 4. Prove

- The repro from step 1 now passes — show the output.
- The surrounding test suite still passes — show the output.
- Keep the repro as a permanent regression test, named after the behavior
  (not the ticket number).

Finish with: root cause (one sentence), the fix (files), proof (test output),
and anything related you noticed but didn't touch.
