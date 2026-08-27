#!/usr/bin/env bash
# Deploy the jarvis Claude Code kit into a target project.
#
# Usage:
#   ./install.sh <target-project-dir> [--link] [--check|--dry-run|-n]
#
#   default : copy .claude/ contents into <target>/.claude/ (existing local
#             files are preserved; kit files are overwritten so updates propagate)
#   --link  : symlink <target>/.claude/skills + agents back to this repo
#             (single source of truth; machine-local only — don't commit symlinks)
#   --check : report exactly what a real run would do and write nothing.
#             Aliases: --dry-run, -n. Composes with --link (`--link --check`).
#
# Exit codes:
#   0  --check: nothing would change, AND the merge prediction succeeded ·
#      plain run: completed
#   2  --check only: changes are pending, OR the merge prediction did not
#      succeed — look for "— prediction incomplete" in the summary line on
#      STDOUT; the cause (bad JSON in the target's settings.json, or no
#      working python) is on stderr. Exit 0 must never claim knowledge it
#      lacks; a plain run is the safe fallback (it attempts the merge and
#      warns again). Note a machine with no working python fails the
#      prediction every time, so --check there always exits 2.
#      Why a failed prediction is 2 and not 3: settings_merge is invoked as
#      `… || rc=$?`, and a command on the left of || is exempt from the ERR
#      trap — so its failure is captured as data, not an abort. Keep that
#      wrapper: dropping it makes a bad settings.json abort the whole run.
#   1  usage error (unknown flag, missing/non-directory target, a second
#      positional argument, or target == this kit repo) — always writes nothing
#   3  aborted mid-run after a command failed under `set -e` — on a plain run
#      the target may be partially written; under --check nothing was
#      written (the abort was in check-only bookkeeping, e.g. a broken
#      TMPDIR); re-run once the underlying cause is fixed (every step here is
#      safe to repeat, so idempotence is required of every step, present and
#      future)
#
# CLAUDE.md is kit-managed and always overwritten on install; ProjectCLAUDE.md
# is seeded from ProjectCLAUDE.md.template only if missing. .claude/hooks/ is
# installed and made executable alongside skills/agents. settings.json is
# seeded only when missing; kit-managed keys (enabledPlugins,
# extraKnownMarketplaces, worktree) are merged in either way. Under --check,
# target-only ("stale") top-level entries are reported as informational notes
# — never deleted — for skills/agents/hooks in copy mode, but under --link
# only hooks/ is scanned (link mode replaces the other two wholesale, so
# per-entry counts there would be meaningless).

