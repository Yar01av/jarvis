# Jarvis — reusable Claude Code agent kit

Single source of truth for the Claude Code configuration I use across projects:
skills, subagents, settings, and a `CLAUDE.md` template that together define the
"main agent" for development work.

## What's inside

```
jarvis/
├── CLAUDE.md               # Kit-managed instructions (always overwritten on install)
├── ProjectCLAUDE.md.template  # Project-specific template → becomes ProjectCLAUDE.md in the target repo
├── install.sh              # Deploys this kit into a target project
└── .claude/
    ├── settings.json       # Baseline permissions + status line (safe defaults, stack-agnostic)
    ├── statusline.sh       # Usage tracker rendered in the status bar
    ├── agents/             # Subagents (delegated via the Agent tool)
    │   ├── code-reviewer.md
    │   ├── maintainability-reviewer.md
    │   ├── planner.md
    │   ├── researcher.md
    │   ├── experimenter.md
    │   ├── implementer.md
    │   ├── test-writer.md
    │   ├── debugger.md
    │   └── librarian.md    # owns code-derived docs (codebase map + feature docs)
    └── skills/             # Slash commands (/implement, /fix, /commit, ...)
        ├── build-feature/  # full pipeline: research → grill → plan/experiment → TDD → review → smoke test
        ├── implement/      # explore → plan → build → verify workflow
        ├── fix/            # repro-first bug fixing
        ├── commit/         # scoped commits + hygiene checks
        ├── handoff/        # session handoff doc + CLAUDE.md update
        ├── sync-docs/      # hierarchically indexed codebase docs in docs/
        ├── grill-me/       # stress-test a plan via relentless interview †
        ├── caveman/        # ultra-terse response mode †
        └── write-a-skill/  # meta: author new skills properly †
```

† from [mattpocock/skills](https://github.com/mattpocock/skills) (MIT);
`handoff` is a merge of ours and his.

## Usage

Deploy into a project:

```sh
./install.sh ~/path/to/project          # copies .claude/ + CLAUDE.md (default)
./install.sh ~/path/to/project --link   # symlinks .claude/ → edits here apply everywhere
```

- **Copy mode** (default): self-contained, safe to commit in the target repo,
  team members get it via git. Re-run `install.sh` to pull in updates.
- **Link mode**: one source of truth, instant propagation — but the symlink only
  works on your machine, so don't commit it in shared repos.

`CLAUDE.md` is kit-managed and always overwritten on re-install (same as
skills/agents), so workflow and skill updates propagate automatically. Put
project-specific context in `ProjectCLAUDE.md` — that file is only seeded from
the template on first install and never touched again.

## Status line (usage tracker)

`.claude/statusline.sh` renders a single-line usage gauge in the status bar,
wired up via the `statusLine` block in `.claude/settings.json`:

```
████░░░░░░ 42% ctx · 85.0k↑ 1.2k↓ · 5h 23% · 7d 41%
```

- **Context usage** — `context_window.used_percentage` as a 10-cell bar + %,
  colored green / yellow / red at the 60% / 85% thresholds.
- **Token counts** — total input (`↑`) / output (`↓`) for the session,
  humanized (`85.0k`, `1.5M`).
- **Rate limits** — 5-hour and 7-day `used_percentage`. These exist only on
  Claude.ai Pro/Max sessions and are omitted on API/Console sessions.

It reads the status-line JSON Claude Code pipes on stdin, runs locally, and
costs no API tokens. The numbers are client-side **estimates** (same as
`cost.total_cost_usd`) — fine for a live gauge, not for billing reconciliation.

Notes:
- The status line only re-reads settings on **restart** — relaunch Claude Code
  after install for it to appear.
- `install.sh` always copies `statusline.sh`, but `settings.json` is only
  seeded on **first** install. Fresh installs get the `statusLine` block
  automatically; existing projects keep their own `settings.json`, so add the
  block (see `.claude/settings.json` here) manually to opt in.
- The command uses `${CLAUDE_PROJECT_DIR}` so it resolves regardless of which
  subdirectory you're in. If the bar is blank or shows `statusline skipped`,
  the only hard dependency is `jq` on `PATH` (the script degrades gracefully if
  it's missing).
- Test standalone:
  ```sh
  echo '{"context_window":{"used_percentage":42.5,"total_input_tokens":85000,"total_output_tokens":1200}}' | .claude/statusline.sh
  ```

## Conventions

- **Skills** live in `.claude/skills/<name>/SKILL.md` — the *directory name* is
  the command name. Supporting files (scripts, references) can sit next to
  `SKILL.md`.
- **Agents** live in `.claude/agents/<name>.md` — identity comes from the
  `name:` frontmatter field, not the filename.
- **Local overrides** never go in this repo: use `.claude/settings.local.json`
  and `CLAUDE.local.md` in the target project (gitignored there).
- **Codebase docs** are generated *in the target repo* under `docs/`
  by `/sync-docs` (first run bootstraps, later runs update incrementally from
  the git diff since the last sync). They're meant to be committed there;
  nothing doc-related lives in this kit except the skill itself.
- Malformed frontmatter fails *silently* — a broken skill simply doesn't load.
  After editing, verify with `/skills` or by invoking the skill in a session.

## Adding content

1. New skill: `mkdir .claude/skills/<kebab-name>` + `SKILL.md` with at least a
   `description:` frontmatter field.
2. New agent: `.claude/agents/<name>.md` with `name:` + `description:`
   frontmatter; body is the system prompt. Keep `tools:` minimal.
3. Commit, then re-run `install.sh` in projects that should get the update.
