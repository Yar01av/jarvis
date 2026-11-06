---
name: board
description: "Bring a /construct run's live board viewer back up and show it. Use when the user invokes /board, optionally with a run slug, e.g. because the board went offline or they want to watch a team."
argument-hint: "[run slug; default: the most recently updated run that isn't closed]"
disable-model-invocation: true
---

Show the board for: $ARGUMENTS

1. **Find the run.** Runs live in `<repo>/.claude/projects/construct/<slug>/`, where `<repo>` is the repo this session runs in.
   - If `$ARGUMENTS` names a slug, use it.
   - Otherwise pick the run whose `board.json` changed most recently and whose phase isn't `closed`. If every run is closed, take the most recent one and say it's closed.
2. **Start or reuse its viewer:**
   ```bash
   python "<repo>/.claude/skills/construct/board.py" serve "<run folder>"
   ```
   It prints the URL. It's idempotent: a viewer that is already up is reused on the same port, so an open canvas node or browser tab just recovers.
3. **Show it:**
   - If `NODETERM_NODE_ID` is set, run `sh "<nodeterm shim>" show-web --url <url>`. The shim path is in the manage-nodeterm-canvas skill.
   - Otherwise give the user the URL.
4. **Reply in one line:** the run, its phase, the URL, and the viewer's "Board" and "Graph" tabs. Don't touch the run otherwise: this skill only shows the board.

To stop a viewer: `python "<repo>/.claude/skills/construct/board.py" stop "<run folder>"`. It stays down until the next `serve`, here or from the lead. A closed run's viewer also stops itself about 10 minutes after closing.