set -Eeuo pipefail

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ---------------------------------------------------------------------------
# Globals
# ---------------------------------------------------------------------------
CHECK=false
LINK=false
WOULD=0
SAME=0
WARNINGS=0
HAD_SKIP=false
HAVE_PY=false
PY=()
TS_CHANGED=0
MERGE_TGT=""
# MERGE_TMP is a SEPARATE variable from MERGE_TGT: MERGE_TGT also points at
# the target's REAL settings.json on the keep-if-exists path and on every
# apply run, so a trap that removed whatever MERGE_TGT holds would delete a
# real project's settings.json on exit. MERGE_TMP holds only the mktemp path,
# and only when the check+seed branch created one.
MERGE_TMP=""
trap '[[ -n "$MERGE_TMP" ]] && rm -f "$MERGE_TMP"' EXIT
# Requires `set -E` (errtrace) above: without it, an ERR trap set here never
# fires for a failure inside a function (run(), copy_kit_file(), ...) — and
# nearly every mutation in this script happens through one. Does not fire on
# the deliberate exit 1 / exit 2 paths (those are `exit`, not a failure) and
# coexists with the EXIT trap above (this one calls `exit 3`, which then runs
# the EXIT trap for MERGE_TMP cleanup before the process actually exits).
# The BASHPID guard restores pre-`-E` subshell behaviour: `-E` also hands this
# trap to command-substitution and process-substitution subshells (the
# check-only `MERGE_TMP="$(mktemp)"` seed-prediction copy; tree_scan's
# `< <(find ...)`), where `exit 3` only kills that subshell, not the script —
# so without the guard the message prints once per subshell PLUS once more in
# the parent when the failure propagates, and in tree_scan's case it prints at
# all despite the run then completing successfully. $BASHPID (this process)
# vs $$ (the script's original PID, fixed at start) tells the two apart; a
# subshell re-raises its own exit code and says nothing. The message text
# itself is mode-aware: $CHECK is a global set before this trap is installed,
# so it already reflects argument parsing by the time any real mutation can
# fail. Use `_err_rc`, not `rc` — `rc` is a live global read by the summary.
# ${BASHPID:-$$}, not $BASHPID: BASHPID is bash 4.0+, and on bash 3.2 (stock
# /bin/bash on macOS) `set -u` would make this trap body itself fatal — exiting
# 1 after a partial write, i.e. exactly the bug the trap exists to prevent. The
# fallback degrades to "always the parent": message and exit 3 stay correct,
# only the subshell suppression is lost.
trap '_err_rc=$?; [[ ${BASHPID:-$$} != $$ ]] && exit "$_err_rc"
      if [[ $CHECK == true ]]; then echo "ABORTED — nothing was written" >&2
      else echo "ABORTED — target may be partially written" >&2; fi
      exit 3' ERR

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# run <argv...>: the single mutation gate. No mutation ever runs while $CHECK
# is true. The `$# == 0` guard is `set -u` hygiene for bash <= 4.3 (a known
# nounset bug on an empty "$@" expansion, fixed in 4.4) — this script doesn't
# assume a bash version, so the guard stays even though it's a no-op here.
run() {
  (($# == 0)) && return 0
  [[ $CHECK == true ]] && return 0
  "$@"
}

# emit <is_change 0|1> <line>: the ONLY place an action line is ever printed.
# is_change controls the WOULD/SAME tally; the "would " prefix is controlled
# solely by $CHECK — so check-mode text equals apply-mode text on a
# successful run (not proof a mutation succeeded on THIS run — see act()).
emit() {
  if (($1)); then
    WOULD=$((WOULD + 1))
  else
    SAME=$((SAME + 1))
  fi
  if [[ $CHECK == true ]]; then
    printf 'would %s\n' "$2"
  else
    printf '%s\n' "$2"
  fi
}

# act <line> <argv...>: report-and-gate together, so a label can never drift
# from the mutation it was written for. It is NOT proof that mutation
# succeeded: emit fires before run, so an aborted apply run can print an
# action line for a command that then failed.
act() {
  local line="$1"
  shift
  emit 1 "$line"
  run "$@"
}

# same <line>: report KEEP/OK/identical — never a mutation.
same() {
  emit 0 "$1"
}

# note <text>: check-only enrichment line. Explicit `return 0` — without it,
# the function's own last command is the `[[ ]] && printf` test, which is
# false (and thus returns 1) in apply mode; a bare `note "..."` call would
# then trip `set -e` on every real install.
note() {
  [[ $CHECK == true ]] && printf '# %s\n' "$1"
  return 0
}

# warn <line...>: each argument becomes its own stderr line; one WARNINGS
# tick per call, regardless of how many lines it prints.
warn() {
  WARNINGS=$((WARNINGS + 1))
  printf '%s\n' "$@" >&2
}

# gi_append <gitignore-file> <pattern>: terminates an unterminated last line
# first (Spike A finding B), so an append can never fuse onto the previous
# line.
gi_append() {
  local gi="$1" pattern="$2"
  if [[ -s "$gi" ]] && [[ -n "$(tail -c1 "$gi")" ]]; then
    printf '\n' >>"$gi"
  fi
  printf '%s\n' "$pattern" >>"$gi"
}

# resolve_python: probes python3 -> python -> py -3 by EXECUTING each (the
# Microsoft Store stub resolves fine on PATH but exits 49 when actually run).
# The probe asserts Python >= 3.5, not just "runs" — settings_merge's heredoc
# uses `{**a, **b}` dict-merge syntax, so a Python 2 `python` must fall
# through to the next candidate rather than be accepted here.
# Sets HAVE_PY + PY (an argv array, so `py -3` survives as two tokens).
# Called bare at statement level, under the ERR trap: no explicit `return 0`
# needed — the loop's last-executed command is always the `if`/`fi` itself,
# and a false test with no `else` (nothing found) exits 0 same as a
# successful `break` (found) does, so the function's own status is always 0.
resolve_python() {
  local candidates=("python3" "python" "py -3") cand parts
  HAVE_PY=false
  PY=()
  for cand in "${candidates[@]}"; do
    read -ra parts <<<"$cand"
    if "${parts[@]}" -c "import sys; sys.exit(0 if sys.version_info >= (3, 5) else 1)" >/dev/null 2>&1; then
      PY=("${parts[@]}")
      HAVE_PY=true
      break
    fi
  done
}

# settings_merge <src-settings> <tgt-settings> <check|apply>: THE single call
# site for the embedded merge program (a heredoc is stdin, so a second call
# site would mean a second copy — exactly the drift this feature exists to
# prevent). mode gates only the write; the exit code (0 changed / 9 unchanged
# / other error) is identical in both modes.
settings_merge() {
  local src="$1" tgt="$2" mode="$3"
  "${PY[@]}" - "$src" "$tgt" "$mode" <<'PY'
import json, sys
src, tgt = json.load(open(sys.argv[1])), json.load(open(sys.argv[2]))
mode = sys.argv[3]
changed = False
for key, kit_wins in (("enabledPlugins", True), ("extraKnownMarketplaces", True), ("worktree", False)):
    if key not in src:
        continue
    if kit_wins:
        merged = {**tgt.get(key, {}), **src[key]}
    else:
        merged = {**src[key], **tgt.get(key, {})}
    if merged != tgt.get(key):
        tgt[key] = merged
        changed = True
if changed and mode == "apply":
    with open(sys.argv[2], "w") as f:
        json.dump(tgt, f, indent=2)
        f.write("\n")
sys.exit(0 if changed else 9)
PY
}

# tree_scan <src-dir> <tgt-dir> <label>: check-only, never called in apply
# mode — the one deliberate exception to "predicates run in both modes"
# (feeds no decision, the tree COPY line is unconditional; only enrichment).
# find -print0 + per-file cmp -s (not `diff -rq` — a source-only directory
# reports as one `Only in` line regardless of file count, which can't feed a
# per-file tally) to compute would-overwrite / would-add / identical counts,
# plus one STALE note per stale TOP-LEVEL target entry (never recursive — the
# STALE note is about whole entries the kit no longer ships, not individual
# files inside them).
# Sets TS_CHANGED (1 if overwrite>0 or add>0, else 0) for the caller's emit().
tree_scan() {
  local src="$1" tgt="$2" label="$3"
  local overwrite=0 add=0 identical=0 stale=0
  local rsrc rel f entry name
  if [[ -d "$src" ]]; then
    rsrc="$(cd "$src" && pwd)"
    while IFS= read -r -d '' f; do
      rel="${f#"$rsrc"/}"
      if [[ -f "$tgt/$rel" ]]; then
        if cmp -s "$f" "$tgt/$rel"; then
          identical=$((identical + 1))
        else
          overwrite=$((overwrite + 1))
        fi
      else
        add=$((add + 1))
      fi
    done < <(find "$rsrc" -type f -print0)
  fi
  if [[ -d "$tgt" ]]; then
    while IFS= read -r -d '' entry; do
      name="$(basename "$entry")"
      if [[ ! -e "$src/$name" ]]; then
        stale=$((stale + 1))
        note "  STALE .claude/$label/$name"
      fi
    done < <(find "$tgt" -mindepth 1 -maxdepth 1 -print0)
  fi
  note "  $label: $overwrite would overwrite · $add would add · $identical identical · $stale stale"
  # No explicit `return 0` needed, called bare under the ERR trap as this is:
  # the `if`/`else` always has both arms, and a plain assignment always
  # exits 0, so whichever arm runs, the function's own status is always 0.
  if ((overwrite > 0 || add > 0)); then
    TS_CHANGED=1
  else
    TS_CHANGED=0
  fi
}

# copy_kit_file <src> <tgt> <line>: unconditional-overwrite single file.
# cmp -s decides same|act (identical content -> SAME, even though the label
# always reads "COPY" — "change" means content, not mtime); the identical-
# content branch never calls cp at all.
copy_kit_file() {
  local src="$1" tgt="$2" line="$3"
  if [[ -f "$tgt" ]] && cmp -s "$src" "$tgt"; then
    same "$line"
  else
    act "$line" cp "$src" "$tgt"
  fi
}

# plan_settings_seed <report_keep true|false>: settings.json is keep-if-
# exists, not unconditional-overwrite (Spike B — a blanket cmp would over-
# report on every project that has legitimately customized permissions), so
# it gets its own helper, shared by both the --link and copy branches so
# MERGE_TGT can't be forgotten in one. report_keep preserves an existing
# asymmetry in this script: the copy branch prints a KEEP line when the file
# already exists, --link stays silent in that case.
plan_settings_seed() {
  local report_keep="$1"
  if [[ -f "$TARGET/.claude/settings.json" ]]; then
    MERGE_TGT="$TARGET/.claude/settings.json"
    if [[ "$report_keep" == true ]]; then
      same "KEEP  .claude/settings.json (already exists)"
    fi
  else
    act "COPY  .claude/settings.json (baseline — adjust per project)" \
      cp "$SRC/.claude/settings.json" "$TARGET/.claude/settings.json"
    if [[ $CHECK == true ]]; then
      # Predict against a throwaway mktemp copy of the kit's own
      # settings.json — never point MERGE_TGT at a path inside the kit or
      # the target.
      MERGE_TMP="$(mktemp)"
      cp "$SRC/.claude/settings.json" "$MERGE_TMP"
      MERGE_TGT="$MERGE_TMP"
      note "  predicted against the baseline settings.json this run would seed"
    else
      MERGE_TGT="$TARGET/.claude/settings.json"
    fi
  fi
}

usage() {
  echo "Usage: $0 <target-project-dir> [--link] [--check|--dry-run|-n]" >&2
}

# ---------------------------------------------------------------------------
# Argument parsing — strict: unknown flags and a second positional both exit
# 1 before any write. Predicate only; identical in both modes.
# ---------------------------------------------------------------------------
TARGET=""
while (($#)); do
  case "$1" in
  --link)
    LINK=true
    ;;
  --check | --dry-run | -n)
    CHECK=true
    ;;
  -*)
    printf 'Unknown option: %s\n' "$1" >&2
    usage
    exit 1
    ;;
  *)
    if [[ -n "$TARGET" ]]; then
      usage
      exit 1
    fi
    TARGET="$1"
    ;;
  esac
  shift
