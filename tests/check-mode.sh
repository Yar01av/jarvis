#!/usr/bin/env bash
# tests/check-mode.sh — plain-bash harness for install.sh's --check (dry run)
# mode. Spec: docs/designs/install-dry-run.md (Architecture -> Test harness,
# as overridden by Plan sign-off). The Plan sign-off's 28 tests are below,
# implemented verbatim and in its order, plus a phase-9 review's fix-round
# additions appended within each section.
#
# Runs under `set -u` but deliberately NOT -e/pipefail: this is a runner with
# explicit pass/fail accounting, and predicates like `grep -c` legitimately
# return 1 when they match nothing (see normalize(), the gitignore counters).
#
# Tools used, all confirmed present: bash find cmp diff sed grep sort wc
# sha256sum stat mktemp tail readlink basename awk, plus core builtins/
# coreutils (cp mv mkdir rm printf cd) that install.sh itself already
# depends on. No bats/shellcheck/shellspec/rsync/jq/python assumed.
#
# install.sh is NEVER modified by this file, and nothing under .claude/ is
# ever touched — every fixture lives under a scratch dir whose name contains
# "jarvis-check-mode.", and every removal goes through sandbox_rm.

set -u
export LC_ALL=C

# ---------------------------------------------------------------------------
# Paths & globals
# ---------------------------------------------------------------------------
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
KIT="$(cd "$HERE/.." && pwd)"
INSTALL_SH="$KIT/install.sh"

if [[ ! -f "$INSTALL_SH" ]]; then
  echo "harness error: install.sh not found at $INSTALL_SH" >&2
  exit 1
fi

# Pure-string check, independent of the filesystem, so it can be unit-tested
# with a synthetic path that need not exist. Defined here, ahead of
# SCRATCH_ROOT, so the rail check right below can use it — sandbox_rm (which
# also needs it) is defined later, alongside the rest of the safety rail.
path_component_count() {
  local p="$1" IFS='/' parts=() n=0 x
  read -ra parts <<< "$p"
  for x in "${parts[@]}"; do
    [[ -n "$x" ]] && n=$((n + 1))
  done
  printf '%s\n' "$n"
}

SCRATCH_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/jarvis-check-mode.XXXXXX")" || {
  echo "harness error: mktemp failed to create a scratch dir" >&2
  exit 1
}
# sandbox_rm's shallow-path rail refuses anything under 3 path components,
# counted after resolving symlinks/mounts via `cd ... && pwd -P` (that's what
# sandbox_rm itself does before counting) — a raw, unresolved SCRATCH_ROOT is
# the wrong string to count: on Git Bash, /tmp is a mount onto a much deeper
# real path (e.g. /c/Users/<u>/AppData/Local/Temp), so the unresolved string
# would false-positive here even though sandbox_rm would happily remove it.
# TMPDIR unset on plain Linux falls back to a literal /tmp with no such
# mount, where /tmp/jarvis-check-mode.XXXXXX really is only 2 components and
# the rail really would refuse. Fail closed here, before anything is built
# under it, rather than discover it at teardown with a scratch tree already
# populated.
SCRATCH_ROOT_RESOLVED="$(cd "$SCRATCH_ROOT" && pwd -P)" || {
  echo "harness error: cannot resolve SCRATCH_ROOT '$SCRATCH_ROOT'" >&2
  exit 1
}
if (($(path_component_count "$SCRATCH_ROOT_RESOLVED") < 3)); then
  echo "harness error: SCRATCH_ROOT '$SCRATCH_ROOT' resolves to" >&2
  echo "'$SCRATCH_ROOT_RESOLVED', which has fewer than 3 path components —" >&2
  echo "sandbox_rm's shallow-path rail would refuse to remove it. Set" >&2
  echo "TMPDIR to a deeper path (e.g. export TMPDIR=\$HOME/tmp) and re-run." >&2
  echo "Leaving '$SCRATCH_ROOT' in place; it is empty." >&2
  exit 1
fi
PRISTINE="$SCRATCH_ROOT/pristine"
WORK="$SCRATCH_ROOT/work"
mkdir -p "$PRISTINE" "$WORK"

PASS_COUNT=0
FAIL_COUNT=0
TEST_DETAIL=""
INSTALL_RC=0

# The three patterns install.sh's gitignore loop appends, kept in one place.
GI_PATTERNS=(".claude/settings.local.json" "CLAUDE.local.md" ".claude/worktrees/")

# HOOK_SAMPLE_NAME: derived, not hardcoded — the name of one file the kit's
# own .claude/hooks/ ships. Tests that need to plant a pre-existing file at a
# real hook's path (to make a `cp` fail) key off this instead of a literal
# filename, so a hook rename doesn't silently stop exercising the abort path.
HOOK_SAMPLE_PATH="$(find "$KIT/.claude/hooks" -mindepth 1 -maxdepth 1 -type f | sort | head -1)"
HOOK_SAMPLE_NAME="$(basename "${HOOK_SAMPLE_PATH:-}" 2>/dev/null)"
if [[ -z "$HOOK_SAMPLE_NAME" ]]; then
  echo "harness error: kit's .claude/hooks/ has no files to sample from" >&2
  exit 1
fi

# ---------------------------------------------------------------------------
# Safety rail
# ---------------------------------------------------------------------------

