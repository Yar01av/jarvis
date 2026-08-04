# Project: Jarvis kit

This repo is the kit itself — the skills, agents, and settings that
`install.sh` deploys into other projects. **The `.claude/` tree here is the
product**, so editing it is normal work in this repo (the never-modify-
`.claude/` rule inside `/build` applies to *runs of that skill*, not
to kit development).

## Commands

- No build step. The deliverables are Markdown instruction files and small
  shell scripts.
- Tests: `bash tests/check-mode.sh` — covers `install.sh`'s dry-run mode
  (no dependencies; fixtures are built under a scratch dir and the
  harness refuses to run against anything outside it). The Markdown
  instruction files have no test suite.
- Shell scripts (`install.sh`, `.claude/statusline.sh`, hooks): check with
  `shellcheck <file>` if available.
- Verify a skill loads after editing: malformed frontmatter fails *silently*
  — run `/skills` in a session or invoke the skill.

## Architecture

- `.claude/skills/<name>/SKILL.md` — slash commands; directory name = command
  name.
- `.claude/agents/<name>.md` — subagents; identity from `name:` frontmatter.
- `CLAUDE.md` — kit-managed, overwritten on install. `ProjectCLAUDE.md` (this
  file) — per-repo, seeded once.
- `docs/` here holds only hand-written material: `docs/designs/` (design and
  handoff docs) and `docs/solutions/` (captured lessons, with its own
  `INDEX.md`). There is deliberately **no `/sync-docs`-managed tree and no
  `docs/INDEX.md`** — that output belongs in target repos, not in the kit, so
  don't bootstrap one here.

## Conventions

- Instruction prose is load-bearing: keep the existing voice (bold-led
  paragraphs, explicit "why" for every rule), and keep phase numbering
  stable in `build` — the checklist numbers are a resume mechanism
  in the wild.
- Changes to skills/agents ripple to every installed project on the next
  `install.sh` run — prefer additive, conditional instructions over
  breaking renames.