done

if [[ -z "$TARGET" || ! -d "$TARGET" ]]; then
  usage
  exit 1
fi
TARGET="$(cd "$TARGET" && pwd)"

if [[ "$TARGET" == "$SRC" ]]; then
  echo "Refusing to install into the kit repo itself." >&2
  exit 1
fi

resolve_python

# From here down is the mutation sequence: an exit-3 abort can leave any
# prefix of these steps applied. That's only survivable because every step
# is idempotent — re-running after the underlying cause is fixed converges
# rather than double-applies. Holds today by construction (`cp`/`mkdir -p`/
# `chmod` overwrite-or-create, the merge is keyed on `changed`, `gi_append`
# checks before appending); a future step joining this sequence must keep it.
note "CHECK mode — nothing will be written · target: $TARGET"

run mkdir -p "$TARGET/.claude"

if [[ $LINK == true ]]; then
  for dir in skills agents; do
    if [[ -e "$TARGET/.claude/$dir" && ! -L "$TARGET/.claude/$dir" ]]; then
      HAD_SKIP=true
      warn "SKIP  .claude/$dir exists and is not a symlink — resolve manually."
    else
      act "LINK  .claude/$dir -> $SRC/.claude/$dir" \
        ln -sfn "$SRC/.claude/$dir" "$TARGET/.claude/$dir"
    fi
  done
  # settings.json is keep-if-exists here too, never symlinked: projects
  # diverge on permissions, so only a missing file gets the baseline copy.
  plan_settings_seed false
