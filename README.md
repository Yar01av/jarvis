# Jarvis — reusable Claude Code agent kit

Single source of truth for the Claude Code configuration I use across projects:
skills, subagents, settings, and a `CLAUDE.md` template that together define the
"main agent" for development work.

## What's inside

```
jarvis/
├── CLAUDE.md.template      # Project-instructions template → becomes CLAUDE.md in the target repo
├── install.sh              # Deploys this kit into a target project
└── .claude/
    ├── settings.json       # Baseline permissions (safe defaults, stack-agnostic)
    ├── agents/             # Subagents (delegated via the Agent tool)
    │   ├── code-reviewer.md
    │   ├── planner.md
    │   ├── test-writer.md
    │   └── debugger.md
    └── skills/             # Slash commands (/implement, /fix, /commit, ...)
        ├── implement/      # explore → plan → build → verify workflow
        ├── fix/            # repro-first bug fixing
        ├── commit/         # scoped commits + hygiene checks
        ├── handoff/        # session handoff doc + CLAUDE.md update
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

The script never overwrites an existing `CLAUDE.md`; it copies the template to
`CLAUDE.md` only if none exists. Per-skill/agent files are overwritten on
re-install (that's the point — updates propagate).

## Conventions

- **Skills** live in `.claude/skills/<name>/SKILL.md` — the *directory name* is
  the command name. Supporting files (scripts, references) can sit next to
  `SKILL.md`.
- **Agents** live in `.claude/agents/<name>.md` — identity comes from the
  `name:` frontmatter field, not the filename.
- **Local overrides** never go in this repo: use `.claude/settings.local.json`
  and `CLAUDE.local.md` in the target project (gitignored there).
- Malformed frontmatter fails *silently* — a broken skill simply doesn't load.
  After editing, verify with `/skills` or by invoking the skill in a session.

## Adding content

1. New skill: `mkdir .claude/skills/<kebab-name>` + `SKILL.md` with at least a
   `description:` frontmatter field.
2. New agent: `.claude/agents/<name>.md` with `name:` + `description:`
   frontmatter; body is the system prompt. Keep `tools:` minimal.
3. Commit, then re-run `install.sh` in projects that should get the update.
