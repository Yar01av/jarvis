---
name: explain-skill
description: Read a skill's source and explain it in depth — its real control flow, hidden steps, gotchas, and side effects — well beyond what the one-line summary reveals. Use when the user runs /explain-skill, or asks to understand/break down/walk through how a specific skill works.
argument-hint: "<skill name to explain, e.g. build-feature>"
disable-model-invocation: true
---

Explain the skill named **$ARGUMENTS** in depth. Goal: let the user understand
it fast and reveal the details the summary alone hides. Output to chat only —
do **not** write a file.

## 1. Locate the source

Search these roots for `<name>/SKILL.md` (project first, it wins on conflict):

- `.claude/skills/<name>/SKILL.md` — this kit's own skills
- `~/.claude/skills/<name>/SKILL.md` — user skills
- `~/.claude/plugins/marketplaces/*/*/*/skills/<name>/SKILL.md` — plugin skills

```
find . ~/.claude -path "*skills/<name>/SKILL.md" 2>/dev/null
```

- **Multiple matches** → list them, explain the project one, note the others exist.
- **No match on disk** → it's almost certainly a **built-in** (deep-research,
  verify, run, code-review, init, schedule, loop, …), bundled inside the
  `claude` binary and not readable from disk. Say so plainly. Offer to explain
  it from its loaded description + your general knowledge, and **label that
  output clearly as "not read from source — may be incomplete."**

## 2. Read everything

Read `SKILL.md` in full, then every bundled file it references or ships
alongside (`REFERENCE.md`, `EXAMPLES.md`, `scripts/*`, prompt templates,
any sub-docs). Don't explain from the frontmatter description — that's the
summary you're trying to go beyond.

## 3. Analyze — surface what the summary hides

Pull out, specifically:

- **Frontmatter mechanics**: `allowed-tools` (what it's restricted to),
  `disable-model-invocation` (manual-only vs auto-trigger), `argument-hint`,
  `model`. Explain what each implies for behavior.
- **Real control flow**: phases/steps in order, branches, loops, early-exits,
  and the conditions that gate them.
- **Subagents it spawns** and **other skills it calls** — the fan-out the
  summary never mentions.
- **Side effects**: files written/deleted, commits, network calls, anything
  irreversible or outward-facing.
- **Gotchas & traps**: ordering constraints, "must do X before Y", silent
  caps, places it stops and asks the user.

If the source contradicts itself or a referenced file is missing, **say so** —
that's a finding, not a detour.

## 4. Diagram in ASCII (terminal-native)

Draw the control flow as an ASCII diagram — boxes + arrows render directly in
the terminal, no renderer needed. Do **not** use mermaid (shows as raw code
here). Keep it tight; one flow diagram is usually enough. Add a second
(e.g. an agent fan-out tree) only when the flow alone doesn't capture it.

```
 invoke ──▶ locate ──▶ found? ──no──▶ built-in? report + offer
                          │yes
                          ▼
                     read source ──▶ analyze ──▶ explain
```

## 5. Output structure

**Carry the explanation in diagrams and tables. Prose to the bare minimum** —
no narration, no recap, no transitions. If a point fits a table row or a
diagram label, it goes there, not in a sentence. The user asks when they want
more on something; don't pre-explain.

1. **TL;DR** — 1 line: what it does + the one thing the summary omits.
2. **Flow diagram** (ASCII). Add a second (e.g. agent fan-out) only if needed.
3. **Hidden details** — a short table (detail | why it matters), not prose.
4. **Step-by-step** — a table (phase | who | what it touches), one row each.
5. **Resources & scripts** — one line, or "none bundled."
6. **Gotchas** — bullets, one line each.
7. **When to use / when not** — bullets.

Close with a one-line offer to drill into any part. Skip any section that
would be empty. Match the user's caveman mode if active.