else
  if [[ $CHECK == true ]]; then
    tree_scan "$SRC/.claude/skills" "$TARGET/.claude/skills" "skills"
    skills_changed=$TS_CHANGED
    tree_scan "$SRC/.claude/agents" "$TARGET/.claude/agents" "agents"
    agents_changed=$TS_CHANGED
    if ((skills_changed == 1 || agents_changed == 1)); then
      trees_changed=1
    else
      trees_changed=0
    fi
    emit "$trees_changed" "COPY  .claude/skills/ + .claude/agents/"
  else
    emit 1 "COPY  .claude/skills/ + .claude/agents/"
  fi
  run cp -R "$SRC/.claude/skills" "$TARGET/.claude/"
  run cp -R "$SRC/.claude/agents" "$TARGET/.claude/"
  plan_settings_seed true
fi

# statusline.sh/.py are kit-owned — always overwrite so updates propagate. The
# statusLine block in settings.json points at it; settings.json itself is only
# seeded on first install (see above), so existing projects must add the block
# manually to opt in.
copy_kit_file "$SRC/.claude/statusline.sh" "$TARGET/.claude/statusline.sh" \
  "COPY  .claude/statusline.sh (kit-managed usage tracker)"
run chmod +x "$TARGET/.claude/statusline.sh"
# statusline.py is the jq-free Python port the baseline settings.json points at
# (statusline.sh stays for jq-only setups).
copy_kit_file "$SRC/.claude/statusline.py" "$TARGET/.claude/statusline.py" \
  "COPY  .claude/statusline.py (kit-managed usage tracker, Python port)"

