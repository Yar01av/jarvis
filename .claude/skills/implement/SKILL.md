---
name: implement
description: Structured feature implementation — explore, plan, build, verify. Use for any non-trivial feature or change instead of diving straight into code.
argument-hint: "<what to build>"
disable-model-invocation: true
---

Implement the following: $ARGUMENTS

Work through these phases in order. Do not skip ahead to writing code.

## 1. Explore

- Find the code areas this touches and read them — including 1-2 examples of
  similar existing functionality (extend established patterns over inventing
  new ones).
- Note the test setup: framework, where tests live, how to run one file.

## 2. Plan

- Write a short plan: ordered steps with file paths, plus what could break.
- For changes touching 3+ files or with architectural impact, delegate to the
  `planner` agent instead and review its plan.
- If the request is ambiguous in a way that changes the design, ask before
  building — one question now beats a rebuild later.

## 3. Build

- Implement in the planned order, smallest verifiable increment first.
- Match surrounding code style exactly: naming, error handling, comment density.
- No drive-by refactors — note them, don't do them.

## 4. Verify

- Add or extend tests for the new behavior (delegate to `test-writer` for
  substantial coverage work).
- Run the relevant tests and the linter. Paste actual results — "should work"
  is not verification.
- Re-read the full diff (`git diff`) once, as a reviewer would, before
  declaring done.

Finish with a summary: what changed (files), how it's verified, anything
deferred.
