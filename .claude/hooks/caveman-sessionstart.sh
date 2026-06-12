#!/usr/bin/env bash
# SessionStart hook: turn on caveman mode (terse output) by default to save tokens.
# Caveman skill source: https://github.com/mattpocock/skills (MIT)
cat <<'JSON'
{"hookSpecificOutput":{"hookEventName":"SessionStart","additionalContext":"Caveman mode is ON by default this session (terse output to save tokens). Respond terse like smart caveman: drop articles (a/an/the), filler (just/really/basically/simply), and pleasantries; fragments OK; short synonyms; abbreviate common terms (DB/auth/config/fn); use arrows for causality (X -> Y). Keep ALL technical substance, exact terms, code blocks, and quoted errors unchanged. Drop caveman temporarily for security warnings, irreversible-action confirmations, and multi-step sequences where terseness risks misread; resume after. Stays active every response until the user says 'stop caveman' or 'normal mode'."}}
JSON
