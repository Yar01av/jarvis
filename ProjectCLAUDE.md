# Project: Jarvis kit

This repo is the kit itself — the skills, agents, and settings that
`install.sh` deploys into other projects. **The `.claude/` tree here is the
product**, so editing it is normal work in this repo (the never-modify-
`.claude/` rule inside `/build-feature` applies to *runs of that skill*, not
to kit development).

## Commands

- No build, no test suite. The deliverables are Markdown instruction files
  and small shell scripts.
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
- There is deliberately no `docs/` tree here — `/sync-docs` output lives in
  target repos, not in the kit.

## Conventions

- Instruction prose is load-bearing: keep the existing voice (bold-led
  paragraphs, explicit "why" for every rule), and keep phase numbering
  stable in `build-feature` — the checklist numbers are a resume mechanism
  in the wild.
- Changes to skills/agents ripple to every installed project on the next
  `install.sh` run — prefer additive, conditional instructions over
  breaking renames.
