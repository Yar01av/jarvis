#!/usr/bin/env bash
# Deploy the jarvis Claude Code kit into a target project.
#
# Usage:
#   ./install.sh <target-project-dir> [--link]
#
#   default : copy .claude/ contents into <target>/.claude/ (existing local
#             files are preserved; kit files are overwritten so updates propagate)
#   --link  : symlink <target>/.claude/skills + agents back to this repo
#             (single source of truth; machine-local only — don't commit symlinks)
#
# CLAUDE.md.template is copied to <target>/CLAUDE.md only if none exists.

set -euo pipefail

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET="${1:-}"
MODE="${2:-copy}"

if [[ -z "$TARGET" || ! -d "$TARGET" ]]; then
  echo "Usage: $0 <target-project-dir> [--link]" >&2
  exit 1
fi
TARGET="$(cd "$TARGET" && pwd)"

if [[ "$TARGET" == "$SRC" ]]; then
  echo "Refusing to install into the kit repo itself." >&2
  exit 1
fi

mkdir -p "$TARGET/.claude"

if [[ "$MODE" == "--link" ]]; then
  for dir in skills agents; do
    if [[ -e "$TARGET/.claude/$dir" && ! -L "$TARGET/.claude/$dir" ]]; then
      echo "SKIP  .claude/$dir exists and is not a symlink — resolve manually." >&2
    else
      ln -sfn "$SRC/.claude/$dir" "$TARGET/.claude/$dir"
      echo "LINK  .claude/$dir -> $SRC/.claude/$dir"
    fi
  done
  # settings.json is always copied: projects diverge on permissions.
  if [[ ! -f "$TARGET/.claude/settings.json" ]]; then
    cp "$SRC/.claude/settings.json" "$TARGET/.claude/settings.json"
    echo "COPY  .claude/settings.json (baseline — adjust per project)"
  fi
else
  cp -R "$SRC/.claude/skills" "$TARGET/.claude/"
  cp -R "$SRC/.claude/agents" "$TARGET/.claude/"
  echo "COPY  .claude/skills/ + .claude/agents/"
  if [[ ! -f "$TARGET/.claude/settings.json" ]]; then
    cp "$SRC/.claude/settings.json" "$TARGET/.claude/settings.json"
    echo "COPY  .claude/settings.json (baseline — adjust per project)"
  else
    echo "KEEP  .claude/settings.json (already exists)"
  fi
fi

# CLAUDE.md is kit-owned — always overwrite so workflow/skill updates propagate.
cp "$SRC/CLAUDE.md" "$TARGET/CLAUDE.md"
echo "COPY  CLAUDE.md (kit-managed — do not edit; put project context in ProjectCLAUDE.md)"

# ProjectCLAUDE.md is project-owned — only seed it from the template if missing.
if [[ ! -f "$TARGET/ProjectCLAUDE.md" ]]; then
  cp "$SRC/ProjectCLAUDE.md.template" "$TARGET/ProjectCLAUDE.md"
  echo "COPY  ProjectCLAUDE.md (from template — fill in the project-specific sections)"
else
  echo "KEEP  ProjectCLAUDE.md (already exists)"
fi

# Make sure local-only files stay out of the target's git history.
GI="$TARGET/.gitignore"
for pattern in ".claude/settings.local.json" "CLAUDE.local.md"; do
  if [[ ! -f "$GI" ]] || ! grep -qxF "$pattern" "$GI"; then
    echo "$pattern" >> "$GI"
    echo "GITIGNORE  added $pattern"
  fi
done

echo "Done. Open the project and run /skills to verify everything loaded."
