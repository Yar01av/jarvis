---
name: handoff
description: End-of-session handoff — write a handoff document a fresh agent can continue from, and update CLAUDE.md with anything durable learned about the project.
argument-hint: "[optional: what the next session will focus on]"
disable-model-invocation: true
---

<!-- Partly based on https://github.com/mattpocock/skills (MIT) -->

Wrap up the current session. If arguments were passed, treat them as a
description of what the next session will focus on and tailor the document
accordingly: $ARGUMENTS

## 1. State of the work

Summarize from the actual diff and conversation (check `git status` /
`git diff`, don't recall from memory):

- **Done & verified** — changes that have passing tests/checks behind them.
- **Done, unverified** — changes made but not proven to work. Be honest here.
- **In progress / not started** — with enough detail that a fresh session can
  continue without re-deriving it: file paths, the chosen approach, the next
  concrete step.
- **Known issues / deferred** — anything noticed but deliberately not touched.

Rules for the document:

- Don't duplicate content already captured in other artifacts (PRDs, plans,
  ADRs, issues, commits, diffs) — reference them by path or URL instead.
- Add a **Suggested skills** section: which skills/agents the next session
  should invoke (e.g. `/implement`, `/fix`, the `debugger` agent) and for what.
- Redact any sensitive information: API keys, credentials, tokens,
  personally identifiable data.

## 2. Update CLAUDE.md (only if warranted)

Review what this session revealed about the project that a future session
would otherwise have to rediscover: a non-obvious build/test command, a
convention that wasn't documented, a boundary that was almost violated.

- Add only durable, project-level facts — not session-specific state.
- Edit the existing CLAUDE.md sections; don't append a changelog.
- If nothing qualifies, say so and skip the edit. An accurate short CLAUDE.md
  beats a comprehensive stale one.

## 3. Output

Save the handoff document to the OS temporary directory (not the workspace,
so it never ends up in a commit), named `handoff-<project>-<topic>.md`, and
print the path. Then repeat the handoff as your final message, structured
with the headings from step 1. If work is incomplete, the "next concrete
step" line is the most important sentence — make it specific.
