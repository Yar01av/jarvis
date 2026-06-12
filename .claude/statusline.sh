#!/usr/bin/env bash
#
# Jarvis kit status line — usage tracker.
#
# Reads the status-line JSON Claude Code passes on stdin and renders a single
# line showing how much you've consumed this session:
#   - context window used (% + bar)
#   - input / output token counts
#   - rate-limit consumption (5-hour and 7-day windows, when available)
#
# Wired up via .claude/settings.json -> statusLine. Runs locally, costs no
# API tokens. Output goes to stdout; stderr is ignored by Claude Code.
#
# Test standalone:
#   echo '{"context_window":{"used_percentage":42.5,"total_input_tokens":85000,
#     "total_output_tokens":1200},"rate_limits":{"five_hour":{"used_percentage":23.5},
#     "seven_day":{"used_percentage":41.2}}}' | .claude/statusline.sh

set -euo pipefail

input="$(cat)"

# Bail out gracefully if jq is missing rather than spamming the status line.
if ! command -v jq >/dev/null 2>&1; then
  printf 'statusline: jq not found'
  exit 0
fi

# --- ANSI helpers -----------------------------------------------------------
DIM=$'\033[2m'; RESET=$'\033[0m'
GREEN=$'\033[32m'; YELLOW=$'\033[33m'; RED=$'\033[31m'

# Pick a color for a 0-100 percentage: green < 60, yellow < 85, red otherwise.
color_for() {
  local pct=$1
  if   [ "$pct" -lt 60 ]; then printf '%s' "$GREEN"
  elif [ "$pct" -lt 85 ]; then printf '%s' "$YELLOW"
  else                         printf '%s' "$RED"
  fi
}

# Render a 10-cell bar for a 0-100 percentage.
bar_for() {
  local pct=$1 filled i out=""
  filled=$(( pct / 10 ))
  [ "$filled" -gt 10 ] && filled=10
  for ((i = 0; i < 10; i++)); do
    if [ "$i" -lt "$filled" ]; then out+="█"; else out+="░"; fi
  done
  printf '%s' "$out"
}

# Compact a token count to a human form: 85000 -> 85.0k, 1500000 -> 1.5M.
humanize() {
  awk -v n="$1" 'BEGIN {
    if (n >= 1000000) printf "%.1fM", n/1000000;
    else if (n >= 1000) printf "%.1fk", n/1000;
    else printf "%d", n;
  }'
}

# --- Pull fields (defaults keep us quiet when a field is absent/null) -------
ctx_pct=$(jq -r '(.context_window.used_percentage // 0) | floor' <<<"$input")
in_tok=$(jq -r '.context_window.total_input_tokens // 0' <<<"$input")
out_tok=$(jq -r '.context_window.total_output_tokens // 0' <<<"$input")

# Rate limits are only present for Claude.ai Pro/Max sessions; -1 means absent.
rl_5h=$(jq -r '.rate_limits.five_hour.used_percentage // -1 | floor' <<<"$input")
rl_7d=$(jq -r '.rate_limits.seven_day.used_percentage // -1 | floor' <<<"$input")

# --- Build the line ---------------------------------------------------------
ctx_color=$(color_for "$ctx_pct")
ctx_bar=$(bar_for "$ctx_pct")
segments=()
segments+=("${ctx_color}${ctx_bar} ${ctx_pct}% ctx${RESET}")
segments+=("${DIM}$(humanize "$in_tok")↑ $(humanize "$out_tok")↓${RESET}")

if [ "$rl_5h" -ge 0 ]; then
  segments+=("$(color_for "$rl_5h")5h ${rl_5h}%${RESET}")
fi
if [ "$rl_7d" -ge 0 ]; then
  segments+=("$(color_for "$rl_7d")7d ${rl_7d}%${RESET}")
fi

# Join with a dim separator.
sep="${DIM} · ${RESET}"
line=""
for seg in "${segments[@]}"; do
  if [ -z "$line" ]; then line="$seg"; else line="${line}${sep}${seg}"; fi
done

printf '%s' "$line"