# .claude/hooks/ is kit-owned, same always-overwrite shape as skills/agents —
# the baseline settings.json wires a SessionStart hook to it.
if [[ $CHECK == true ]]; then
  tree_scan "$SRC/.claude/hooks" "$TARGET/.claude/hooks" "hooks"
  hooks_changed=$TS_CHANGED
else
  hooks_changed=1
fi
emit "$hooks_changed" "COPY  .claude/hooks/ (session hooks wired via the kit baseline)"
run cp -R "$SRC/.claude/hooks" "$TARGET/.claude/"
# chmod only the entries the kit actually ships, by name — a bare
# `chmod -R +x` on the whole target dir would also re-mode a project-local
# hook that lives alongside the kit's, silently, since chmod never gets an
# action line. `-R` is safe to use unconditionally here: it has no effect on
# a plain file, so the file/directory branch below doesn't need to split on it.
for hook_entry in "$SRC"/.claude/hooks/*; do
  [[ -e "$hook_entry" ]] || continue
  hook_name="$(basename "$hook_entry")"
  run chmod -R +x "$TARGET/.claude/hooks/$hook_name"
done

# Some settings keys are kit-managed, but settings.json is only seeded when
# missing — so when it already exists we must merge the kit's keys in.
# Idempotent: a no-op when seeding just copied them. Plugin keys: kit wins on
# conflict. worktree: project wins (a deliberate baseRef choice survives);
# only missing entries are filled in.
mode_arg=apply
if [[ $CHECK == true ]]; then
  mode_arg=check
fi
rc=0
if [[ $HAVE_PY == true ]]; then
  settings_merge "$SRC/.claude/settings.json" "$MERGE_TGT" "$mode_arg" || rc=$?
else
  rc=1
fi
case "$rc" in
0)
  emit 1 "MERGE .claude/settings.json (kit-managed keys synced)"
  ;;
9)
  same "OK    .claude/settings.json kit-managed keys already current"
  ;;
*)
  if [[ $HAVE_PY == true ]]; then
    warn "WARN  could not merge settings keys (the target's .claude/settings.json may not be valid JSON — see the error above) — add enabledPlugins + extraKnownMarketplaces + worktree from the kit manually"
  else
    warn "WARN  could not merge settings keys (no working python: tried python3, python, py -3) — add enabledPlugins + extraKnownMarketplaces + worktree from the kit manually"
  fi
  ;;
esac

# CLAUDE.md is kit-owned — always overwrite so workflow/skill updates propagate.
copy_kit_file "$SRC/CLAUDE.md" "$TARGET/CLAUDE.md" \
  "COPY  CLAUDE.md (kit-managed — do not edit; put project context in ProjectCLAUDE.md)"

# ProjectCLAUDE.md is project-owned — only seed it from the template if missing.
if [[ -f "$TARGET/ProjectCLAUDE.md" ]]; then
  same "KEEP  ProjectCLAUDE.md (already exists)"
else
  act "COPY  ProjectCLAUDE.md (from template — fill in the project-specific sections)" \
    cp "$SRC/ProjectCLAUDE.md.template" "$TARGET/ProjectCLAUDE.md"
fi

# Make sure local-only files stay out of the target's git history.
# .claude/worktrees/ holds worktree-isolated subagent checkouts (experiment
# spikes) — never content to commit.
GI="$TARGET/.gitignore"
for pattern in ".claude/settings.local.json" "CLAUDE.local.md" ".claude/worktrees/"; do
  if [[ ! -f "$GI" ]] || ! grep -qxF "$pattern" "$GI"; then
    act "GITIGNORE  added $pattern" gi_append "$GI" "$pattern"
  fi
done

# Preflight: the bundled plugins ship MCP servers launched via `npx`, which
# needs node on the PATH Claude Code inherits (a GUI launch may not see a
# version-manager / Homebrew PATH). Warn early instead of a silent ENOENT.
if ! command -v npx >/dev/null 2>&1; then
  warn "WARN  npx not found — context7 plugin's MCP server will fail (ENOENT)." \
    "      Install Node, then ensure node/npx are on Claude Code's PATH" \
    "      (e.g. symlink into ~/.local/bin)."
fi

echo "Done. Open the project and run /skills to verify everything loaded."

if [[ $CHECK == true ]]; then
  # Keyed on the merge rc, not on $HAVE_PY: a working interpreter that failed
  # on the target's settings.json (e.g. invalid JSON) is just as incomplete a
  # prediction as no interpreter at all — both land in the WARN arm above.
  incomplete=false
  if ((rc != 0 && rc != 9)); then
    incomplete=true
  fi

  trailer="nothing to do"
  exit_code=0
  if ((WOULD > 0)); then
    trailer="re-run without --check to apply"
    exit_code=2
  fi
  if [[ $incomplete == true ]]; then
    # "I cannot confirm nothing would change" must not short-circuit the
    # `--check || install` gate: force exit 2, and — even when WOULD alone
    # would have said "nothing to do" — say the same thing a real change
    # would, since a plain run is the safe fallback here too (it attempts
    # the merge for real and warns again if it still fails).
    trailer="re-run without --check to apply"
    exit_code=2
  fi
  # A SKIP warning (link-mode target exists and isn't a symlink) means a
  # plain re-run will NOT fix it — only removing the path manually will.
  # Overrides whichever trailer the checks above picked.
  if [[ $HAD_SKIP == true ]]; then
    trailer="resolve the skipped paths first, then re-run"
  fi

  summary="# $WOULD would change · $SAME unchanged · $WARNINGS warnings — $trailer (exit $exit_code)"
  if [[ $incomplete == true ]]; then
    summary="$summary — prediction incomplete (see stderr)"
  fi
  printf '%s\n' "$summary"
  exit "$exit_code"
fi
exit 0
