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
    ├── settings.json       # Baseline permissions + status line + worktree base (safe defaults)
    ├── statusline.py       # Usage tracker rendered in the status bar (Python, no jq)
    ├── statusline.sh       # Same gauge as a bash/jq script
    ├── hooks/              # Session hooks wired up via settings.json
    ├── agents/             # Subagents (delegated via the Agent tool)
    │   ├── code-reviewer.md
    │   ├── maintainability-reviewer.md
    │   ├── planner.md
    │   ├── researcher.md
    │   ├── experimenter.md
    │   ├── implementer.md
    │   ├── test-writer.md
    │   ├── debugger.md
    │   ├── kit-retrospective.md  # mines a finished build run for kit improvements
    │   └── librarian.md    # owns code-derived docs (codebase map + feature docs)
    └── skills/             # Slash commands (/implement, /fix, /commit, ...)
        ├── build/          # SKILL.md (run-wide rules) + phases.md (phase bodies): delivery pipeline for any deliverable: research → grill → plan/experiment → validate → build → review (TDD for code, its discipline generalised for docs/decks/data)
        ├── tree-build/     # PARKED design record — recursive /build; blocked: subagents can't spawn subagents
        ├── implement/      # explore → plan → build → verify workflow
        ├── fix/            # repro-first bug fixing + fail-on-revert proof
        ├── commit/         # scoped commits + hygiene checks
        ├── handoff/        # session handoff doc + CLAUDE.md update
        ├── sync-docs/      # hierarchically indexed codebase docs in docs/
        ├── refresh-solutions/ # curate the docs/solutions/ lessons store
        ├── explain-skill/  # meta: explain another skill's source in depth
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
./install.sh ~/path/to/project --check  # dry run: report what would change, write nothing
```

- **Copy mode** (default): self-contained, safe to commit in the target repo,
  team members get it via git. Re-run `install.sh` to pull in updates.
- **Link mode**: one source of truth, instant propagation — but the symlink only
  works on your machine, so don't commit it in shared repos.
- **Check mode** (`--check`, or `--dry-run` / `-n`): prints the same action lines
  a real run would, each prefixed `would `, plus per-tree counts and any stale
  top-level entries in `skills/`, `agents/` and `hooks/` — present in the target
  but not shipped by the kit (a deprecated kit file the kit no longer ships, or
  a project-local addition the kit never had), which a real run leaves in place
  (nothing is ever deleted). In `--link` mode, `skills/`/`agents/` aren't
  tree-scanned (they're symlinked wholesale, not compared file-by-file); `hooks/`
  — never symlinked — is always tree-scanned and stale-checked under `--check`,
  link or not. Exit codes make it usable as a gate:
  **0** nothing would change *and* the settings merge prediction succeeded,
  **2** changes pending *or* the merge prediction did not succeed,
  **1** usage error,
  **3** aborted mid-run (on a plain run the target may be partially written;
  under `--check` nothing was written) — so
  `./install.sh ~/proj --check || ./install.sh ~/proj` installs only when
  something would actually change (or when the prediction was incomplete —
  a plain run is the safe fallback there too). A prediction fails on invalid
  JSON in the target's `settings.json`, or when no working python is found —
  the latter fails every time, so `--check` always exits 2 on such a machine.
  Look for `— prediction incomplete` in the summary line on **stdout**; the
  cause is on stderr. Exit 0 must never claim knowledge it lacks.
  Stale target-only entries are
  reported but never counted as a change, so a stale-only target still exits
  0 and the gate is a no-op there. Under `--link`, a check normally reports
  pending work because every `ln -sfn` is reported as a change regardless of
  whether the symlink already points there — except when a target path
  (`.claude/skills` or `.claude/agents`) already exists and isn't a symlink:
  that path is skipped with a warning instead of linked. Since each of
  `skills`/`agents` is judged independently, the check only exits 0 when
  *both* land in that skipped case (both already real, non-symlink
  directories) and nothing else differs — one skipped path alongside an
  actual link action still reports pending work. The trailer then says to
  resolve the skipped paths first, then re-run, rather than promising a
  plain re-run will fix them on its own.

Unknown flags are rejected (exit 1).

`CLAUDE.md` is kit-managed and always overwritten on re-install (same as
skills/agents, `.claude/hooks/` and `statusline.py`/`.sh`), so workflow and skill
updates propagate automatically. Put
project-specific context in `ProjectCLAUDE.md` — that file is only seeded from
the template on first install and never touched again.

## Status line (usage tracker)

`.claude/statusline.py` (Python port; `statusline.sh` is the bash/jq original) renders a single-line usage gauge in the status bar,
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
- `install.sh` always copies `statusline.py` and `statusline.sh`, but `settings.json` is only
  seeded on **first** install. Fresh installs get the `statusLine` block
  automatically; existing projects keep their own `settings.json`, so add the
  block (see `.claude/settings.json` here) manually to opt in.
- The `worktree.baseRef: "head"` key (worktree-isolated agents branch from
  the session's HEAD instead of the default branch — `/build`'s
  experiment spikes rely on it) is **merged into existing settings on every
  install**, unlike `statusLine`; a project's own `worktree` values win.
  Manual add is only needed when the merge step warned (no working Python
  found — tried `python3`, `python`, `py -3`).
- The command uses `${CLAUDE_PROJECT_DIR}` so it resolves regardless of which
  subdirectory you're in. If the bar is blank or shows `statusline skipped`,
  the only hard dependency is `python` on `PATH` (`statusline.sh` needs `jq`
  instead; both degrade gracefully if it's missing).
- Test standalone:
  ```sh
  echo '{"context_window":{"used_percentage":42.5,"total_input_tokens":85000,"total_output_tokens":1200}}' | python .claude/statusline.py
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
