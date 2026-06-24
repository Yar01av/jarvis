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

# statusline.sh is kit-owned — always overwrite so updates propagate. The
# statusLine block in settings.json points at it; settings.json itself is only
# seeded on first install (see above), so existing projects must add the block
# manually to opt in.
cp "$SRC/.claude/statusline.sh" "$TARGET/.claude/statusline.sh"
chmod +x "$TARGET/.claude/statusline.sh"
echo "COPY  .claude/statusline.sh (kit-managed usage tracker)"

# Plugin keys (enabledPlugins / extraKnownMarketplaces) are kit-managed, but
# settings.json is only seeded when missing — so when it already exists we must
# merge the kit's plugin keys in. Idempotent: a no-op when seeding just copied
# them. Kit values win on conflict; project-only entries are preserved.
if python3 - "$SRC/.claude/settings.json" "$TARGET/.claude/settings.json" <<'PY'
import json, sys
src, tgt = json.load(open(sys.argv[1])), json.load(open(sys.argv[2]))
changed = False
for key in ("enabledPlugins", "extraKnownMarketplaces"):
    if key not in src:
        continue
    merged = {**tgt.get(key, {}), **src[key]}
    if merged != tgt.get(key):
        tgt[key] = merged
        changed = True
if changed:
    with open(sys.argv[2], "w") as f:
        json.dump(tgt, f, indent=2)
        f.write("\n")
sys.exit(0 if changed else 9)
PY
then
  echo "MERGE .claude/settings.json (plugin keys synced)"
else
  rc=$?
  [[ "$rc" == "9" ]] \
    && echo "OK    .claude/settings.json plugin keys already current" \
    || echo "WARN  could not merge plugin keys (python3 missing?) — add enabledPlugins + extraKnownMarketplaces from the kit manually" >&2
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

# Preflight: the bundled plugins ship MCP servers launched via `npx`, which
# needs node on the PATH Claude Code inherits (a GUI launch may not see a
# version-manager / Homebrew PATH). Warn early instead of a silent ENOENT.
if ! command -v npx >/dev/null 2>&1; then
  echo "WARN  npx not found — context7 plugin's MCP server will fail (ENOENT)." >&2
  echo "      Install Node, then ensure node/npx are on Claude Code's PATH" >&2
  echo "      (e.g. symlink into ~/.local/bin)." >&2
fi

echo "Done. Open the project and run /skills to verify everything loaded."
