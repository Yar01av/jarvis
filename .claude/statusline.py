#!/usr/bin/env python3
"""
Jarvis kit status line — Python port of statusline.sh (no jq dependency).

Renders: [bar] pct% ctx · in↑ out↓ [· 5h %] [· 7d %]
"""
import io
import json
import sys
import math

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

# ANSI
DIM    = "\033[2m"
RESET  = "\033[0m"
GREEN  = "\033[32m"
YELLOW = "\033[33m"
RED    = "\033[31m"

def color_for(pct):
    if pct < 60:  return GREEN
    if pct < 85:  return YELLOW
    return RED

def bar_for(pct):
    filled = min(10, math.floor(pct / 10))
    return "█" * filled + "░" * (10 - filled)

def humanize(n):
    if n >= 1_000_000: return f"{n/1_000_000:.1f}M"
    if n >= 1_000:     return f"{n/1_000:.1f}k"
    return str(n)

try:
    data = json.loads(sys.stdin.read())
except Exception:
    sys.exit(0)

cw = data.get("context_window", {})
rl = data.get("rate_limits", {})

ctx_pct = math.floor(cw.get("used_percentage") or 0)
in_tok  = cw.get("total_input_tokens") or 0
out_tok = cw.get("total_output_tokens") or 0

rl_5h = rl.get("five_hour", {}).get("used_percentage")
rl_7d = rl.get("seven_day", {}).get("used_percentage")

sep = f"{DIM} · {RESET}"
segments = []

c = color_for(ctx_pct)
segments.append(f"{c}{bar_for(ctx_pct)} {ctx_pct}% ctx{RESET}")
segments.append(f"{DIM}{humanize(in_tok)}↑ {humanize(out_tok)}↓{RESET}")

if rl_5h is not None:
    p = math.floor(rl_5h)
    segments.append(f"{color_for(p)}5h {p}%{RESET}")
if rl_7d is not None:
    p = math.floor(rl_7d)
    segments.append(f"{color_for(p)}7d {p}%{RESET}")

print(sep.join(segments), end="")