# sandbox_rm: the ONLY way this harness ever removes anything. Refuses:
#   - any path that isn't a descendant of a scratch dir named jarvis-check-mode.*
#   - the kit repo itself, or any ancestor of the kit repo
#   - any resolved path with fewer than 3 path components
sandbox_rm() {
  local target="${1:-}"
  if [[ -z "$target" ]]; then
    echo "sandbox_rm: refusing empty path" >&2
    return 1
  fi
  if [[ ! -e "$target" ]]; then
    return 0 # already gone; not an error
  fi

  local resolved
  if [[ -d "$target" ]]; then
    resolved="$(cd "$target" 2>/dev/null && pwd -P)" || {
      echo "sandbox_rm: cannot resolve $target" >&2
      return 1
    }
  else
    local parent="${target%/*}" base="${target##*/}"
    [[ "$parent" == "$target" ]] && parent="."
    parent="$(cd "$parent" 2>/dev/null && pwd -P)" || {
      echo "sandbox_rm: cannot resolve parent of $target" >&2
      return 1
    }
    resolved="$parent/$base"
  fi

  case "$resolved" in
  */jarvis-check-mode.*) ;;
  *)
    echo "sandbox_rm: refusing path with no jarvis-check-mode. scratch ancestor: $resolved" >&2
    return 1
    ;;
  esac

  local kit_resolved
  kit_resolved="$(cd "$KIT" 2>/dev/null && pwd -P)" || kit_resolved="$KIT"
  case "$kit_resolved" in
  "$resolved")
    echo "sandbox_rm: refusing to remove the kit repo itself: $resolved" >&2
    return 1
    ;;
  "$resolved"/*)
    echo "sandbox_rm: refusing to remove an ancestor of the kit repo: $resolved" >&2
    return 1
    ;;
  esac

  local n
  n="$(path_component_count "$resolved")"
  if ((n < 3)); then
    echo "sandbox_rm: refusing shallow path ($n components): $resolved" >&2
    return 1
  fi

  rm -rf -- "$resolved"
}

selfcheck_sandbox_rm() {
  local ok=true

  if [[ "$(path_component_count "/a/b")" -ge 3 ]]; then
    echo "SELF-CHECK FAILED: path_component_count(\"/a/b\") should be < 3" >&2
    ok=false
  fi

  if sandbox_rm "$KIT" 2>/dev/null; then
    echo "SELF-CHECK FAILED: sandbox_rm removed the kit repo path" >&2
    ok=false
  fi
  if [[ ! -d "$KIT" ]]; then
    echo "SELF-CHECK CATASTROPHE: the kit repo directory is gone. Aborting." >&2
    exit 1
  fi

  if sandbox_rm "$KIT/.." 2>/dev/null; then
    echo "SELF-CHECK FAILED: sandbox_rm removed an ancestor of the kit repo" >&2
    ok=false
  fi

  if sandbox_rm "/tmp" 2>/dev/null; then
    echo "SELF-CHECK FAILED: sandbox_rm removed a shallow, non-scratch path (/tmp)" >&2
    ok=false
  fi

  # Positive case: sandbox_rm must actually work on a legitimate scratch path.
  local probe="$SCRATCH_ROOT/.selfcheck-probe"
  mkdir -p "$probe/nested"
  sandbox_rm "$probe"
  if [[ -e "$probe" ]]; then
    echo "SELF-CHECK FAILED: sandbox_rm did not remove a legitimate scratch-nested path" >&2
    ok=false
  fi

  if [[ "$ok" != true ]]; then
    echo "Aborting: the safety rail did not pass its own self-check." >&2
    exit 1
  fi
  echo "self-check ok: sandbox_rm refuses the kit/its ancestors/shallow-or-outside paths, and works on real scratch paths"
}

# ---------------------------------------------------------------------------
# Manifest / normalize
# ---------------------------------------------------------------------------

# manifest <dir>: one line per filesystem entry (type, relpath, and for files
# a sha256 + size + sub-second mtime + permission bits, so an identical-
# content cp that still touches mtime is caught, and so is a chmod with no
# content change at all — AC1 ("check mode writes nothing") must cover
# permissions, not just bytes).
manifest() {
  local root="$1" rroot
  rroot="$(cd "$root" 2>/dev/null && pwd)" || {
    echo "manifest: cannot cd into $root" >&2
    return 1
  }
  find "$rroot" -mindepth 1 -print0 | sort -z | while IFS= read -r -d '' entry; do
    local rel="${entry#"$rroot"/}"
    if [[ -L "$entry" ]]; then
      printf 'L\t%s\t%s\n' "$rel" "$(readlink "$entry")"
    elif [[ -d "$entry" ]]; then
      printf 'D\t%s\n' "$rel"
    elif [[ -f "$entry" ]]; then
      printf 'F\t%s\t%s\t%s\t%s\t%s\n' "$rel" \
        "$(sha256sum "$entry" | awk '{print $1}')" \
        "$(stat -c%s "$entry")" \
        "$(stat -c%.9Y "$entry")" \
        "$(stat -c%a "$entry")"
    else
      printf '?\t%s\n' "$rel"
    fi
  done
}

# kit_manifest <dir>: like manifest(), but excludes .git (git mutates its own
# internals independent of this harness) and omits mtime (OneDrive sync can
# touch metadata without changing content) — type + relpath + sha256 + size
# only, so a false SAFETY FAIL can't be caused by anything but a real write.
kit_manifest() {
  local root="$1" rroot
  rroot="$(cd "$root" 2>/dev/null && pwd)" || {
    echo "kit_manifest: cannot cd into $root" >&2
    return 1
  }
  find "$rroot" -path "$rroot/.git" -prune -o -mindepth 1 -print0 |
    sort -z | while IFS= read -r -d '' entry; do
      local rel="${entry#"$rroot"/}"
      if [[ -L "$entry" ]]; then
        printf 'L\t%s\t%s\n' "$rel" "$(readlink "$entry")"
      elif [[ -d "$entry" ]]; then
        printf 'D\t%s\n' "$rel"
      elif [[ -f "$entry" ]]; then
        printf 'F\t%s\t%s\t%s\n' "$rel" \
          "$(sha256sum "$entry" | awk '{print $1}')" \
          "$(stat -c%s "$entry")"
      else
        printf '?\t%s\n' "$rel"
      fi
    done
}

# The output contract's normalizer (spec, verbatim): strips check-only "# "
# enrichment lines, then strips the "would " marker. Applied identically to
# stdout and stderr, in both modes, so real output is a no-op under it.
normalize() {
  grep -v '^# ' | sed 's/^would //'
}

# expected_gitignore_adds <gitignore-file>: how many of the 3 kit patterns
# install.sh's OWN predicate (`grep -qxF`) would currently consider missing.
# Computed, never pinned — msys grep matches CRLF lines, GNU/Linux grep
# would not (Spike A finding C).
expected_gitignore_adds() {
  local gi="$1" count=0 p
  for p in "${GI_PATTERNS[@]}"; do
    if [[ ! -f "$gi" ]] || ! grep -qxF "$p" "$gi"; then
      count=$((count + 1))
    fi
  done
  printf '%s\n' "$count"
}

# ---------------------------------------------------------------------------
# Runner helpers
# ---------------------------------------------------------------------------

# new_instance <fixture> -> prints the path of a fresh, writable copy of a
# pristine fixture under $WORK. Every test gets its own instance(s).
#
# Uses `mktemp -d` for uniqueness rather than a shell counter: this function
# is always called as `x="$(new_instance ...)"`, i.e. inside a command-
# substitution subshell — a plain `COUNTER=$((COUNTER+1))` would increment
# only that subshell's copy and never propagate back, so every call for the
# same fixture name would silently collide on the same destination and
# accumulate cruft from whatever the previous test did to it. mktemp's
# uniqueness is real (filesystem-backed), not shell-state, so it survives
# the subshell. (Caught empirically: see report.)
new_instance() {
  local fixture="$1"
  local dst
  dst="$(mktemp -d "$WORK/inst-${fixture}.XXXXXX")" || return 1
  cp -R "$PRISTINE/$fixture/." "$dst/"
  printf '%s\n' "$dst"
}

# run_install <outfile> <errfile> <target> [args...] — invokes install.sh via
# `bash`, sets $INSTALL_RC. Refuses to run against anything that isn't a
# $WORK instance (never a pristine fixture, never the kit) as a second,
# independent guard against corrupting the fixtures a test run depends on.
run_install() {
  local out="$1" err="$2" target="$3"
  shift 3
  case "$target" in
  "$WORK"/*) ;;
  *)
    echo "run_install: refusing to run against a non-instance path: $target" >&2
    INSTALL_RC=127
    return 1
    ;;
  esac
  bash "$INSTALL_SH" "$target" "$@" >"$out" 2>"$err"
  INSTALL_RC=$?
}

fail() { TEST_DETAIL="$1"; }

# ---------------------------------------------------------------------------
# Fixture builders — each built once into pristine/, cp -R'd fresh per use.
# ---------------------------------------------------------------------------

build_fixture_empty() {
  mkdir -p "$PRISTINE/empty"
}

build_fixture_current() {
  local dir="$PRISTINE/current"
  mkdir -p "$dir"
  bash "$INSTALL_SH" "$dir" >"$WORK/.build-current.out" 2>"$WORK/.build-current.err"
  local rc=$?
  if ((rc != 0)); then
    # Every other fixture derives from 'current' (cp -R's it, then mutates a
    # copy) — a bad build here cascades into confusing reds across the whole
    # suite rather than one clear failure at the source. Abort instead. Print
    # stderr inline rather than pointing at the file, then remove the scratch
    # tree — telling the reader to go read a file this same block is about to
    # delete would leave them with nothing.
    echo "fixture builder: building 'current' failed (rc=$rc); stderr:" >&2
    cat "$WORK/.build-current.err" >&2
    sandbox_rm "$SCRATCH_ROOT"
    exit 1
  fi
}

# stale = current + a pre-rename skill dir the kit no longer ships, and a
# project-local skill the kit never shipped. Exercises target-only entries.
build_fixture_stale() {
  local dir="$PRISTINE/stale"
  [[ -d "$PRISTINE/current" ]] || build_fixture_current
  cp -R "$PRISTINE/current" "$dir"
  mkdir -p "$dir/.claude/skills/build-feature"
  printf '# stale pre-rename skill, left behind by an old install\n' \
    >"$dir/.claude/skills/build-feature/SKILL.md"
  mkdir -p "$dir/.claude/skills/my-local-skill"
  printf '# a project-local skill the kit never shipped\n' \
    >"$dir/.claude/skills/my-local-skill/SKILL.md"
}

# divergent-settings = current's settings.json (kit-managed keys already
# current) plus one project-only top-level key, so cmp reports "differs"
# while the installer's real branch (bare existence check) says KEEP.
# Spike B's case, derived from the real fixture rather than hand-duplicated,
# so it tracks the kit's actual baseline instead of drifting from it.
build_fixture_divergent_settings() {
  local dir="$PRISTINE/divergent-settings"
  [[ -d "$PRISTINE/current" ]] || build_fixture_current
  cp -R "$PRISTINE/current" "$dir"
  local settings="$dir/.claude/settings.json"
  local tmp="$WORK/.divergent-settings.json.tmp"
  sed '$d' "$settings" | sed '$ s/$/,/' >"$tmp"
  {
    printf '  "projectOnly": { "note": "local-only drift, do not remove" }\n'
    printf '}\n'
  } >>"$tmp"
  mv "$tmp" "$settings"
}

# missing-kit-keys = a settings.json that predates all three kit-managed
# keys entirely — the merge step should MERGE, not KEEP or WARN.
build_fixture_missing_kit_keys() {
  local dir="$PRISTINE/missing-kit-keys"
  [[ -d "$PRISTINE/current" ]] || build_fixture_current
  cp -R "$PRISTINE/current" "$dir"
  cat >"$dir/.claude/settings.json" <<'JSON'
{
  "$schema": "https://json.schemastore.org/claude-code-settings.json",
  "permissions": {
    "allow": [],
    "deny": []
  }
}
JSON
}

# invalid-json = current's settings.json with a trailing comma injected
# before the final closing brace — syntactically broken JSON despite the kit
# keys themselves being present and current. Exercises the review's WARN
# cause-discrimination fix: a working interpreter that fails to parse the
# target's settings.json must not be blamed on "no working python".
build_fixture_invalid_json() {
  local dir="$PRISTINE/invalid-json"
  [[ -d "$PRISTINE/current" ]] || build_fixture_current
  cp -R "$PRISTINE/current" "$dir"
  local settings="$dir/.claude/settings.json"
  local tmp="$WORK/.invalid-json.settings.json.tmp"
  sed '$d' "$settings" | sed '$ s/$/,/' >"$tmp"
  printf '}\n' >>"$tmp"
  mv "$tmp" "$settings"
}

# partial: listed in the Architecture's fixture set but not consumed by any
# test in the Plan sign-off's trimmed 28-test list. Built for spec fidelity;
# deliberately never instantiated by a test — see the report's spec-defect
# note (Revision 2 trimmed 44 tests -> 28 without reconciling this list).
build_fixture_partial() {
  local dir="$PRISTINE/partial"
  mkdir -p "$dir/.claude"
  [[ -d "$PRISTINE/current" ]] || build_fixture_current
  cp "$PRISTINE/current/.claude/settings.json" "$dir/.claude/settings.json"
}

# gitignore-crlf = current + a CRLF .gitignore that ALREADY contains all
# three kit patterns, CRLF-terminated. Spike A finding C: msys grep -qxF
# matches CRLF lines (0 adds here); GNU grep on Linux would not (3 adds).
# On Git Bash this fixture is therefore vacuous for the "0 adds" half of that
# claim (nothing here can tell msys grep's CRLF-tolerance apart from a bug
# that also produced 0 adds) — it's a portability canary, not a live
# assertion, until this suite runs on Linux, where the 3-adds branch becomes
# load-bearing.
build_fixture_gitignore_crlf() {
  local dir="$PRISTINE/gitignore-crlf"
  [[ -d "$PRISTINE/current" ]] || build_fixture_current
  cp -R "$PRISTINE/current" "$dir"
  printf '%s\r\n' "${GI_PATTERNS[@]}" >"$dir/.gitignore"
}

# gitignore-noeol = current + a .gitignore whose last line has no trailing
# newline, none of the 3 kit patterns present. Spike A finding B: the first
# append fuses onto the unterminated last line.
build_fixture_gitignore_noeol() {
  local dir="$PRISTINE/gitignore-noeol"
  [[ -d "$PRISTINE/current" ]] || build_fixture_current
  cp -R "$PRISTINE/current" "$dir"
  printf 'p1\np2' >"$dir/.gitignore"
}

# artifact_tag <argv...>: turns a full call's argument vector into a safe,
# filename-usable tag. Needed because several tests call antidrift_check or
# assert_no_writes with the SAME fixture but different flags (e.g. "empty any
# --check" vs "empty any --link --check") — keying an output file on the
# fixture name alone means the later call overwrites the earlier call's
# captured stdout/stderr, destroying the post-mortem evidence a failing test
# depends on. Not guaranteed collision-free against adversarial input (this
# harness's own call sites are the only input), just against the callers that
# actually exist today.
artifact_tag() {
  local s="$*"
  s="${s// /_}"
  s="${s//[^A-Za-z0-9_.-]/_}"
  printf '%s' "$s"
}

# ---------------------------------------------------------------------------
# Anti-drift shared helper
# ---------------------------------------------------------------------------

# antidrift_check <fixture> [extra args applied to BOTH invocations] —
# instantiates the fixture twice, runs --check into one and a real apply
# into the other, compares normalize()'d stdout AND stderr for equality.
antidrift_check() {
  local fixture="$1"
  shift
  local tag
  tag="$(artifact_tag "$fixture" "$@")"
  local a b
  a="$(new_instance "$fixture")"
  b="$(new_instance "$fixture")"
  local outA="$WORK/.ad.$tag.A.out" errA="$WORK/.ad.$tag.A.err"
  local outB="$WORK/.ad.$tag.B.out" errB="$WORK/.ad.$tag.B.err"

  run_install "$outA" "$errA" "$a" --check "$@"
  local rcA=$INSTALL_RC
  run_install "$outB" "$errB" "$b" "$@"
  local rcB=$INSTALL_RC

  local normA normB
  normA="$(normalize <"$outA")"
  normB="$(normalize <"$outB")"
  if [[ "$normA" != "$normB" ]]; then
    fail "normalized stdout differs, --check (rc=$rcA) vs apply (rc=$rcB): $(diff <(printf '%s\n' "$normA") <(printf '%s\n' "$normB") | tr '\n' ' ')"
    return 1
  fi

  local errNormA errNormB
  errNormA="$(normalize <"$errA")"
  errNormB="$(normalize <"$errB")"
  if [[ "$errNormA" != "$errNormB" ]]; then
    fail "normalized stderr differs, --check (rc=$rcA) vs apply (rc=$rcB): $(diff <(printf '%s\n' "$errNormA") <(printf '%s\n' "$errNormB") | tr '\n' ' ')"
    return 1
  fi
  return 0
}

# ---------------------------------------------------------------------------
# No-writes shared helper
# ---------------------------------------------------------------------------

# assert_no_writes <fixture> <expected_rc|any> [install.sh args...] —
# instantiates the fixture, runs install.sh with the given args, and asserts
# the target's manifest is byte-for-byte unchanged (see manifest()'s own
# comment for what "unchanged" covers: content, mtime, and mode bits).
# expected_rc also checks the exit code, unless it's the literal string
# "any" — some of this helper's callers never asserted an rc, and collapsing
# them into one helper must not add an assertion none of them had.
assert_no_writes() {
  local fixture="$1" expected_rc="$2"
  shift 2
  local tag
  tag="$(artifact_tag "$fixture" "$expected_rc" "$@")"
  local target
  target="$(new_instance "$fixture")"
  local out="$WORK/.anw.$tag.out" err="$WORK/.anw.$tag.err"
  local before after
  before="$(manifest "$target")"
  run_install "$out" "$err" "$target" "$@"
  after="$(manifest "$target")"
  if [[ "$expected_rc" != any ]] && ((INSTALL_RC != expected_rc)); then
    fail "expected exit $expected_rc, got rc=$INSTALL_RC; stderr: $(tr '\n' ' ' <"$err")"
    return 1
  fi
  if [[ "$before" != "$after" ]]; then
    local before_n after_n
    before_n="$(printf '%s\n' "$before" | grep -c .)"
    after_n="$(printf '%s\n' "$after" | grep -c .)"
    fail "expected no writes for '$fixture $*'; manifest changed ($before_n -> $after_n entries); stderr: $(tr '\n' ' ' <"$err")"
    return 1
  fi
  return 0
}

# ---------------------------------------------------------------------------
# Tests — the Plan sign-off's 28, verbatim and in its order, plus a phase-9
# review fix round's additions interspersed by section.
# ---------------------------------------------------------------------------

# --- parsing / usage --------------------------------------------------------

test_unknown_flag_exits_1_and_writes_nothing() {
  assert_no_writes empty 1 --bogus-flag
}

test_unknown_flag_error_names_the_flag() {
  # A generic usage line doesn't tell the caller whether they typo'd a real
  # flag or asked for something unsupported — the rejected flag itself must
  # appear in the message.
  local target
  target="$(new_instance empty)"
  run_install "$WORK/.out.ufn" "$WORK/.err.ufn" "$target" --bogus-flag
  if ! grep -qF -- '--bogus-flag' "$WORK/.err.ufn"; then
    fail "expected the offending flag '--bogus-flag' to appear in the usage error; stderr: $(tr '\n' ' ' <"$WORK/.err.ufn")"
    return 1
  fi
  return 0
}

test_refuses_kit_repo_as_target() {
  local out="$WORK/.out.rk" err="$WORK/.err.rk"
  bash "$INSTALL_SH" "$KIT" --check >"$out" 2>"$err"
  local rc=$?
  if ((rc != 1)); then
    fail "expected exit 1 when target == kit repo, got rc=$rc"
    return 1
  fi
  if ! grep -qF "Refusing to install into the kit repo itself." "$err"; then
    fail "expected the kit-repo refusal message on stderr; got: $(tr '\n' ' ' <"$err")"
    return 1
  fi
  return 0
}

test_check_and_link_compose() {
  assert_no_writes empty any --link --check
}

# --- writes nothing ----------------------------------------------------------

test_check_writes_nothing_empty_target() {
  assert_no_writes empty any --check
}

test_check_writes_nothing_gitignore_noeol_target() {
  assert_no_writes gitignore-noeol any --check
}

test_check_never_writes_to_the_kit_repo() {
  # Must be a fresh/empty target, not "current": the risky case this guards
  # (Revision 1 — MERGE_TGT must never be a kit path) only exists when the
  # settings.json SEED branch fires, which only happens on a target that
  # doesn't have one yet. Against "current" the seed branch never fires and
  # this test would pass without exercising the path it exists to guard.
  local target
  target="$(new_instance empty)"
  local kit_before kit_after
  kit_before="$(kit_manifest "$KIT")"
  run_install "$WORK/.out.wk" "$WORK/.err.wk" "$target" --check
  kit_after="$(kit_manifest "$KIT")"
  if [[ "$kit_before" != "$kit_after" ]]; then
    fail "install.sh <dir> --check wrote into the kit repo itself — kit manifest changed"
    return 1
  fi
  return 0
}

# --- anti-drift ---------------------------------------------------------------

test_antidrift_empty_target() { antidrift_check empty; }
test_antidrift_current_target() { antidrift_check current; }
test_antidrift_divergent_settings() { antidrift_check divergent-settings; }
test_antidrift_missing_kit_keys() { antidrift_check missing-kit-keys; }
test_antidrift_gitignore_crlf() { antidrift_check gitignore-crlf; }
test_antidrift_gitignore_noeol() { antidrift_check gitignore-noeol; }

test_antidrift_link_mode() { antidrift_check empty --link; }

# --- exit codes -----------------------------------------------------------

test_exit_0_when_target_current() {
  local target
  target="$(new_instance current)"
  run_install "$WORK/.out.e0" "$WORK/.err.e0" "$target" --check
  if ((INSTALL_RC != 0)); then
    fail "expected exit 0 on an already-current target, got rc=$INSTALL_RC"
    return 1
  fi
  return 0
}

test_exit_2_when_changes_pending() {
  local target
  target="$(new_instance empty)"
  run_install "$WORK/.out.e2" "$WORK/.err.e2" "$target" --check
  if ((INSTALL_RC != 2)); then
    fail "expected exit 2 with changes pending (empty target), got rc=$INSTALL_RC"
    return 1
  fi
  return 0
}

test_apply_mode_still_exits_0() {
  local target
  target="$(new_instance empty)"
  run_install "$WORK/.out.ea" "$WORK/.err.ea" "$target"
  if ((INSTALL_RC != 0)); then
    fail "expected exit 0 for a plain apply run, got rc=$INSTALL_RC"
    return 1
  fi
  return 0
}

test_midrun_abort_exits_3_and_says_partial() {
  # A real apply, not --check: the abort only exists on the mutation path.
  # Pre-seed the target with an unwritable file at the same path a kit hook
  # ships, so `cp -R .../hooks ...` fails partway through.
  local target
  target="$(new_instance empty)"
  mkdir -p "$target/.claude/hooks"
  printf 'pre-existing, unwritable\n' >"$target/.claude/hooks/$HOOK_SAMPLE_NAME"
  chmod 444 "$target/.claude/hooks/$HOOK_SAMPLE_NAME"
  run_install "$WORK/.out.ma" "$WORK/.err.ma" "$target"
  local rc=$INSTALL_RC
  # Restore writability before any further use of $target (including the
  # suite's final sandbox_rm) so this repro doesn't leak a read-only file.
  chmod 644 "$target/.claude/hooks/$HOOK_SAMPLE_NAME" 2>/dev/null
  if ((rc != 3)); then
    fail "expected exit 3 for a mid-run abort, got rc=$rc"
    return 1
  fi
  if ! grep -qi 'ABORTED' "$WORK/.err.ma"; then
    fail "expected an ABORTED message on stderr reporting the partial write; stderr: $(tr '\n' ' ' <"$WORK/.err.ma")"
    return 1
  fi
  # Now that the trap has two distinct messages (mode-aware, since fix round
  # 2), pin the apply-mode one specifically — otherwise this test and
  # test_check_mode_abort_says_nothing_was_written would both pass even if a
  # future edit made apply mode print the check-mode text.
  if ! grep -qi 'partially written' "$WORK/.err.ma"; then
    fail "expected the apply-mode ABORTED message to say 'partially written'; stderr: $(tr '\n' ' ' <"$WORK/.err.ma")"
    return 1
  fi
  # Assert the observable intent, not install.sh's exact step order (a
  # future reordering shouldn't need this test rewritten): a real mid-run
  # abort leaves SOME evidence of partial work on disk beyond the pre-seeded
  # hooks/ file, and it never reaches the final line.
  if [[ -z "$(find "$target/.claude" -mindepth 1 ! -path "$target/.claude/hooks*" 2>/dev/null)" ]]; then
    fail "expected some evidence of partial work under $target/.claude besides the pre-seeded hooks/ file"
    return 1
  fi
  if grep -qxF 'Done. Open the project and run /skills to verify everything loaded.' "$WORK/.out.ma"; then
    fail "expected no 'Done.' line on stdout — a half-install must not claim completion"
    return 1
  fi
  return 0
}

test_check_mode_abort_says_nothing_was_written() {
  # Reproduces fix-round-2 finding (a): plan_settings_seed's check-only
  # `MERGE_TMP="$(mktemp)"` + `cp` into it are real, ungated writes — to a
  # scratch file, never the target — so a broken TMPDIR aborts check mode
  # too. Before the fix this printed "target may be partially written"
  # (false: check mode never touches the target) and printed it TWICE (once
  # in the command-substitution subshell `-E` hands the trap, once in the
  # parent). Bypasses run_install (like test_refuses_kit_repo_as_target)
  # because TMPDIR must be set only for this one invocation.
  local target
  target="$(new_instance empty)"
  local before after
  before="$(manifest "$target")"
  local out="$WORK/.out.tmpdir-abort" err="$WORK/.err.tmpdir-abort"
  TMPDIR=/nonexistent-dir-xyz bash "$INSTALL_SH" "$target" --check >"$out" 2>"$err"
  local rc=$?
  after="$(manifest "$target")"
  if ((rc != 3)); then
    fail "expected exit 3 when the check-only mktemp fails under a broken TMPDIR, got rc=$rc; stderr: $(tr '\n' ' ' <"$err")"
    return 1
  fi
  if [[ "$before" != "$after" ]]; then
    fail "expected the target to be unchanged after a check-mode abort; manifest changed"
    return 1
  fi
  if ! grep -qi 'nothing was written' "$err"; then
    fail "expected the ABORTED message to say 'nothing was written' in check mode; stderr: $(tr '\n' ' ' <"$err")"
    return 1
  fi
  if grep -qi 'partially written' "$err"; then
    fail "check-mode abort message still claims the target may be partially written: $(tr '\n' ' ' <"$err")"
    return 1
  fi
  local aborted_n
  aborted_n="$(grep -ci 'ABORTED' "$err")"
  if ((aborted_n != 1)); then
    fail "expected exactly one ABORTED line on stderr, got $aborted_n: $(tr '\n' ' ' <"$err")"
    return 1
  fi
  return 0
}

test_shadowed_find_does_not_falsely_abort() {
  # Reproduces fix-round-2 finding (b): `-E` also hands the ERR trap to
  # tree_scan's process substitutions (`< <(find ...)`), where `exit 3` only
  # kills that subshell. Shadow `find` with a wrapper that runs the real
  # `find` then always exits 1 (what a real `find` does against an
  # unreadable directory) — before the fix the trap fired (and printed)
  # three times on a run that then completed successfully with correct
  # output and exit 2.
  local real_find
  real_find="$(command -v find)" || {
    fail "no system 'find' on PATH to shadow"
    return 1
  }
  local fakebin="$WORK/.fakebin-find.$$"
  mkdir -p "$fakebin"
  cat >"$fakebin/find" <<EOF
#!/usr/bin/env bash
"$real_find" "\$@"
exit 1
EOF
  chmod +x "$fakebin/find"
  local target
  target="$(new_instance empty)"
  local out="$WORK/.out.shadowed-find" err="$WORK/.err.shadowed-find"
  PATH="$fakebin:$PATH" bash "$INSTALL_SH" "$target" --check >"$out" 2>"$err"
  local rc=$?
  if ((rc != 2)); then
    fail "expected exit 2 (changes pending) even with a 'find' that always exits 1, got rc=$rc; stderr: $(tr '\n' ' ' <"$err")"
    return 1
  fi
  if grep -qi 'ABORTED' "$out" "$err"; then
    fail "the trap fired inside tree_scan's process-substitution subshell despite the run completing successfully: stdout: $(tr '\n' ' ' <"$out") stderr: $(tr '\n' ' ' <"$err")"
    return 1
  fi
  if ! grep -qxF 'Done. Open the project and run /skills to verify everything loaded.' "$out"; then
    fail "expected the run to complete normally (Done. line present) despite the shadowed 'find'"
    return 1
  fi
  return 0
}

# --- link-mode SKIP messaging -----------------------------------------------

test_link_check_skip_trailer_says_resolve_manually() {
  # Smoke-test defect: a target whose .claude/skills exists as a real
  # directory (not a symlink) makes link mode SKIP it and warn on stderr —
  # but a plain re-run will NOT link that directory, only removing it
  # manually will. The trailer must say that, not promise a re-run fixes it.
  local target
  target="$(new_instance empty)"
  mkdir -p "$target/.claude/skills"
  printf 'real dir, not a symlink\n' >"$target/.claude/skills/placeholder"
  run_install "$WORK/.out.lst" "$WORK/.err.lst" "$target" --link --check
  if ! grep -qi 'SKIP' "$WORK/.err.lst"; then
    fail "expected a SKIP warning for the real .claude/skills directory; stderr: $(tr '\n' ' ' <"$WORK/.err.lst")"
    return 1
  fi
  if grep -qF 're-run without --check to apply' "$WORK/.out.lst"; then
    fail "trailer still promises a plain re-run fixes the SKIP; stdout: $(tr '\n' ' ' <"$WORK/.out.lst")"
    return 1
  fi
  if ! grep -qi 'resolve' "$WORK/.out.lst"; then
    fail "expected the trailer to say the skipped path must be resolved manually; stdout: $(tr '\n' ' ' <"$WORK/.out.lst")"
    return 1
  fi
  return 0
}

# --- the settings line (unpredictable line 1) ------------------------------

test_no_false_warn_could_not_merge_on_empty_target() {
  # Narrowed to the merge-specific WARN text, not any 'WARN' — a bare 'WARN'
  # grep would also fire on the (unrelated) npx-missing preflight warning.
  local target
  target="$(new_instance empty)"
  run_install "$WORK/.out.nw" "$WORK/.err.nw" "$target" --check
  if grep -qi 'could not merge' "$WORK/.err.nw"; then
    fail "stderr contains the merge WARN line on a fresh/empty target: $(tr '\n' ' ' <"$WORK/.err.nw")"
    return 1
  fi
  return 0
}

test_no_python_traceback_on_stderr_empty_target() {
  local target
  target="$(new_instance empty)"
  run_install "$WORK/.out.nt" "$WORK/.err.nt" "$target" --check
  if grep -qiE 'Traceback|FileNotFoundError' "$WORK/.err.nt"; then
    fail "stderr leaked a python traceback: $(tr '\n' ' ' <"$WORK/.err.nt")"
    return 1
  fi
  return 0
}

test_predicts_merge_when_kit_keys_missing() {
  local target
  target="$(new_instance missing-kit-keys)"
  run_install "$WORK/.out.pm" "$WORK/.err.pm" "$target" --check
  if ! grep -qE 'MERGE.*settings\.json' "$WORK/.out.pm"; then
    fail "expected a MERGE line for settings.json when kit-managed keys are missing; stdout: $(tr '\n' ' ' <"$WORK/.out.pm") stderr: $(tr '\n' ' ' <"$WORK/.err.pm")"
    return 1
  fi
  return 0
}

test_keep_settings_never_reported_as_overwrite() {
  local target
  target="$(new_instance divergent-settings)"
  run_install "$WORK/.out.ks" "$WORK/.err.ks" "$target" --check
  if grep -qE 'COPY +\.claude/settings\.json' "$WORK/.out.ks"; then
    fail "settings.json reported as COPY/overwrite even though it exists with current kit keys (byte-compare over-reporting, Spike B): $(tr '\n' ' ' <"$WORK/.out.ks")"
    return 1
  fi
  if ! grep -qE '(KEEP|OK) +\.claude/settings\.json' "$WORK/.out.ks"; then
    fail "expected a KEEP/OK line for settings.json; stdout: $(tr '\n' ' ' <"$WORK/.out.ks")"
    return 1
  fi
  return 0
}

test_merge_succeeds_when_python3_is_a_stub() {
  # Narrowed to the merge-specific WARN text for the same reason as
  # test_no_false_warn_could_not_merge_on_empty_target above.
  local target
  target="$(new_instance missing-kit-keys)"
  run_install "$WORK/.out.mp" "$WORK/.err.mp" "$target" --check
  if grep -qi 'could not merge' "$WORK/.err.mp"; then
    fail "expected the python3 -> python -> py -3 fallback to let the merge succeed despite python3 being a Store stub (exit 49) on this machine; stderr instead reports 'could not merge': $(tr '\n' ' ' <"$WORK/.err.mp")"
    return 1
  fi
  return 0
}

test_invalid_json_warns_about_json_not_python() {
  # A working interpreter that fails to parse the target's settings.json
  # must not be blamed on "no working python" — that sends the user chasing
  # a Python install for a JSON syntax error.
  local target
  target="$(new_instance invalid-json)"
  run_install "$WORK/.out.ij" "$WORK/.err.ij" "$target" --check
  if grep -qi 'no working python' "$WORK/.err.ij"; then
    fail "WARN blamed 'no working python' for a working interpreter that failed on invalid JSON: $(tr '\n' ' ' <"$WORK/.err.ij")"
    return 1
  fi
  if ! grep -qi 'valid JSON' "$WORK/.err.ij"; then
    fail "expected the WARN to point at the target's settings.json possibly not being valid JSON; stderr: $(tr '\n' ' ' <"$WORK/.err.ij")"
    return 1
  fi
  return 0
}

test_check_reports_incomplete_when_merge_prediction_fails() {
  # Same fixture as above, from the exit-0/summary side: a broken merge
  # prediction must not exit 0 claiming "nothing to do" without saying so.
  local target
  target="$(new_instance invalid-json)"
  run_install "$WORK/.out.ci" "$WORK/.err.ci" "$target" --check
  if ! grep -qi 'prediction incomplete' "$WORK/.out.ci"; then
    fail "expected the summary to say 'prediction incomplete' when the merge prediction failed on a working interpreter; stdout: $(tr '\n' ' ' <"$WORK/.out.ci")"
    return 1
  fi
  return 0
}

test_exit_2_when_merge_prediction_incomplete() {
  # Smoke-test defect: an incomplete prediction must not exit 0 — a caller
  # branching on the exit code (README's `--check || install` gate) would
  # treat an unresolved settings merge as "nothing to do" and never retry.
  # The invalid-json fixture is otherwise fully current, so WOULD would be
  # 0 without this fix — the exit code must be forced to 2 regardless.
  local target
  target="$(new_instance invalid-json)"
  run_install "$WORK/.out.epi" "$WORK/.err.epi" "$target" --check
  if ((INSTALL_RC != 2)); then
    fail "expected exit 2 when the merge prediction is incomplete (invalid JSON), got rc=$INSTALL_RC; stdout: $(tr '\n' ' ' <"$WORK/.out.epi")"
    return 1
  fi
  return 0
}

# --- the gitignore line (unpredictable line 2) + the corruption bug --------

test_gitignore_all_three_predicted_on_missing_file() {
  local target
  target="$(new_instance empty)"
  local expected
  expected="$(expected_gitignore_adds "$target/.gitignore")"
  run_install "$WORK/.out.g3" "$WORK/.err.g3" "$target" --check
  local got
  got="$(grep -c 'GITIGNORE  added' "$WORK/.out.g3")"
  if [[ "$got" != "$expected" ]]; then
    fail "expected $expected predicted GITIGNORE adds on a target with no .gitignore, got $got"
    return 1
  fi
  return 0
}

test_gitignore_does_not_corrupt_unterminated_last_line() {
  # Real apply, not --check: the corruption comes from gi_append's mutation
  # (echo >> fusing onto an unterminated last line), which only exists on
  # the write path. Running this under --check would go green the moment
  # check mode writes nothing, without ever exercising the actual bug.
  local target
  target="$(new_instance gitignore-noeol)"
  run_install "$WORK/.out.gc" "$WORK/.err.gc" "$target"
  if ! grep -qxF 'p2' "$target/.gitignore"; then
    fail "expected the pre-existing unterminated last line 'p2' to still be intact as its own line after the append; last lines now: $(tail -3 "$target/.gitignore" | tr '\n' '|')"
    return 1
  fi
  return 0
}

test_gitignore_converges_in_one_apply_run() {
  local target
  target="$(new_instance gitignore-noeol)"
  run_install "$WORK/.out.gv" "$WORK/.err.gv" "$target"
  local missing="" p
  for p in "${GI_PATTERNS[@]}"; do
    grep -qxF "$p" "$target/.gitignore" || missing="$missing [$p]"
  done
  if [[ -n "$missing" ]]; then
    fail "expected all three patterns present as standalone lines after one apply run; still missing:$missing"
    return 1
  fi
  return 0
}

# --- stale reporting --------------------------------------------------------

test_stale_entry_reported_and_not_counted_as_change() {
  local target
  target="$(new_instance stale)"
  run_install "$WORK/.out.st" "$WORK/.err.st" "$target" --check
  if ! grep -q 'STALE' "$WORK/.out.st"; then
    fail "expected a STALE line for build-feature/ and the local-only skill"
    return 1
  fi

  # AC6's other, easy-to-miss half: stale entries must not be counted as
  # changes. "stale" is otherwise identical to "current", so its "would
  # change" tally must equal current's — derived from a second run, never
  # pinned to a number, so this keeps checking the real invariant even
  # after STALE reporting ships.
  local target2
  target2="$(new_instance current)"
  run_install "$WORK/.out.st2" "$WORK/.err.st2" "$target2" --check
  local stale_n current_n
  # The summary line is `# N would change · …`. That `# ` prefix is required,
  # not cosmetic: normalize() strips `# ` lines, apply mode prints no summary at
  # all, and seven antidrift tests need normalized check-stdout == apply-stdout.
  stale_n="$(grep -oE '^# [0-9]+ would change' "$WORK/.out.st" | grep -oE '[0-9]+' | head -1)"
  current_n="$(grep -oE '^# [0-9]+ would change' "$WORK/.out.st2" | grep -oE '[0-9]+' | head -1)"
  if [[ -z "$stale_n" || -z "$current_n" ]]; then
    fail "expected a '# N would change' summary line to compare stale vs current tallies; found none"
    return 1
  fi
  if [[ "$stale_n" != "$current_n" ]]; then
    fail "stale target-only entries were counted as changes: stale tally=$stale_n vs current tally=$current_n (should be equal)"
    return 1
  fi
  return 0
}

# --- in-scope fixes and the output contract --------------------------------

test_hooks_tree_installed_in_apply_mode() {
  local target
  target="$(new_instance empty)"
  run_install "$WORK/.out.hk" "$WORK/.err.hk" "$target"
  if [[ ! -f "$target/.claude/hooks/$HOOK_SAMPLE_NAME" ]]; then
    fail "expected $HOOK_SAMPLE_NAME to exist under .claude/hooks/ after apply — settings.json wires a SessionStart hook to that tree"
    return 1
  fi
  return 0
}

test_enrichment_lines_are_check_only() {
  local target
  target="$(new_instance empty)"
  run_install "$WORK/.out.en" "$WORK/.err.en" "$target"
  if grep -q '^# ' "$WORK/.out.en"; then
    fail "apply-mode stdout contains a check-only '# ' enrichment line: $(grep '^# ' "$WORK/.out.en" | tr '\n' ' ')"
    return 1
  fi
  # A future step could bypass `emit` with a bare `printf 'would PRUNE …\n'`
  # instead of an `echo` — the '# '-only check above wouldn't catch that, and
  # apply mode would then print a literal "would " line nothing objects to.
  if grep -q '^would ' "$WORK/.out.en"; then
    fail "apply-mode stdout contains a check-only 'would ' line: $(grep '^would ' "$WORK/.out.en" | tr '\n' ' ')"
    return 1
  fi
  return 0
}

# _assert_every_check_line_is_prefixed_or_known <fixture>: guards the output
# contract itself, not any one line of it: a future step written as
# `run cp …` plus a bare `echo "PRUNE …"` would pass every other test here
# (identical in both modes -> anti-drift passes; writes nothing -> no-write
# passes) while never reaching emit(), so the change counter wouldn't tick
# and the summary would silently say "nothing to do". Every check-mode
# stdout line must be an action line (`would `), an enrichment line (`# `),
# or the one fixed `Done. …` line — nothing else is legal. Run against more
# than one fixture — a fresh 'empty' target never exercises the KEEP/OK/STALE
# branches that only fire once something already exists.
_assert_every_check_line_is_prefixed_or_known() {
  local fixture="$1"
  local target
  target="$(new_instance "$fixture")"
  local out="$WORK/.pf.$fixture.out" err="$WORK/.pf.$fixture.err"
  run_install "$out" "$err" "$target" --check
  local bad
  bad="$(grep -vE '^(would |# )' "$out" | grep -vxF 'Done. Open the project and run /skills to verify everything loaded.')"
  if [[ -n "$bad" ]]; then
    fail "found a check-mode stdout line (fixture=$fixture) that is neither 'would '-prefixed, '# '-prefixed, nor the Done. line: $(printf '%s' "$bad" | tr '\n' '|')"
    return 1
  fi
  return 0
}
test_every_check_line_is_prefixed_or_known() { _assert_every_check_line_is_prefixed_or_known empty; }
test_every_check_line_is_prefixed_or_known_current() { _assert_every_check_line_is_prefixed_or_known current; }

test_no_action_line_contains_the_target_path() {
  # The contract is scoped to ACTION lines — the spec's own mode header
  # ("# CHECK mode ... target: <path>") legitimately carries the target
  # path as check-only enrichment, so this must check normalize()'d output,
  # not raw stdout, or it goes red the moment the header ships.
  local target
  target="$(new_instance empty)"
  run_install "$WORK/.out.tp" "$WORK/.err.tp" "$target" --check
  local normalized
  normalized="$(normalize <"$WORK/.out.tp")"
  if printf '%s\n' "$normalized" | grep -qF "$target"; then
    fail "an action line leaked the target path: $(printf '%s\n' "$normalized" | grep -F "$target" | tr '\n' ' ')"
    return 1
  fi
  return 0
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

echo "== pre-flight: git status of the kit repo (baseline; may show pre-existing dirt) =="
(cd "$KIT" && git status --porcelain) || true

echo "== pre-flight: kit repo manifest snapshot =="
KIT_BEFORE="$(kit_manifest "$KIT")"

echo "== safety rail self-check =="
selfcheck_sandbox_rm

echo "== building fixtures =="
build_fixture_empty
build_fixture_current
build_fixture_stale
build_fixture_divergent_settings
build_fixture_missing_kit_keys
build_fixture_invalid_json
build_fixture_partial
build_fixture_gitignore_crlf
build_fixture_gitignore_noeol

TESTS=(
  # parsing / usage
  test_unknown_flag_exits_1_and_writes_nothing
  test_unknown_flag_error_names_the_flag
  test_refuses_kit_repo_as_target
  test_check_and_link_compose

  # writes nothing
  test_check_writes_nothing_empty_target
  test_check_writes_nothing_gitignore_noeol_target
  test_check_never_writes_to_the_kit_repo

  # anti-drift: normalized stdout AND stderr equality, check vs real apply
  test_antidrift_empty_target
  test_antidrift_current_target
  test_antidrift_divergent_settings
  test_antidrift_missing_kit_keys
  test_antidrift_gitignore_crlf
  test_antidrift_gitignore_noeol
  test_antidrift_link_mode

  # exit codes
  test_exit_0_when_target_current
  test_exit_2_when_changes_pending
  test_apply_mode_still_exits_0
  test_midrun_abort_exits_3_and_says_partial
  test_check_mode_abort_says_nothing_was_written
  test_shadowed_find_does_not_falsely_abort

  # link-mode SKIP messaging
  test_link_check_skip_trailer_says_resolve_manually

  # the settings line (unpredictable line 1)
  test_no_false_warn_could_not_merge_on_empty_target
  test_no_python_traceback_on_stderr_empty_target
  test_predicts_merge_when_kit_keys_missing
  test_keep_settings_never_reported_as_overwrite
  test_merge_succeeds_when_python3_is_a_stub
  test_invalid_json_warns_about_json_not_python
  test_check_reports_incomplete_when_merge_prediction_fails
  test_exit_2_when_merge_prediction_incomplete

  # the gitignore line (unpredictable line 2) + the corruption bug
  test_gitignore_all_three_predicted_on_missing_file
  test_gitignore_does_not_corrupt_unterminated_last_line
  test_gitignore_converges_in_one_apply_run

  # stale reporting
  test_stale_entry_reported_and_not_counted_as_change

  # in-scope fixes and the output contract
  test_hooks_tree_installed_in_apply_mode
  test_enrichment_lines_are_check_only
  test_every_check_line_is_prefixed_or_known
  test_every_check_line_is_prefixed_or_known_current
  test_no_action_line_contains_the_target_path
)

echo "== running ${#TESTS[@]} tests =="
for t in "${TESTS[@]}"; do
  TEST_DETAIL=""
  if "$t"; then
    PASS_COUNT=$((PASS_COUNT + 1))
    printf 'PASS %s\n' "$t"
  else
    FAIL_COUNT=$((FAIL_COUNT + 1))
    printf 'FAIL %s: %s\n' "$t" "$TEST_DETAIL"
  fi
done

echo "== post-flight: kit repo manifest re-check =="
KIT_AFTER="$(kit_manifest "$KIT")"
KIT_DIFF="$(diff <(printf '%s\n' "$KIT_BEFORE") <(printf '%s\n' "$KIT_AFTER"))"
if [[ -z "$KIT_DIFF" ]]; then
  echo "SAFETY PASS  kit repo manifest unchanged"
else
  echo "SAFETY FAIL  kit repo manifest changed:"
  echo "$KIT_DIFF"
  FAIL_COUNT=$((FAIL_COUNT + 1))
fi

echo "$PASS_COUNT passed, $FAIL_COUNT failed"

sandbox_rm "$SCRATCH_ROOT"

if ((FAIL_COUNT > 0)); then
  exit 1
fi
exit 0
