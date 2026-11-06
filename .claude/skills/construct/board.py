"""Board tool for /construct: the only way to change a run's board.

RUN/board.json holds the state; every mutation re-renders RUN/board.md (read by
humans and agents) and RUN/board.html (live viewer, see `serve`).
"""
import argparse
import collections
import fnmatch
import functools
import os
import html
import http.client
import json
import re
import secrets
import shlex
import socket
import statistics
import subprocess
import sys
import tempfile
import threading
import time
from contextlib import contextmanager
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path, PurePosixPath, PureWindowsPath
from urllib.parse import urlsplit

LOCK_TIMEOUT = 10
REPLACE_ATTEMPTS = 20
REPLACE_DELAY = 0.05
PROGRESS_MAX_CHARS = 200
PROGRESS_KEEP = 20
HTML_LOG_LINES = 15
VIEWER_WATCH_SECONDS = 30
VIEWER_STOP_POLL_SECONDS = 1
VIEWER_CLOSED_GRACE_SECONDS = 600
VIEWER_START_WAIT = 3
VIEWER_STOP_WAIT = 5
VIEWER_HEAL_BACKOFF_SECONDS = 60
IDLE_GAP_MINUTES = 90
DEFAULT_ESTIMATE_MINUTES = 25
# Byte budgets for what every agent reads. Over budget only warns: `show` for these run files, `card` for a body.
READ_BUDGETS = {"rules.md": 5_000, "context.md": 8_000}
CARD_BUDGET = 4_000

PHASES = ["shaping", "running", "closed"]
ACCEPT_STATUSES = ["open", "met", "failed", "unverified"]
STATUSES = ["todo", "doing", "review", "done", "blocked", "dropped"]
ACTIVE = ("doing", "review")
SATISFIED = ("done", "dropped")
TIERS = ["sonnet", "opus", "fable", "haiku"]
EFFORTS = ["low", "medium", "high", "xhigh", "max"]
# Commands that change the board; each one heals a dead viewer afterwards.
MUTATING = {"set", "accept", "team", "card", "repo", "checkpoint", "merge", "move", "report", "progress",
            "log", "dispatch", "returned", "brief"}
ROLES = ["builder", "reviewer"]
KINDS = ["build", "question"]
SIZES = ["S", "M", "L"]
ROUTES = ["single", "lanes"]  # SKILL §0 Route first
REVIEWS = ["standard", "deep", "light", "none"]  # none: tests are the gate; the card is done when it's green
LADDER = ["sonnet", "opus", "fable"]
# SKILL §Tiers as data: size -> builder (tier, effort); review depth -> reviewer (tier, effort, budget line).
BUILD_POLICY = {"S": ("sonnet", "medium"), "M": ("opus", "medium"), "L": ("opus", "high")}
REVIEW_POLICY = {"standard": ("opus", "medium", "at most ~25 tool calls"), "deep": ("opus", "high", "uncapped"),
                 "light": ("sonnet", "low", "at most ~8 tool calls")}
GATE_TIMEOUT = 300
TOOL_SILENT_MINUTES = 20  # a foreground command is capped at 10 min, so 20 is no longer a command
GATE_TAIL_LINES = 40

# (from, to) -> (counter to bump or None, what happens to `since`: "now" | "clear")
TRANSITIONS = {
    ("todo", "doing"): ("tries", "now"),
    ("doing", "review"): (None, "now"),
    ("doing", "todo"): (None, "clear"),
    ("review", "todo"): ("bounces", "clear"),
    ("review", "done"): (None, "clear"),
    ("doing", "done"): (None, "clear"),  # a --review none card whose gate is green
    ("doing", "blocked"): (None, "clear"),
    ("review", "blocked"): (None, "clear"),
    ("blocked", "todo"): (None, "clear"),
    ("todo", "dropped"): (None, "clear"),
    ("blocked", "dropped"): (None, "clear"),
}


def now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def hhmm(t: str) -> str:
    return datetime.fromisoformat(t).strftime("%H:%M")


def elapsed_seconds(t: str) -> int:
    return max(0, int((datetime.now().astimezone() - datetime.fromisoformat(t)).total_seconds()))


def fmt_elapsed(seconds: int) -> str:
    minutes = seconds // 60
    if seconds < 3600:
        return f"{minutes}m {seconds % 60}s"
    if minutes < 1440:
        return f"{minutes // 60}h {minutes % 60}m"
    return f"{minutes // 1440}d {minutes % 1440 // 60}h"


# ---------------------------------------------------------------- state / lock

def board_path(run: Path) -> Path:
    return run / "board.json"


def read_retry(path: Path) -> str:
    # On Windows, reading fails with PermissionError while a writer is replacing the file.
    for attempt in range(REPLACE_ATTEMPTS):
        try:
            return path.read_text(encoding="utf-8")
        except PermissionError:
            if attempt == REPLACE_ATTEMPTS - 1:
                raise
            time.sleep(REPLACE_DELAY)


def replace_retry(tmp: Path, target: Path) -> None:
    # On Windows, replace fails with PermissionError while a reader holds the target open.
    for attempt in range(REPLACE_ATTEMPTS):
        try:
            tmp.replace(target)
            return
        except PermissionError:
            if attempt == REPLACE_ATTEMPTS - 1:
                raise
            time.sleep(REPLACE_DELAY)


def write_atomic(path: Path, text: str) -> None:
    """Write-then-replace so a reader never sees a half-written file."""
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    replace_retry(tmp, path)


def load(run: Path) -> dict:
    path = board_path(run)
    if not path.exists():
        raise SystemExit(f"no board at {path}; run `init` first")
    state = json.loads(read_retry(path))
    state.setdefault("repos", [])
    state.setdefault("route", None)
    for repo in state["repos"]:
        repo.setdefault("merges", [])
    for card in state["cards"]:
        card.setdefault("kind", "build")
        card.setdefault("repo", None)
        card.setdefault("resources", [])
        card.setdefault("estimate", None)
        card.setdefault("dispatches", [])
        card.setdefault("size", None)
        card.setdefault("review", None)
        card.setdefault("bump", 0)
        card.setdefault("lane", None)
        card["held"] = [[card["repo"], h] if isinstance(h, str) else h for h in card.get("held", [])]
    return state


def save(run: Path, state: dict) -> None:
    write_atomic(board_path(run), json.dumps(state, indent=2, ensure_ascii=False))


@contextmanager
def locked(run: Path):
    lock = run / "board.lock"
    deadline = time.monotonic() + LOCK_TIMEOUT
    while True:
        try:
            f = lock.open("x", encoding="utf-8")
            try:
                f.write(f"pid={os.getpid()} since={now()}")
            except BaseException:
                f.close()
                lock.unlink()
                raise
            f.close()
            break
        except FileExistsError:
            if time.monotonic() >= deadline:
                try:
                    holder = lock.read_text(encoding="utf-8").strip()
                except FileNotFoundError:
                    continue  # the holder released it just now; take it
                raise SystemExit(f"board locked: {lock} still exists after {LOCK_TIMEOUT}s "
                                 f"({holder}); if that process is gone, delete board.lock")
            time.sleep(0.1)
    try:
        yield
    finally:
        lock.unlink()


def finish(run: Path, state: dict) -> None:
    state["updated"] = now()
    save(run, state)
    write_atomic(run / "board.md", render_md(state))
    write_atomic(run / "board.html", render_html(state, lessons_count(run)))


def mutate(run: Path, fn) -> None:
    """lock -> load -> fn(state) -> updated -> save -> render -> unlock."""
    with locked(run):
        state = load(run)
        lines = fn(state)
        finish(run, state)
    for line in lines or []:
        print(line)


def find_card(state: dict, cid: str) -> dict:
    for card in state["cards"]:
        if card["id"] == cid:
            return card
    raise SystemExit(f"unknown card {cid}")


def log_entry(state, who, why, card=None, frm=None, to=None) -> None:
    state["log"].append({"t": now(), "card": card, "from": frm, "to": to, "who": who, "why": why})


def card_num(card: dict) -> int:
    return int(card["id"][1:])


# ------------------------------------------------------------------- eligibility

def porcelain_paths(repo: Path, files: list[str]) -> list[str]:
    out = subprocess.run(["git", "--no-optional-locks", "--literal-pathspecs", "-C", str(repo), "status", "--porcelain", "-z",
                          "-uall", "--", *files], capture_output=True, check=True).stdout.decode("utf-8")
    records = out.split("\0")
    paths, i = [], 0
    while i < len(records) and records[i]:
        xy, path = records[i][:2], records[i][3:]
        paths.append(path)
        i += 1
        if "R" in xy or "C" in xy:  # the old path follows as its own record
            paths.append(records[i])
            i += 1
    return paths


def overlaps(a: str, b: str) -> bool:
    """Same file, or one entry lies inside the other (a directory listed as a file-set entry)."""
    return a == b or a.startswith(b + "/") or b.startswith(a + "/")


def repo_of(state: dict, name: str) -> dict:
    found = next((r for r in state["repos"] if r["name"] == name), None)
    if found is None:
        raise SystemExit(f"unknown repo {name}; register it with `repo` first")
    return found


def card_pairs(card: dict, files=None) -> set[tuple[str, str]]:
    return {(card["repo"], f) for f in (card["files"] if files is None else files)}


def held_pairs(card: dict) -> set[tuple[str, str]]:
    return {(r, f) for r, f in card.get("held", [])}


def needs_repo(card: dict) -> str | None:
    if card["files"] and card["repo"] is None:
        return f"{card['id']} has files but no repo; run `card --update --repo NAME`"
    return None


def blocker(state: dict, card: dict, picked_files: set[tuple[str, str]], picked_res: dict[str, str]) -> str | None:
    """Why this todo card cannot start now, or None when it is eligible."""
    by_id = {c["id"]: c for c in state["cards"]}
    # A build card may build on a build dep that is in review (its gate is green): the review runs alongside.
    # Question cards, e.g. the integration review, wait for done.
    waiting = [d for d in card["deps"] if by_id[d]["status"] not in SATISFIED
               and not (by_id[d]["status"] == "review" and by_id[d]["kind"] == card["kind"] == "build")]
    if waiting:
        return f"waits on {', '.join(waiting)}"
    if needs_repo(card):
        return needs_repo(card)
    active = [c for c in state["cards"] if c["status"] in ACTIVE]
    busy = [(c["repo"], f, c["id"]) for c in active for f in c["files"]]
    for f in card["files"]:
        holder = next((cid for r, g, cid in busy if r == card["repo"] and overlaps(f, g)), None)
        if holder:
            return f"file {f} is in use by {holder}"
        if any(r == card["repo"] and overlaps(f, g) for r, g in picked_files):
            return f"file {f} overlaps another card in this batch"
    for res in card["resources"]:
        holder = next((c["id"] for c in active if res in c["resources"]), None) or picked_res.get(res)
        if holder:
            return f"resource {res} is in use by {holder}"
    if card["repo"] is not None:
        entry = repo_of(state, card["repo"])
        if entry["branch"] is not None:
            current = git_ok(entry["path"], "branch", "--show-current") or "detached HEAD"
            if current != entry["branch"]:
                return f"repo {entry['name']} is on {current}, not {entry['branch']}"
        owned = {(c["repo"], f) for c in state["cards"] if c["status"] == "done" for f in c["files"]}
        # Files this card held in an earlier attempt may be dirty from its own half-edit, unless
        # another unfinished card also held them.
        others_held = set().union(*(held_pairs(c) for c in state["cards"]
                                    if c["id"] != card["id"] and c["status"] not in SATISFIED))
        own = (held_pairs(card) & card_pairs(card)) - others_held
        dirty = [p for p in porcelain_paths(Path(entry["path"]), card["files"])
                 if not any(r == card["repo"] and overlaps(p, g) for r, g in owned)
                 and (card["repo"], p) not in own]
        stray = [p for p in dirty if p not in card["files"]]
        if stray:
            entries = [f for f in card["files"] if stray[0].startswith(f + "/")] or card["files"]
            return f"file-set entry {', '.join(entries)} matches {stray[0]}; list concrete files"
        if dirty:
            return f"has uncommitted changes outside done cards: {', '.join(dirty)}"
    return None


def free_slots(state: dict) -> int:
    return state["limit"] - sum(1 for c in state["cards"] if c["status"] == "doing")


def eligible_ids(state: dict) -> tuple[list[str], list[str]]:
    """(ids to start now, one "<id> skipped: <reason>" line per todo card left out)."""
    picked_ids, picked_files, picked_res, skipped = [], set(), {}, []
    slots = free_slots(state)
    for card in sorted((c for c in state["cards"] if c["status"] == "todo"), key=card_num):
        if len(picked_ids) >= slots:
            skipped.append(f"{card['id']} skipped: parallel limit {state['limit']} reached")
            continue
        why = blocker(state, card, picked_files, picked_res)
        if why is None:
            picked_ids.append(card["id"])
            picked_files |= card_pairs(card)
            picked_res.update({res: card["id"] for res in card["resources"]})
        else:
            skipped.append(f"{card['id']} skipped: {why}")
    return picked_ids, skipped


# --------------------------------------------------------------------- commands

def cmd_init(args) -> None:
    run = args.run
    if board_path(run).exists():
        raise SystemExit(f"{board_path(run)} already exists")
    for sub in ("cards", "reports", "out"):
        (run / sub).mkdir(parents=True, exist_ok=True)
    with locked(run):
        state = {"title": args.title, "slug": run.name, "route": args.route, "phase": "shaping", "limit": args.limit,
                 "goal": "", "updated": now(), "acceptance": [], "team": [], "repos": [], "cards": [], "log": []}
        finish(run, state)
    if args.route == "lanes":
        print("route lanes: only when the user asked for lanes (SKILL §0 Route first); otherwise --route single",
              file=sys.stderr)


def valid_clock(text: str) -> bool:
    if re.fullmatch(r"\d{1,2}:\d\d", text):
        hour, minute = map(int, text.split(":"))
        return hour < 24 and minute < 60
    try:
        datetime.fromisoformat(text)
    except ValueError:
        return False
    return True


def cmd_set(args) -> None:
    fields = ("goal", "phase", "limit", "next_input", "next_input_at", "availability")
    if all(getattr(args, f) is None for f in fields):
        raise SystemExit("set: give at least one of --goal, --phase, --limit, "
                         "--next-input, --next-input-at, --availability")
    if args.next_input_at and not valid_clock(args.next_input_at):
        raise SystemExit(f"set: --next-input-at {args.next_input_at!r} must be HH:MM or an ISO time")

    def fn(state):
        for f in fields:
            if getattr(args, f) is not None:
                state[f] = getattr(args, f)
    mutate(args.run, fn)


def cmd_accept(args) -> None:
    if args.status and not args.why:
        raise SystemExit("accept: --status needs --why")

    def fn(state):
        item = next((a for a in state["acceptance"] if a["id"] == args.id), None)
        if item is None:
            if not args.text:
                raise SystemExit(f"accept: unknown id {args.id}; a new item needs --text")
            item = {"id": args.id, "text": args.text, "side_effect": False, "status": "open", "why": ""}
            state["acceptance"].append(item)
        elif args.text:
            item["text"] = args.text
        if args.side_effect:
            item["side_effect"] = True
        if args.status:
            item["status"] = args.status
            item["why"] = args.why
    mutate(args.run, fn)


def cmd_team(args) -> None:
    def fn(state):
        if any(t["agent"] == args.agent and t["role"] == args.role for t in state["team"]):
            raise SystemExit(f"team: {args.agent} is already on the team as {args.role}")
        state["team"].append({"agent": args.agent, "role": args.role, "tier": args.tier})
    mutate(args.run, fn)


def dep_cycle(state: dict, cid: str, deps: list[str]) -> list[str] | None:
    """The path cid→...→cid if giving `cid` these deps closes a loop, else None."""
    graph = {c["id"]: c["deps"] for c in state["cards"]}
    graph[cid] = deps

    def walk(node: str, path: list[str]) -> list[str] | None:
        for dep in graph[node]:
            if dep == cid:
                return path + [cid]
            if dep not in path:
                found = walk(dep, path + [dep])
                if found:
                    return found
        return None
    return walk(cid, [cid])


def cmd_card(args) -> None:
    if not re.fullmatch(r"C\d+", args.id):
        raise SystemExit(f"card: id {args.id} must match C<number>")
    if not args.update:
        for flag in ("title", "builder", "reviewer", "body_file"):
            if getattr(args, flag) is None:
                raise SystemExit(f"card: --{flag.replace('_', '-')} is required without --update")
    if args.update and all(getattr(args, f) is None for f in
                           ("title", "builder", "reviewer", "files", "deps", "body_file",
                            "repo", "kind", "resources", "estimate", "size", "review", "lane")):
        raise SystemExit(f"card: nothing to update for {args.id}; give at least one field")
    for entry in args.files or []:
        if entry.endswith(("/", "\\")):
            raise SystemExit(f"card: file set entries must be concrete files, not directories: {entry}")
        posix = entry.replace("\\", "/")
        if PurePosixPath(posix).is_absolute() or PureWindowsPath(entry).is_absolute() or ".." in posix.split("/"):
            raise SystemExit(f"card: file set entries must be relative paths inside the repo: {entry}")
    body = args.body_file.read_text(encoding="utf-8") if args.body_file else None
    final = {}

    def fn(state):
        existing = next((c for c in state["cards"] if c["id"] == args.id), None)
        if args.update:
            if existing is None:
                raise SystemExit(f"unknown card {args.id}")
            if existing["status"] not in ("todo", "blocked"):
                raise SystemExit(f"card: {args.id} is {existing['status']}; "
                                 "only todo or blocked cards can be updated")
        elif existing is not None:
            raise SystemExit(f"card: {args.id} already exists")
        base = existing or {}
        builder = args.builder or base.get("builder")
        reviewer = args.reviewer or base.get("reviewer")
        for agent, role in ((builder, "builder"), (reviewer, "reviewer")):
            if not (role == "builder" and agent == "lead") and not any(t["agent"] == agent and t["role"] == role for t in state["team"]):
                raise SystemExit(f"card: {agent} is not on the team as {role}")
        if builder == reviewer:
            raise SystemExit(f"card: builder and reviewer must differ (both {builder})")
        deps = args.deps if args.deps is not None else base.get("deps", [])
        known = {c["id"] for c in state["cards"]}
        for dep in deps:
            if dep not in known:
                raise SystemExit(f"card: unknown dep {dep}")
        cycle = dep_cycle(state, args.id, deps)
        if cycle:
            raise SystemExit(f"card: deps would create a cycle {'→'.join(cycle)}")
        kind = args.kind or base.get("kind", "build")
        files = [Path(f).as_posix() for f in args.files] if args.files else base.get("files", [])
        repo = args.repo if args.repo is not None else base.get("repo")
        if kind == "question":
            if args.files:
                raise SystemExit(f"card: {args.id} is a question card; question cards have no files")
            if args.repo is not None:
                raise SystemExit(f"card: {args.id} is a question card; question cards have no repo")
            files, repo = [], None
        resources = args.resources if args.resources is not None else base.get("resources", [])
        if kind == "build":
            # A build card without files is an action on a shared runtime (sync a stand, run live jobs).
            if not files and (repo is not None or not resources):
                raise SystemExit(f"card: {args.id} is a build card; --files is required, or with no --repo and "
                                 f"no files at least one --resources (an action on a shared runtime)")
            if files and repo is None:
                raise SystemExit(f"card: {args.id} has files; --repo NAME is required")
            if repo is not None and not any(r["name"] == repo for r in state["repos"]):
                raise SystemExit(f"card: unknown repo {repo}; register it with `repo` first")
        if body is not None:
            (args.run / "cards" / f"{args.id}.md").write_text(body, encoding="utf-8")
        estimate = args.estimate if args.estimate is not None else base.get("estimate")
        fields = {"title": args.title or base.get("title"), "kind": kind, "deps": deps, "repo": repo,
                  "files": files, "resources": resources, "builder": builder, "reviewer": reviewer,
                  "estimate": estimate, "size": args.size or base.get("size"),
                  "review": args.review or base.get("review"), "lane": args.lane or base.get("lane")}
        if existing is None:
            state["cards"].append({"id": args.id, "status": "todo", **fields, "tries": 0, "bounces": 0,
                                   "bump": 0, "since": None, "reports": [], "progress": [],
                                   "dispatches": []})
        else:
            existing.update(fields)
            log_entry(state, "lead", f"card {args.id} updated", args.id)
        final["deps"] = deps
    mutate(args.run, fn)
    if body is not None:
        unlisted = sorted(cited_cards(body) - set(final["deps"]) - {args.id}, key=lambda c: int(c[1:]))
        if unlisted:
            print(f"card: {args.id}'s body cites {', '.join(unlisted)} but its deps don't list them, so "
                  f"`handoff` won't show them; add them to --deps if {args.id} builds on their result",
                  file=sys.stderr)
        size = len(body.encode("utf-8"))
        if size > CARD_BUDGET:
            print(f"card: {args.id}'s body is {size:,} bytes, over its {CARD_BUDGET:,} budget; keep the spec, and "
                  f"move what other cards share into rules/<topic>.md and other cards' results into their Handoff",
                  file=sys.stderr)


CITED_REPORT = re.compile(r"reports[/\\](C\d+)-(?:build|review)-\d+\.md|\b(C\d+)'s (?:report|review|answer|verdict)")


def cited_cards(body: str) -> set[str]:
    """Cards whose report a card body points at, by path or as "C2's report"."""
    return {a or b for a, b in CITED_REPORT.findall(body)}


def git_run(repo: Path | str, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "--no-optional-locks", "--literal-pathspecs", "-C", str(repo), *args],
                          capture_output=True, text=True, encoding="utf-8")


def git_ok(repo: Path | str, *args: str) -> str:
    done = git_run(repo, *args)
    if done.returncode != 0:
        raise SystemExit(f"git {' '.join(args[:2])} failed in {repo}: "
                         f"{(done.stderr + done.stdout).strip()}")
    return done.stdout.strip()


def cmd_repo(args) -> None:
    path = args.path.resolve()
    top = git_run(path, "rev-parse", "--show-toplevel")
    if top.returncode != 0 or Path(top.stdout.strip()).resolve() != path:
        raise SystemExit(f"repo: {path} is not a git repo (or not its root)")
    current = git_ok(path, "branch", "--show-current")
    if not current:
        raise SystemExit(f"repo: HEAD is detached in {path}; check out a branch first")

    def fn(state):
        name = path.name
        if any(r["name"] == name or r["path"] == path.as_posix() for r in state["repos"]):
            raise SystemExit(f"repo: {name} is already registered")
        branch = None if args.no_branch else f"construct/{state['slug']}"
        base = git_ok(path, "rev-parse", "HEAD")
        dirt = git_run(path, "status", "--porcelain").stdout.splitlines()
        if branch:
            if git_run(path, "rev-parse", "--verify", "-q", f"refs/heads/{branch}").returncode == 0:
                raise SystemExit(f"repo: branch {branch} already exists in {name}")
            git_ok(path, "switch", "-c", branch)
        state["repos"].append({"path": path.as_posix(), "name": name, "original_branch": current,
                               "base": base, "branch": branch, "gate": args.gate, "gate_glob": args.gate_glob})
        carried = f", {len(dirt)} uncommitted paths carried over" if dirt and branch else ""
        log_entry(state, "lead", f"repo {name} registered at {base[:7]}"
                  + (f", branch {branch}" if branch else ", no branch") + carried)
        if dirt and branch:
            return ["these uncommitted changes move to the run branch:", *dirt]
    mutate(args.run, fn)


def cmd_checkpoint(args) -> None:
    def fn(state):
        return [do_checkpoint(state, find_card(state, args.id))]
    mutate(args.run, fn)


def do_checkpoint(state: dict, card: dict) -> str:
    """Commit exactly the card's files on its repo's run branch; the sha."""
    if card["kind"] == "question":
        raise SystemExit(f"checkpoint: {card['id']} is a question card; question cards are never checkpointed")
    if not card["files"]:
        raise SystemExit(f"checkpoint: {card['id']} has no files: nothing to commit; "
                         "move it done after its review PASS")
    # A --review none card is committed on its green gate, straight from doing; any other after a PASS review.
    stage, kind, verdict = ("doing", "build", "DONE") if review_depth(card) == "none" else ("review", "review", "PASS")
    if card["status"] != stage:
        raise SystemExit(f"checkpoint: {card['id']} needs a card in {stage}; it is {card['status']}")
    if needs_repo(card):
        raise SystemExit(f"checkpoint: {needs_repo(card)}")
    last = card["reports"][-1] if card["reports"] else None
    if last is None or last["name"] != f"{kind}-{card['tries']}" or not last["verdict"].startswith(verdict):
        shown = f"{last['name']} {last['verdict']}" if last else "none"
        raise SystemExit(f"checkpoint: {card['id']} needs a {verdict} {kind}-{card['tries']} as its last "
                         f"report; last report: {shown}")
    if card.get("commit"):
        raise SystemExit(f"checkpoint: {card['id']} is already committed as {card['commit'][:7]}")
    repo = repo_of(state, card["repo"])
    if repo["branch"] is None:
        raise SystemExit(f"checkpoint: no-branch repo {repo['name']}: changes stay uncommitted by design")
    current = git_ok(repo["path"], "branch", "--show-current")
    if current != repo["branch"]:
        raise SystemExit(f"checkpoint: {repo['name']} is on branch {current or 'detached HEAD'}, "
                         f"expected {repo['branch']}")
    paths = list(dict.fromkeys(porcelain_paths(Path(repo["path"]), card["files"])))
    if not paths:
        raise SystemExit(f"checkpoint: nothing changed in {', '.join(card['files'])}")
    git_ok(repo["path"], "add", "--", *paths)
    git_ok(repo["path"], "commit", "-m", f"construct({state['slug']}): {card['id']} {flat(card['title'])}",
           "-m", "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>", "--", *paths)
    sha = git_ok(repo["path"], "rev-parse", "HEAD")
    changed = [x for x in git_run(repo["path"], "diff-tree", "--no-commit-id", "--name-only", "-r", "-z",
                                  sha).stdout.split("\0") if x]
    outside = [x for x in changed if not any(overlaps(x, f) for f in card["files"])]
    left = porcelain_paths(Path(repo["path"]), card["files"])
    problems = []
    if outside:
        problems.append(f"it contains paths outside the card's files: {', '.join(outside)}")
    if left:
        problems.append(f"the card's files are still uncommitted: {', '.join(left)}")
    if problems:
        raise SystemExit(f"checkpoint: commit {sha[:7]} made but not recorded: {'; '.join(problems)}")
    card["commit"] = sha
    log_entry(state, "lead", f"checkpoint {sha[:7]}", card["id"])
    return sha


CONFLICT_MARKER = re.compile(rb"^(<<<<<<< |>>>>>>> |=======\r?$)", re.M)


def unmerged_paths(path: str) -> list[str]:
    return [x for x in git_run(path, "diff", "--name-only", "--diff-filter=U", "-z").stdout.split("\0") if x]


def abort_merge(path: str, why: str) -> None:
    git_ok(path, "merge", "--abort")
    raise SystemExit(why)


def cmd_merge(args) -> None:
    def fn(state):
        repo = repo_of(state, args.repo)
        path, branch = repo["path"], repo["branch"]
        if branch is None:
            raise SystemExit(f"merge: no-branch repo {repo['name']}: the run never commits there")
        current = git_ok(path, "branch", "--show-current")
        if current != branch:
            raise SystemExit(f"merge: {repo['name']} is on branch {current or 'detached HEAD'}, expected {branch}")
        dirty = porcelain_paths(Path(path), [])
        if dirty:
            raise SystemExit(f"merge: {repo['name']} has uncommitted changes: {', '.join(dirty)}")
        found = git_run(path, "rev-parse", "--verify", "-q", f"{args.ref}^{{commit}}")
        if found.returncode != 0:
            raise SystemExit(f"merge: ref {args.ref} does not resolve to a commit in {repo['name']}")
        ref_sha, pre = found.stdout.strip(), git_ok(path, "rev-parse", "HEAD")
        if git_run(path, "merge-base", "--is-ancestor", ref_sha, pre).returncode == 0:
            raise SystemExit(f"merge: {branch} already contains {args.ref} ({ref_sha[:7]})")
        ours_from = git_ok(path, "merge-base", pre, ref_sha)
        done = git_run(path, "merge", "--no-ff", "--no-commit", ref_sha)
        conflicted = unmerged_paths(path)
        if done.returncode != 0 and not conflicted:
            if git_run(path, "rev-parse", "-q", "--verify", "MERGE_HEAD").returncode == 0:
                git_ok(path, "merge", "--abort")
            raise SystemExit(f"merge: git merge failed in {repo['name']}: {(done.stderr + done.stdout).strip()}")
        if conflicted and args.conflicts != "theirs":
            abort_merge(path, f"merge: {args.ref} conflicts in {repo['name']} at {', '.join(conflicted)}; merge "
                              f"aborted, nothing changed. Rerun with --conflicts theirs to take {args.ref}'s whole "
                              f"file at those paths, then let cards re-apply our side")
        for p in conflicted:
            stages = git_ok(path, "ls-files", "-u", "--", p).splitlines()
            if any(line.split()[2] == "3" for line in stages):
                git_ok(path, "checkout", "--theirs", "--", p)
                git_ok(path, "add", "--", p)
            else:  # the ref deleted it
                git_ok(path, "rm", "-q", "--", p)
        left = unmerged_paths(path)
        if left:
            abort_merge(path, f"merge: still unmerged after taking {args.ref}'s side: {', '.join(left)}; "
                              "merge aborted, nothing changed")
        marked = [p for p in conflicted if (Path(path) / p).is_file()
                  and CONFLICT_MARKER.search((Path(path) / p).read_bytes())]
        if marked:
            abort_merge(path, f"merge: a conflict marker line is left in {', '.join(marked)}; merge aborted, "
                              "nothing changed")
        message = ["-m", f"construct({state['slug']}): merge {args.ref} ({ref_sha[:7]})"]
        if conflicted:
            listing = "\n".join(f"- {p}" for p in conflicted)
            message += ["-m", f"These paths took {args.ref}'s whole file; cards re-apply our side from "
                              f"`git diff {ours_from} {pre} -- <path>`:\n{listing}"]
        message += ["-m", "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"]
        commit = git_run(path, "commit", *message)
        if commit.returncode != 0:
            abort_merge(path, f"merge: git commit failed in {repo['name']}, merge aborted: "
                              f"{(commit.stderr + commit.stdout).strip()}")
        sha = git_ok(path, "rev-parse", "HEAD")
        second = git_run(path, "rev-parse", "-q", "--verify", f"{sha}^2").stdout.strip()
        if second != ref_sha:
            raise SystemExit(f"merge: commit {sha[:7]} made but not recorded: its second parent is "
                             f"{second[:7] or 'missing'}, not {args.ref} ({ref_sha[:7]})")
        repo["merges"].append({"sha": sha, "ref": args.ref, "ref_sha": ref_sha, "whole_file_from_ref": conflicted})
        whole = f", {len(conflicted)} paths took its whole file" if conflicted else ""
        log_entry(state, "lead", f"merge {args.ref} ({ref_sha[:7]}) into {repo['name']} as {sha[:7]}{whole}")
        return [sha, *([f"took {args.ref}'s whole file, cards re-apply our side "
                        f"(git diff {ours_from} {pre} -- <path>):", *conflicted] if conflicted else [])]
    mutate(args.run, fn)


def owner_entries(state: dict, name: str) -> list[tuple[str, str]]:
    """(entry, label) for what the run's cards own in a repo: done cards' files, others' held files."""
    out = []
    for c in sorted(state["cards"], key=card_num):
        entries = card_pairs(c) if c["status"] == "done" else held_pairs(c)
        out += [(f, f"{c['id']} {c['status']}") for r, f in sorted(entries) if r == name]
    return out


def label_of(entries: list[tuple[str, str]], path: str) -> str:
    return ", ".join(dict.fromkeys(lab for f, lab in entries if overlaps(path, f))) or "no card"


def tracked(path: str, files: list[str]) -> list[str]:
    return [x for x in git_run(path, "ls-files", "-z", "--", *files).stdout.split("\0") if x]


def dropped_label(card: dict) -> str:
    return " (dropped)" if card["status"] == "dropped" else ""


def cmd_rollback(args) -> None:
    state = load(args.run)
    print("rollback plan (nothing is executed; run the commands yourself)")
    for repo in state["repos"]:
        path = repo["path"]
        where = f'git -C "{path}"'
        entries = owner_entries(state, repo["name"])
        print(f"\nrepo {repo['name']} ({path})")
        if repo["branch"] is None:
            print(f"  no-branch repo, base {repo['base']}; the run's edits are uncommitted")
            dirty = porcelain_paths(Path(path), [f for f, _ in entries]) if entries else []
            if not dirty:
                print("  no uncommitted edits in the cards' files")
                continue
            for d in dirty:
                print(f"  uncommitted: {d} ({label_of(entries, d)})")
            files = " ".join(shlex.quote(f) for f, _ in entries)
            print(f"  see what changed: {where} status --porcelain -- {files}")
            known = set(tracked(path, dirty))
            old = [d for d in dirty if d in known]
            new = [d for d in dirty if d not in known]
            if old:
                print("  optional undo of edits to tracked files, discards those edits:")
                print(f"  {where} checkout -- {' '.join(shlex.quote(d) for d in old)}")
            if new:
                joined = " ".join(shlex.quote(d) for d in new)
                print("  new files: preview what would be removed:")
                print(f"  {where} clean -n -- {joined}")
                print("  optional undo of new files, deletes these new files:")
                print(f"  {where} clean -f -- {joined}")
            continue
        branch, original = repo["branch"], repo["original_branch"]
        if git_run(path, "rev-parse", "--verify", "-q", f"refs/heads/{branch}").returncode != 0:
            print(f"  run branch {branch} already gone")
            continue
        shas = git_ok(path, "rev-list", f"{repo['base']}..{branch}").split()
        print(f"  base {repo['base']}, run branch {branch}, original branch {original}")
        print(f"  {len(shas)} commit{'' if len(shas) == 1 else 's'} on the run branch since base")
        commits = [c for c in sorted(state["cards"], key=card_num) if c["repo"] == repo["name"] and c.get("commit")]
        for c in commits:
            print(f"  card commit {c['commit'][:7]} {c['id']} {flat(c['title'])}{dropped_label(c)}")
        merges = repo["merges"]
        for m in merges:
            brought = git_ok(path, "rev-list", "--count", f"{m['sha']}^1..{m['ref_sha']}")
            print(f"  merged in {m['ref']} at {m['sha'][:7]} ({brought} commit{'' if brought == '1' else 's'})")
        # Commits reachable from a recorded merge's ref came in with that merge; they are not foreign.
        ours = git_ok(path, "rev-list", f"{repo['base']}..{branch}", "--not", *(m["ref_sha"] for m in merges)).split()
        recorded = {c["commit"] for c in commits} | {m["sha"] for m in merges}
        extra = [x for x in ours if x not in recorded]
        if extra:
            print("  not from this run:")
            for x in extra:
                print(f"  {git_ok(path, 'log', '-1', '--format=%h %s', x)}")
            print("  keep them: the branch is renamed instead of deleted; cherry-pick what you want to keep")
            print("  discard the run branch:")
            print(f"  {where} switch {shlex.quote(original)}")
            print(f"  {where} branch -m {shlex.quote(branch)} {shlex.quote(branch + '-discarded')}")
        else:
            print("  discard the whole run:")
            print(f"  {where} switch {shlex.quote(original)}")
            print(f"  {where} branch -D {shlex.quote(branch)}")
        if commits:
            print("  or undo a single card:")
            for c in commits:
                print(f"  {where} revert {c['commit']}")
        for m in merges:
            print(f"  or undo the merge of {m['ref']} (later cards may build on it):")
            print(f"  {where} revert -m 1 {m['sha']}")
        dirty = porcelain_paths(Path(path), [])
        if dirty:
            print(f"  warning: {repo['name']} has uncommitted changes; they would travel with the switch")
            for d in dirty:
                print(f"  uncommitted: {d} ({label_of(entries, d)})")


def dirty_held(state: dict, card: dict) -> list[str]:
    """Paths among the card's held files that are dirty in their repo and not owned by a done card."""
    owned = {(c["repo"], f) for c in state["cards"] if c["status"] == "done" for f in c["files"]}
    dirty = []
    for name in sorted({r for r, _ in held_pairs(card)}):
        files = sorted(f for r, f in held_pairs(card) if r == name)
        repo = repo_of(state, name)
        try:
            found = porcelain_paths(Path(repo["path"]), files)
        except subprocess.CalledProcessError as e:
            raise SystemExit(f"{card['id']} cannot be dropped: git failed in repo {name} ({repo['path']}): "
                             f"{flat(e.stderr.decode('utf-8', 'replace').strip())}") from None
        dirty += [d for d in found if not any(r == name and overlaps(d, g) for r, g in owned)]
    return dirty


def cmd_move(args) -> None:
    if (args.tier or args.effort) and args.status not in ACTIVE:
        raise SystemExit(f"move: --tier and --effort record a dispatch; they go with doing or review, "
                         f"not {args.status}")
    dependents = []

    def fn(state):
        dependents.extend(do_move(state, find_card(state, args.id), args.status, args.who, args.why,
                                  args.tier, args.effort))
    mutate(args.run, fn)
    if dependents:
        print(f"re-check dependents: {', '.join(dependents)}", file=sys.stderr)


def do_move(state: dict, card: dict, to: str, who: str, why: str, tier=None, effort=None) -> list[str]:
    """One status change with all its checks; for a drop, the dependents to re-check."""
    frm = card["status"]
    if (frm, to) not in TRANSITIONS:
        raise SystemExit(f"illegal transition {frm}→{to} for {card['id']}")
    counter, since = TRANSITIONS[(frm, to)]
    if to == "doing":
        if free_slots(state) <= 0:
            raise SystemExit(f"{card['id']} cannot start: parallel limit {state['limit']} reached")
        blocked_by = blocker(state, card, set(), {})
        if blocked_by:
            raise SystemExit(f"{card['id']} cannot start: {blocked_by}")
    if to == "dropped":
        dirty = dirty_held(state, card)
        if dirty:
            raise SystemExit(f"{card['id']} cannot be dropped: restore {card['id']}'s files first: "
                             f"{', '.join(dirty)}")
    if to == "doing":
        card["held"] = sorted([r, f] for r, f in held_pairs(card) | card_pairs(card))
    if to == "done" and card["kind"] == "build" and card["repo"] and not card.get("commit"):
        entry = repo_of(state, card["repo"])
        left = porcelain_paths(Path(entry["path"]), card["files"]) if entry["branch"] else []
        if left:
            raise SystemExit(f"{card['id']} cannot be done: uncommitted changes in "
                             f"{', '.join(left)}; run `checkpoint` first")
    if counter:
        card[counter] += 1
    card["since"] = now() if since == "now" else None
    card["status"] = to
    if tier or effort:
        role = "builder" if to == "doing" else "reviewer"
        card["dispatches"].append({"t": now(), "role": role, "agent": card[role], "tier": tier, "effort": effort})
    log_entry(state, who, why, card["id"], frm, to)
    if to == "dropped":
        return [c["id"] for c in sorted(state["cards"], key=card_num) if card["id"] in c["deps"]]
    return []


def cmd_eligible(args) -> None:
    ids, skipped = eligible_ids(load(args.run))
    for line in skipped:
        print(line, file=sys.stderr)
    for cid in ids:
        print(cid)


def last_handback(transcript: Path) -> str:
    return last_handback_at(transcript)[0]


def last_handback_at(transcript: Path) -> tuple[str, str | None]:
    """The message of the last SubagentHandback call in a transcript, and its row's timestamp."""
    message, at = None, None
    for line in transcript.read_text(encoding="utf-8").split("\n"):
        if not line.strip():
            continue
        row = json.loads(line)
        msg = row.get("message")
        if not isinstance(msg, dict) or msg.get("role") != "assistant" or not isinstance(msg.get("content"), list):
            continue
        for block in msg["content"]:
            if block.get("type") == "tool_use" and block.get("name") == "SubagentHandback":
                message, at = block["input"]["message"], row.get("timestamp")
    if message is None:
        raise SystemExit(f"report: no SubagentHandback call in {transcript}")
    return message, at


NO_SECTION = {"none", "none.", "- none", "n/a"}


def report_section(message: str, heading: str) -> str:
    """The body under the last `## <heading>` line outside a code fence, or "" when absent, empty or none."""
    lines = [ln.rstrip("\r") for ln in message.split("\n")]
    fenced, start = False, None
    for i, line in enumerate(lines):
        if line.strip().startswith("```"):
            fenced = not fenced
        elif not fenced and line.strip() == f"## {heading}":
            start = i
    if start is None:
        return ""
    body, fenced = [], False
    for line in lines[start + 1:]:
        if line.strip().startswith("```"):
            fenced = not fenced
        elif not fenced and line.startswith("## "):
            break
        body.append(line)
    text = "\n".join(body).strip()
    return "" if text.lower() in NO_SECTION else text


def lessons_section(message: str) -> str:
    return report_section(message, "Lessons")


def save_lessons(run: Path, state: dict, label: str, text: str) -> None:
    if not text:
        return
    path = run / "lessons.md"
    existing = path.read_text(encoding="utf-8") if path.exists() else f"# Lessons from run {state['slug']}\n"
    if f"### {label}," in existing:  # a retry after a failed save must not add the entry twice
        return
    path.write_text(f"{existing}\n### {label}, {hhmm(now())}\n{text}\n", encoding="utf-8")


def lessons_count(run: Path) -> int:
    path = run / "lessons.md"
    return len(re.findall(r"^### C\d+ ", path.read_text(encoding="utf-8"), re.M)) if path.exists() else 0


def handback_of(agent: str, projects_dir: Path | None) -> str:
    return handback_at(agent, projects_dir)[0]


def handback_at(agent: str, projects_dir: Path | None) -> tuple[str, str | None]:
    projects = projects_dir or Path.home() / ".claude" / "projects"
    matches = list(projects.glob(f"*/*/subagents/agent-{agent}.jsonl"))
    if len(matches) != 1:
        raise SystemExit(f"report: expected exactly 1 transcript for agent {agent} "
                         f"under {projects}, found {len(matches)}")
    return last_handback_at(matches[0])


def save_report(run: Path, state: dict, card: dict, kind: str, message: str) -> tuple[str, Path]:
    """Record the agent's handback as reports/<id>-<kind>-<try>.md; (verdict, saved path)."""
    verdict = next((ln.strip() for ln in message.split("\n") if ln.strip()), "")
    needs = {"build": "doing", "review": "review"}[kind]
    if card["status"] != needs:
        raise SystemExit(f"report: a {kind} report needs a card in {needs}; {card['id']} is {card['status']}")
    name = f"{kind}-{card['tries']}"
    saved = run / "reports" / f"{card['id']}-{name}.md"
    data = message.encode("utf-8")
    if any(r["name"] == name for r in card["reports"]):
        raise SystemExit(f"report: {name} is already recorded for {card['id']}"
                         + (f"; {saved} already exists" if saved.exists() else ""))
    if not saved.exists():
        saved.write_bytes(data)
    elif saved.read_bytes() != data:  # an identical leftover is a retry after a failed save
        raise SystemExit(f"report: {saved} already exists; refusing to overwrite")
    card["reports"].append({"name": name, "verdict": verdict})
    agent = card["builder"] if kind == "build" else card["reviewer"]
    save_lessons(run, state, f"{card['id']} {name} ({agent})", lessons_section(message))
    log_entry(state, "lead", f"saved {name}: {verdict}", card["id"])
    return verdict, saved


def cmd_report(args) -> None:
    message = handback_of(args.agent, args.projects_dir)

    def fn(state):
        verdict, saved = save_report(args.run, state, find_card(state, args.id), args.kind, message)
        return [verdict, str(saved)]
    mutate(args.run, fn)


# ------------------------------------------------------- dispatch and returns

def build_policy(card: dict) -> tuple[str, str]:
    """(tier, effort) for the card's next builder: its size's tier, one rung up per escalation."""
    tier, effort = BUILD_POLICY[card_size(card)]
    return LADDER[min(LADDER.index(tier) + card["bump"], len(LADDER) - 1)], effort


def card_size(card: dict) -> str:
    return card["size"] or ("S" if card["kind"] == "question" else "M")


def review_depth(card: dict) -> str:
    return card["review"] or ("deep" if card_size(card) == "L" else "standard")


def brief_template(role: str) -> str:
    """The ```text block under briefs.md's `## <role> brief` heading."""
    text = (Path(__file__).resolve().parent / "briefs.md").read_text(encoding="utf-8")
    m = re.search(rf"^## {role} brief[^\n]*\n.*?```text\n(.*?)\n```", text, re.S | re.M)
    if m is None:
        raise SystemExit(f"briefs.md has no ```text block under a `## {role} brief` heading")
    return m.group(1)


def fill(template: str, values: dict, conditions: dict) -> str:
    """{name} -> value; a line starting `[if <cond>] ` stays (without the tag) only when the condition holds."""
    out = []
    for line in template.split("\n"):
        m = re.match(r"\[if (\w+)\] ", line)
        if m:
            if not conditions[m.group(1)]:
                continue
            line = line[m.end():]
        out.append(re.sub(r"\{(\w+)\}", lambda k: str(values[k.group(1)]) if k.group(1) in values else k.group(0),
                          line))
    return "\n".join(out)


def render_brief(run: Path, state: dict, card: dict, role: str) -> Path:
    """Write the card's brief for this dispatch to RUN/briefs/<id>-<build|review>-<try>.md."""
    cid, t = card["id"], card["tries"]
    kind = "build" if role == "builder" else "review"
    repo = repo_of(state, card["repo"]) if card["repo"] else None
    reports = run / "reports"
    earlier = sorted(p.name for p in reports.glob(f"{cid}-*.md")
                     if not p.name.endswith((f"-build-{t}.md", f"-review-{t}.md")))
    values = {"id": cid, "slug": state["slug"], "run": run, "board": Path(__file__).resolve(),
              "skill": Path(__file__).resolve().parent, "card": run / "cards" / f"{cid}.md", "try": t,
              "agent": card[role], "repo_path": Path(repo["path"]) if repo else "-",
              "branch": (repo["branch"] or "its current branch") if repo else "-",
              "files": " ".join(f'"{f}"' for f in card["files"]), "depth": review_depth(card),
              "budget": REVIEW_POLICY.get(review_depth(card), ("", "", "-"))[2],
              "build_report": reports / f"{cid}-build-{t}.md",
              "prev_review": reports / f"{cid}-review-{t - 1}.md",
              "earlier": ", ".join(str(reports / n) for n in earlier), "lane": card["lane"]}
    conditions = {"retry": bool(earlier), "deps": bool(card["deps"]), "rereview": card["bounces"] > 0,
                  "files": bool(card["files"]), "question": card["kind"] == "question", "lane": bool(card["lane"])}
    template = brief_template("Reviewer" if role == "reviewer" else
                              "Question" if card["kind"] == "question" else "Builder")
    path = run / "briefs" / f"{cid}-{kind}-{t}.md"
    path.parent.mkdir(exist_ok=True)
    write_atomic(path, fill(template, values, conditions) + "\n")
    return path


def lane_worker_tier(state: dict, card: dict) -> str | None:
    """The tier of the lane's worker if an earlier card of the card's lane was built, else None."""
    if not card["lane"]:
        return None
    built = [d["tier"] for c in sorted(state["cards"], key=card_num) if c["lane"] == card["lane"] and c is not card
             and c["status"] in SATISFIED for d in c["dispatches"] if d["role"] == "builder"]
    return built[-1] if built else None


def dispatch_line(state: dict, card: dict, role: str, brief: Path, tier: str, effort: str) -> str:
    who = ("answering question card" if card["kind"] == "question" else "the builder for card") \
        if role == "builder" else "the reviewer for card"
    prompt = (f"You are {who} {card['id']} of construct run {state['slug']}. Your brief is {brief}: "
              f"read it first and follow it exactly.")
    line = {"card": card["id"], "subagent_type": card[role], "model": tier, "effort": effort,
            "run_in_background": True,
            "description": f"{card['id']} {'build' if role == 'builder' else 'review'}: {flat(card['title'])[:40]}",
            "prompt": prompt}
    if role == "builder" and card["lane"]:
        # resume: the lane already has a worker at this tier; send it the prompt (SendMessage) instead of a new agent
        line |= {"lane": card["lane"], "resume": lane_worker_tier(state, card) == tier}
    return "dispatch " + json.dumps(line, ensure_ascii=False)


def do_dispatch(run: Path, state: dict) -> tuple[list[str], list[str]]:
    """Start every eligible card: move it to doing at its policy tier and render its brief.
    (dispatch lines, skip reasons)."""
    ids, skipped = eligible_ids(state)
    lines = []
    for cid in ids:
        card = find_card(state, cid)
        if card["builder"] == "lead":
            do_move(state, card, "doing", "lead", "the lead builds it")
            lines.append(f"self {cid}: you build it. Read {run / 'cards' / f'{cid}.md'}, build until its done-when "
                         f"passes, write your report (first line DONE, then a ## Handoff) to a file, and run "
                         f"`returned \"{run}\" {cid} --self <that file>`")
            continue
        tier, effort = build_policy(card)
        do_move(state, card, "doing", "lead", "dispatched", tier, effort)
        lines.append(dispatch_line(state, card, "builder", render_brief(run, state, card, "builder"), tier, effort))
    return lines, skipped


def to_review(run: Path, state: dict, card: dict, why: str) -> str:
    tier, effort, _ = REVIEW_POLICY[review_depth(card)]
    do_move(state, card, "review", "lead", why, tier, effort)
    return dispatch_line(state, card, "reviewer", render_brief(run, state, card, "reviewer"), tier, effort)


def run_gate(state: dict, card: dict) -> str | None:
    """The repo's mechanical gate (formatter, lint) on the card's files: None when green or not set, else its output."""
    if not card["repo"]:
        return None
    repo = repo_of(state, card["repo"])
    files = [f for f in card["files"] if fnmatch.fnmatch(f, repo.get("gate_glob") or "*")
             and (Path(repo["path"]) / f).exists()]
    if not repo.get("gate") or not files:
        return None
    command = repo["gate"].replace("{files}", " ".join(f'"{f}"' for f in files))
    try:
        done = subprocess.run(command, shell=True, cwd=repo["path"], capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=GATE_TIMEOUT)
    except subprocess.TimeoutExpired:
        return f"$ {command}\ngate timed out after {GATE_TIMEOUT} s"
    if done.returncode == 0:
        return None
    tail = (done.stdout + done.stderr).strip().split("\n")[-GATE_TAIL_LINES:]
    return f"$ {command}\nexit {done.returncode}\n" + "\n".join(tail)


def board_line(state: dict) -> str:
    n = counts(state)
    ids = {s: ",".join(c["id"] for c in sorted(state["cards"], key=card_num) if c["status"] == s)
           for s in ("doing", "review", "todo", "blocked")}
    return (f"board: {n['done'] + n['dropped']}/{n['total']} done · doing {ids['doing'] or '-'} · "
            f"review {ids['review'] or '-'} · todo {ids['todo'] or '-'} · blocked {ids['blocked'] or '-'}")


def cmd_dispatch(args) -> None:
    def fn(state):
        lines, skipped = do_dispatch(args.run, state)
        for line in skipped:
            print(line, file=sys.stderr)
        return lines + [board_line(state)]
    mutate(args.run, fn)


def cmd_returned(args) -> None:
    """An agent came back: save its report and take the step its verdict calls for (SKILL §2).
    --saved acts on the report already saved for the card's current try (a resumed run); --self takes the report of
    a card the lead built from a file."""
    if sum(map(bool, (args.agent, args.saved, args.self))) != 1:
        raise SystemExit("returned: give exactly one of --agent, --saved (a report already saved) or --self FILE")
    handback, handed_at = (handback_at(args.agent, args.projects_dir) if args.agent else
                           (args.self.read_text(encoding="utf-8"), None) if args.self else (None, None))

    def fn(state):
        card = find_card(state, args.id)
        if card["status"] not in ACTIVE:
            raise SystemExit(f"returned: {card['id']} is {card['status']}; only doing or review cards return")
        kind = "build" if card["status"] == "doing" else "review"
        if handed_at and datetime.fromisoformat(handed_at.replace("Z", "+00:00")) < datetime.fromisoformat(card["since"]):
            # A resumed lane worker that hasn't handed back yet still shows its previous card's handback.
            raise SystemExit(f"returned: the agent's last handback ({hhmm(handed_at.replace('Z', '+00:00'))}) predates "
                             f"{card['id']}'s dispatch ({hhmm(card['since'])}); it isn't this card's report")
        message = handback
        if args.saved:
            path = args.run / "reports" / f"{card['id']}-{kind}-{card['tries']}.md"
            if not path.exists():
                raise SystemExit(f"returned: --saved, but there is no {path}")
            message = path.read_text(encoding="utf-8")
        if args.saved and any(r["name"] == f"{kind}-{card['tries']}" for r in card["reports"]):
            verdict, saved = next(ln.strip() for ln in message.split("\n") if ln.strip()), path
        else:
            verdict, saved = save_report(args.run, state, card, kind, message)
        head = f"{card['id']} {kind}-{card['tries']}: {verdict}"
        if kind == "build" and verdict.startswith("DONE"):
            red = run_gate(state, card)
            if red:
                (args.run / "reports" / f"{card['id']}-gate-{card['tries']}.md").write_text(red + "\n",
                                                                                         encoding="utf-8")
                do_move(state, card, "todo", "lead", f"gate red: {flat(red.split(chr(10))[-1])[:120]}")
                lines, _ = do_dispatch(args.run, state)
                return [f"{head} -> gate red, retry (not a bounce)", *lines, board_line(state)]
            if review_depth(card) == "none":
                sha = (do_checkpoint(state, card) if card["files"] and repo_of(state, card["repo"])["branch"]
                       else None)
                do_move(state, card, "done", "lead", "gate green, no review" + (f", {sha[:7]}" if sha else ""))
                lines, _ = do_dispatch(args.run, state)
                return [f"{head} -> done on its gate" + (f", checkpoint {sha[:7]}" if sha else ""), *lines,
                        board_line(state)]
            lines = [f"{head} -> review ({review_depth(card)})", to_review(args.run, state, card, "built; gate green")]
            more, _ = do_dispatch(args.run, state)
            return [*lines, *more, board_line(state)]
        if kind == "build" and verdict.startswith("BLOCKED"):
            refused = verdict.startswith("BLOCKED: refused")
            if not refused:
                card["bump"] += 1
            do_move(state, card, "blocked", "lead", verdict[:200])
            return [f"{head} -> blocked: " + ("show the user the exact refusal" if refused else
                    "fix the card (files, question, check) or ask the user, then `move todo` and `dispatch`; "
                    "its next builder is one rung up"), board_line(state)]
        if kind == "review" and verdict.startswith("PASS"):
            sha = do_checkpoint(state, card) if card["files"] and repo_of(state, card["repo"])["branch"] else None
            do_move(state, card, "done", "lead", f"review PASS{', ' + sha[:7] if sha else ''}")
            lines, _ = do_dispatch(args.run, state)
            return [f"{head} -> done" + (f", checkpoint {sha[:7]}" if sha else ""), *lines, board_line(state)]
        if kind == "review" and verdict.startswith("FAIL"):
            finding = next((ln.strip() for ln in message.split("\n")[1:] if ln.strip()), verdict)
            if card["bounces"] >= 2:
                do_move(state, card, "blocked", "lead", f"third FAIL: {flat(finding)[:160]}")
                return [f"{head} -> blocked after a third FAIL: show the user", board_line(state)]
            last_builder = next((d["tier"] for d in reversed(card["dispatches"]) if d["role"] == "builder"), None)
            if last_builder == "sonnet":
                card["bump"] += 1
            do_move(state, card, "todo", "lead", f"review FAIL: {flat(finding)[:160]}")
            started = [f"{c['id']} ({c['status']})" for c in sorted(state["cards"], key=card_num)
                       if card["id"] in c["deps"] and c["status"] in ("doing", "review", "done")]
            return [f"{head} -> todo (bounce {card['bounces']}): name the defect class, write rules/<class>.md and "
                    f"add it to the knowledge line of the cards not dispatched yet, then `dispatch`",
                    *([f"started on {card['id']}'s unreviewed result: {', '.join(started)}; check them against "
                       f"the fix"] if started else []), board_line(state)]
        return [f"{head}: not DONE/BLOCKED/PASS/FAIL; saved as {saved}, handle it by hand", board_line(state)]
    mutate(args.run, fn)


def cmd_brief(args) -> None:
    """Re-render the brief of a card in flight and print its Agent call (a reviewer to re-launch, a resumed run)."""
    def fn(state):
        card = find_card(state, args.id)
        if card["status"] not in ACTIVE:
            raise SystemExit(f"brief: {card['id']} is {card['status']}; only doing or review cards have a brief")
        role = "builder" if card["status"] == "doing" else "reviewer"
        last = next((d for d in reversed(card["dispatches"]) if d["role"] == role), None)
        tier, effort = ((last["tier"], last["effort"]) if last else build_policy(card) if role == "builder"
                        else REVIEW_POLICY[review_depth(card)][:2])
        return [dispatch_line(state, card, role, render_brief(args.run, state, card, role), tier, effort)]
    mutate(args.run, fn)


def agent_transcript(projects: Path, slug: str, brief: Path, since: datetime) -> Path | None:
    """The newest subagent transcript started after `since` whose first prompt names this dispatch's brief."""
    found = []
    for path in projects.glob("*/*/subagents/agent-*.jsonl"):
        mtime = path.stat().st_mtime
        if mtime < since.timestamp():
            continue
        with path.open(encoding="utf-8", errors="replace") as f:
            first = f.readline()
        if brief.name in first and f"construct run {slug}" in first:
            found.append((mtime, path))
    return max(found)[1] if found else None


def stall(transcript: Path, at: datetime, silent: int) -> str | None:
    """Why this agent looks stuck, or None. Silent after a tool result means the model never answered; a turn that
    ended (no tool call) is the agent waiting on its own background job or handing back, which is not a stall."""
    rows = [json.loads(ln) for ln in transcript.read_text(encoding="utf-8", errors="replace").split("\n")
            if ln.strip()]
    rows = [r for r in rows if r.get("timestamp") and r.get("type") in ("user", "assistant")]
    if not rows:
        return None
    last = rows[-1]
    age = (at - datetime.fromisoformat(last["timestamp"].replace("Z", "+00:00"))).total_seconds() / 60
    if last["type"] == "user":
        return f"no model step for {age:.0f} min after its last tool result" if age >= silent else None
    content = (last.get("message") or {}).get("content") or []
    uses = [b for b in content if isinstance(b, dict) and b.get("type") == "tool_use"]
    if not uses or any(b.get("name") == "SubagentHandback" or (b.get("input") or {}).get("run_in_background")
                       for b in uses):
        return None
    return f"one tool call running for {age:.0f} min" if age >= max(silent, TOOL_SILENT_MINUTES) else None


def cmd_watch(args) -> None:
    projects = args.projects_dir or Path.home() / ".claude" / "projects"
    started = time.monotonic()
    while True:
        state = load(args.run)
        if state["phase"] == "closed":
            print("watch: the run is closed")
            return
        at = datetime.now().astimezone()
        alerts = []
        for card in sorted((c for c in state["cards"] if c["status"] in ACTIVE), key=card_num):
            role = "builder" if card["status"] == "doing" else "reviewer"
            brief = args.run / "briefs" / f"{card['id']}-{'build' if role == 'builder' else 'review'}-{card['tries']}.md"
            if not brief.exists():
                continue  # dispatched by hand, not by `dispatch`/`returned`: nothing names its transcript
            since = datetime.fromisoformat(card["since"])
            transcript = agent_transcript(projects, state["slug"], brief, since)
            minutes = (at - since).total_seconds() / 60
            if transcript is None:
                if minutes >= args.silent:
                    alerts.append(f"stall: {card['id']} {role}: no agent transcript names {brief.name} after "
                                  f"{minutes:.0f} min; was it dispatched?")
                continue
            why = stall(transcript, at, args.silent)
            if why:
                alerts.append(f"stall: {card['id']} {role} ({card[role]}): {why}; transcript {transcript}")
        if alerts or args.once:
            print("\n".join(alerts) or "watch: no stalls")
            return
        if time.monotonic() - started >= args.heartbeat * 60:
            # Exiting wakes the lead's session: a lead whose turn died on an API error resumes within a heartbeat.
            print(f"watch: heartbeat after {args.heartbeat:g} min, no stalls; read the board and restart watch")
            return
        time.sleep(args.interval)


def plan_shape(state: dict) -> tuple[int, int]:
    """(width, depth) of the plan: most cards on one dependency layer, and the longest chain in cards."""
    layers = collections.Counter(graph_layers(state).values())
    return (max(layers.values()), max(layers) + 1) if layers else (0, 0)


def cmd_handoff(args) -> None:
    """Print what each direct dependency handed off: the `## Handoff` of its latest build report."""
    state = load(args.run)
    card = find_card(state, args.id)
    if not card["deps"]:
        print(f"{card['id']} has no dependencies.")
        return
    for did in card["deps"]:
        dep = find_card(state, did)
        commit = f", commit {dep['commit']}" if dep.get("commit") else ""
        print(f"### {dep['id']}: {dep['title']} ({dep['status']}{commit})")
        builds = [r["name"] for r in dep["reports"] if r["name"].startswith("build-")]
        path = args.run / "reports" / f"{dep['id']}-{builds[-1]}.md" if builds else None
        if dep["status"] == "dropped":
            why = next((e["why"] for e in reversed(state["log"])
                        if e["card"] == dep["id"] and e["to"] == "dropped"), "")
            print(f"Dropped: {why.rstrip('.')}. Nothing of it is in the code.")
        elif path is None:
            print("No report yet.")
        elif not path.exists():
            print(f"Report missing: {path}")
        else:
            text = report_section(path.read_text(encoding="utf-8"), "Handoff")
            print(f"{text}\nFull report: {path}" if text else f"No handoff; read {path}")
        print()


def cmd_progress(args) -> None:
    def fn(state):
        card = find_card(state, args.id)
        if card["status"] not in ("doing", "review"):
            raise SystemExit(f"progress: {card['id']} is {card['status']}; only doing or review cards take notes")
        card["progress"].append({"t": now(), "who": args.who, "text": args.text[:PROGRESS_MAX_CHARS]})
        card["progress"] = card["progress"][-PROGRESS_KEEP:]
    mutate(args.run, fn)


def cmd_log(args) -> None:
    def fn(state):
        if args.card:
            find_card(state, args.card)
        log_entry(state, args.who, args.text, args.card)
    mutate(args.run, fn)


def owner_of(card: dict) -> str:
    return {"doing": card["builder"], "review": card["reviewer"]}.get(card["status"], "")


def counts(state: dict) -> dict:
    n = {s: sum(1 for c in state["cards"] if c["status"] == s) for s in STATUSES}
    n["total"] = len(state["cards"])
    return n


def over_budget(run: Path) -> list[str]:
    lines = []
    for name, cap in READ_BUDGETS.items():
        path = run / name
        size = path.stat().st_size if path.exists() else 0
        if size > cap:
            lines.append(f"budget: {name} is {size:,} bytes, over its {cap:,}; every agent reads it, so move "
                         f"what only some cards need to a rules/<topic>.md or to those cards' knowledge line")
    return lines


def cmd_show(args) -> None:
    state = load(args.run)
    n = counts(state)
    at = datetime.now().astimezone()
    print(f"{state['title']} [{state['phase']}, route {state['route'] or 'not set'}]  {n['done']}/{n['total']} done · {n['doing']} doing · "
          f"{n['review']} review · {n['todo']} todo · {n['blocked']} blocked · {n['dropped']} dropped")
    extras = header_extras(state, at)
    if extras:
        print(" · ".join(extras))
    for line in over_budget(args.run):
        print(line)
    width, depth = plan_shape(state)
    if n["total"] > 1:
        print(f"plan: width {width}, depth {depth}" + (" · one lane: /build or a direct session is likely faster"
                                                         if width <= 1 else ""))
    for status in STATUSES:
        print(f"\n{status.upper()}")
        for card in sorted((c for c in state["cards"] if c["status"] == status), key=card_num):
            since = f"since {fmt_elapsed(elapsed_seconds(card['since']))}" if card["since"] else "-"
            commit = f"  commit {card['commit'][:7]}{dropped_label(card)}" if card.get("commit") else ""
            print(f"{card['id']}  {card['title']}  {card['kind']} {card['repo'] or '-'}  "
                  f"{owner_of(card) or '-'}  {since}  try {card['tries']} bounce {card['bounces']}"
                  f"{minutes_label(state, card, at)}{commit}")
    mix = dispatch_mix(state)
    if mix:
        print("\nDISPATCH MIX")
        print("\n".join(mix))


# ------------------------------------------------------------ estimates and ETA

def idle_gaps(state: dict, at: datetime) -> list[tuple[datetime, datetime]]:
    """Stretches of IDLE_GAP_MINUTES or more with no sign of a session: no log entry, progress note or dispatch.

    Each card keeps only its last PROGRESS_KEEP notes, so activity older than that shows up only in the log.
    """
    beats = [e["t"] for e in state["log"]]
    for c in state["cards"]:
        beats += [n["t"] for n in c["progress"]] + [d["t"] for d in c["dispatches"]]
    stamps = sorted(datetime.fromisoformat(b) for b in beats)
    limit = timedelta(minutes=IDLE_GAP_MINUTES)
    gaps = [(x, y) for x, y in zip(stamps, stamps[1:]) if y - x >= limit]
    if stamps and at - stamps[-1] >= limit:
        gaps.append((stamps[-1], at))
    return gaps


def actual_minutes(state: dict, card: dict, at: datetime) -> float:
    """Minutes the card spent in doing and review, without the board-wide idle gaps inside those spans."""
    gaps = idle_gaps(state, at)
    total, start = 0.0, None

    def span(begin: str, end: datetime) -> float:
        first = datetime.fromisoformat(begin)
        seconds = (end - first).total_seconds()
        for x, y in gaps:
            seconds -= max(0.0, (min(end, y) - max(first, x)).total_seconds())
        return seconds / 60

    for e in state["log"]:
        if e["card"] != card["id"]:
            continue
        if e["from"] in ACTIVE and start is not None:
            total += span(start, datetime.fromisoformat(e["t"]))
            start = None
        if e["to"] in ACTIVE:
            start = e["t"]
    if start is not None and card["status"] in ACTIVE:
        total += span(start, at)
    return max(total, 0.0)


def eta_minutes(state: dict, at: datetime | None = None) -> float | None:
    """Minutes until the remaining cards finish: the larger of the longest dep chain and load over the limit."""
    at = at or datetime.now().astimezone()
    remaining = {c["id"]: c for c in state["cards"] if c["status"] not in SATISFIED}
    if not remaining:
        return None
    done = [actual_minutes(state, c, at) for c in state["cards"] if c["status"] == "done"]
    done = [m for m in done if m > 0]
    fallback = statistics.median(done) if done else DEFAULT_ESTIMATE_MINUTES
    cost = {}
    for cid, c in remaining.items():
        estimate = c["estimate"] or fallback
        left = estimate - actual_minutes(state, c, at) if c["status"] in ACTIVE else estimate
        cost[cid] = max(left, 0.2 * estimate)

    @functools.cache
    def chain(cid: str) -> float:
        return cost[cid] + max((chain(d) for d in remaining[cid]["deps"] if d in remaining), default=0)
    return max(max(chain(cid) for cid in remaining), sum(cost.values()) / state["limit"])


def estimate_accuracy(state: dict, at: datetime) -> float | None:
    """Median of actual/estimate over the done cards that have an estimate and a measured time."""
    actuals = {c["id"]: actual_minutes(state, c, at) for c in state["cards"] if c["status"] == "done"}
    ratios = [actuals[c["id"]] / c["estimate"] for c in state["cards"]
              if c["status"] == "done" and c["estimate"] and actuals[c["id"]] > 0]
    return statistics.median(ratios) if ratios else None


def clock_label(text: str) -> str:
    return text if re.fullmatch(r"\d{1,2}:\d\d", text) else hhmm(text)


def header_extras(state: dict, at: datetime) -> list[str]:
    out = []
    eta = eta_minutes(state, at)
    if eta is not None and state["phase"] != "closed":
        arrival = at + timedelta(minutes=eta)
        later = f" +{(arrival.date() - at.date()).days}d" if arrival.date() > at.date() else ""
        out.append(f"ETA ~{arrival.strftime('%H:%M')}{later} (est.)")
    if state.get("next_input"):
        when = f" · ~{clock_label(state['next_input_at'])}" if state.get("next_input_at") else ""
        out.append(f"next input: {flat(state['next_input'])}{when}")
    if state.get("availability"):
        out.append(f"you: {flat(state['availability'])}")
    ratio = estimate_accuracy(state, at)
    if ratio is not None:
        out.append(f"actual/est ×{ratio:.1f}")
    return out


def est_label(card: dict) -> str:
    return f"{card['estimate']}m" if card["estimate"] else ""


def actual_label(state: dict, card: dict, at: datetime) -> str:
    return f"~{round(actual_minutes(state, card, at))}m" if card["status"] == "done" else ""


def minutes_label(state: dict, card: dict, at: datetime) -> str:
    parts = []
    if card["estimate"]:
        parts.append(f"est {card['estimate']}m")
    if card["status"] == "done":
        parts.append(f"actual ~{round(actual_minutes(state, card, at))}m")
    return "  " + " ".join(parts) if parts else ""


def dispatch_mix(state: dict) -> list[str]:
    tally: dict[tuple, int] = {}
    for c in state["cards"]:
        for d in c["dispatches"]:
            key = (d["role"], d["tier"] or "?", d["effort"] or "?")
            tally[key] = tally.get(key, 0) + 1
    return [f"{role} · {tier} · {effort}: {n}" for (role, tier, effort), n in sorted(tally.items())]


# ----------------------------------------------------------------------- viewer
#
# The viewer is a detached child process. It proves who it is: after binding it writes RUN/viewer.json
# (pid, port, a random token) and serves the token at /viewer-id. "Our viewer is alive" always means that
# GET answers with the token in viewer.json; nothing is ever killed by a stored pid. `stop` writes
# RUN/viewer.stop and the child shuts itself down.

def viewer_url(port: int) -> str:
    return f"http://127.0.0.1:{port}/board.html"


def accepts(port: int, timeout: float) -> bool:
    try:
        socket.create_connection(("127.0.0.1", port), timeout).close()
    except OSError:
        return False
    return True


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def read_viewer_info(run: Path) -> dict | None:
    try:
        return json.loads(read_retry(run / "viewer.json"))
    except FileNotFoundError:
        return None


def probe(port: int, timeout: float) -> str | None:
    """What GET /viewer-id answers on the port, or None when nothing there speaks to us."""
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=timeout)
    try:
        conn.request("GET", "/viewer-id")
        reply = conn.getresponse()
        return reply.read().decode("utf-8", "replace") if reply.status == 200 else None
    except (OSError, http.client.HTTPException):
        return None  # refused, timed out or not HTTP: the answer to "is it ours" is simply no
    finally:
        conn.close()


def viewer_identity(run: Path, port: int, timeout: float = 0.5) -> dict | None:
    """The viewer.json record when the port answers with its token, else None."""
    info = read_viewer_info(run)
    return info if info and info["port"] == port and probe(port, timeout) == info["token"] else None


def viewer_alive(run: Path, port: int, timeout: float = 0.5) -> bool:
    return viewer_identity(run, port, timeout) is not None


def spawn_viewer(run: Path, port: int) -> subprocess.Popen:
    """Start `_serve` detached from this process, its console and its job, so it outlives the session."""
    cmd = [sys.executable, "-I", str(Path(__file__).resolve()), "_serve", str(run.resolve()), "--port", str(port)]
    if sys.platform == "win32":
        detach = {"creationflags": subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
                  | subprocess.CREATE_NO_WINDOW | subprocess.CREATE_BREAKAWAY_FROM_JOB}
    else:
        detach = {"start_new_session": True}
    with (run / "viewer.log").open("ab") as log:
        return subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=log, stderr=log, close_fds=True,
                                cwd=tempfile.gettempdir(), **detach)


def log_tail(run: Path, lines: int = 10) -> str:
    path = run / "viewer.log"
    return "\n".join(path.read_text(encoding="utf-8", errors="replace").splitlines()[-lines:]) if path.exists() else ""


def starting(run: Path, viewer: dict) -> bool:
    """Another command spawned a viewer a moment ago and it has not announced itself yet (no viewer.json)."""
    return (bool(viewer.get("spawned_at")) and elapsed_seconds(viewer["spawned_at"]) <= VIEWER_START_WAIT + 1
            and not (run / "viewer.json").exists())


def launch(run: Path, state: dict, port: int) -> subprocess.Popen:
    """Under the lock: spawn a viewer on `port` and record it. A spawn that fails starts the heal back-off."""
    for stale in ("viewer.json", "viewer.stop"):
        (run / stale).unlink(missing_ok=True)
    viewer = {k: v for k, v in (state.get("viewer") or {}).items() if k != "spawned_at"}
    try:
        proc = spawn_viewer(run, port)
    except BaseException:
        state["viewer"] = {**viewer, "port": port, "failed_at": now()}
        finish(run, state)
        raise
    state["viewer"] = {**viewer, "port": port, "spawned_at": now()}
    finish(run, state)
    return proc


def wait_for_viewer(run: Path, port: int, proc: subprocess.Popen | None) -> bool:
    deadline = time.monotonic() + VIEWER_START_WAIT
    while time.monotonic() < deadline:
        if viewer_alive(run, port, 0.3):
            return True
        if proc is not None and proc.poll() is not None:  # the child is gone; only another viewer can answer
            return viewer_alive(run, port, 0.3)
        time.sleep(0.1)
    return False


def after_wait(run: Path, port: int, gen: int, explicit: bool) -> int | None:
    """The viewer answered. A stop that landed while it was starting wins: the viewer must not outlive it."""
    with locked(run):
        state = load(run)
        viewer = dict(state.get("viewer") or {})
        if viewer.get("stop_gen", 0) == gen:
            if viewer.pop("failed_at", None):
                state["viewer"] = viewer
                finish(run, state)
            return port
    (run / "viewer.stop").write_text("stop", encoding="utf-8")
    return stopped_while_starting(explicit)


def stopped_while_starting(explicit: bool) -> None:
    if explicit:
        raise SystemExit("serve: a stop arrived while the viewer was starting; it stays stopped until the next "
                         "`serve`")


def ensure_viewer(run: Path, prefer: int | None = None, explicit: bool = False) -> int | None:
    """Make sure our viewer answers; returns its port, or None when a stop or a closed run says to leave it.

    The lock is held to decide and to spawn, never to wait. Only an explicit serve clears `stopped`, and only at
    its start; a stop that lands later (`stop_gen` changes) is honoured by every later step.
    """
    proc = None
    with locked(run):
        state = load(run)
        viewer = dict(state.get("viewer") or {})
        if explicit:
            if any([viewer.pop("stopped", None), viewer.pop("failed_at", None)]):
                state["viewer"] = viewer  # a deliberate serve overrides an earlier stop and the back-off
                finish(run, state)
        elif viewer.get("stopped") or state["phase"] == "closed":
            return None
        gen = viewer.get("stop_gen", 0)
        port = viewer.get("port")
        if port and viewer_alive(run, port, 1.0):
            if prefer and prefer != port:
                print(f"viewer: already running on port {port}; --port {prefer} ignored", file=sys.stderr)
            return port
        port = prefer or port or free_port()
        if not (starting(run, viewer) and viewer.get("port") == port):
            if accepts(port, 0.3):  # answers, but it is not our viewer
                other = free_port()
                print(f"viewer: port {port} is held by another program; serving at {viewer_url(other)} instead",
                      file=sys.stderr)
                port = other
            proc = launch(run, state, port)
    if wait_for_viewer(run, port, proc):
        return after_wait(run, port, gen, explicit)
    with locked(run):
        state = load(run)
        viewer = dict(state.get("viewer") or {})
        if viewer.get("stop_gen", 0) != gen or (not explicit and state["phase"] == "closed"):
            (run / "viewer.stop").write_text("stop", encoding="utf-8")
            return stopped_while_starting(explicit)
        if viewer.get("port") != port:  # another command already moved on
            port, proc = viewer["port"], None
        else:
            why = flat(log_tail(run, 1)) or "no output"
            failed = port
            port = free_port()
            proc = launch(run, state, port)
            print(f"viewer: port {failed} did not come up ({why}); serving at {viewer_url(port)} instead",
                  file=sys.stderr)
    if wait_for_viewer(run, port, proc):
        return after_wait(run, port, gen, explicit)
    with locked(run):
        state = load(run)
        state["viewer"] = {**(state.get("viewer") or {}), "failed_at": now()}
        finish(run, state)
    raise SystemExit(f"serve: the viewer did not come up on port {port}; {run / 'viewer.log'} ends:\n{log_tail(run)}")


def heal_viewer(run: Path) -> None:
    state = load(run)
    viewer = state.get("viewer") or {}
    port = viewer.get("port")
    if not port or state["phase"] == "closed" or viewer.get("stopped"):
        return
    if viewer.get("failed_at") and elapsed_seconds(viewer["failed_at"]) < VIEWER_HEAL_BACKOFF_SECONDS:
        return
    if not viewer_alive(run, port, 0.5):
        ensure_viewer(run)


def cmd_serve(args) -> None:
    if args.foreground:
        serve_loop(args.run, args.port, watch=False)
        return
    print(viewer_url(ensure_viewer(args.run, prefer=args.port or None, explicit=True)))


def cmd_stop(args) -> None:
    was_starting = []

    def mark(state):
        viewer = state.get("viewer") or {}
        was_starting.append(starting(args.run, viewer))
        state["viewer"] = {**({"port": viewer["port"]} if viewer.get("port") else {}), "stopped": True,
                           "stop_gen": viewer.get("stop_gen", 0) + 1}
    mutate(args.run, mark)  # first, so a concurrent command does not restart what is being stopped
    port = load(args.run)["viewer"].get("port")
    info = viewer_identity(args.run, port) if port else None
    flag = args.run / "viewer.stop"
    if info is None and not was_starting[0]:
        print("no viewer running; auto-restart stays off until the next `serve`")
        return
    flag.write_text("stop", encoding="utf-8")
    deadline = time.monotonic() + VIEWER_STOP_WAIT
    if info is None:  # a viewer is starting: it sees the flag on its first poll and exits
        while flag.exists() and time.monotonic() < deadline:
            time.sleep(0.1)
        flag.unlink(missing_ok=True)
        print("stopped the viewer that was starting; auto-restart stays off until the next `serve`")
        return
    while probe(port, 0.3) == info["token"]:
        if time.monotonic() >= deadline:
            raise SystemExit(f"stop: the viewer on port {port} did not stop within {VIEWER_STOP_WAIT}s; "
                             f"nothing was killed. Its pid is {info['pid']}: on Windows run "
                             f"`taskkill /PID {info['pid']} /F`, elsewhere `kill {info['pid']}`")
        time.sleep(0.1)
    print(f"stopped the viewer on port {port}; auto-restart stays off until the next `serve`")


class ViewerHandler(BaseHTTPRequestHandler):
    """Serves board.html and the viewer id, to local host names only; nothing else in the run folder."""

    def __init__(self, *args, run: Path, token: str, **kwargs):
        self.run, self.token = run, token
        super().__init__(*args, **kwargs)

    def log_request(self, *args, **kwargs) -> None:
        pass  # errors still reach log_message; an access log would only fill viewer.log

    def reply(self, head_only: bool) -> None:
        port = self.server.server_address[1]
        if self.headers.get("Host") not in (f"127.0.0.1:{port}", f"localhost:{port}"):
            self.send_error(403, "unknown host")
            return
        path = urlsplit(self.path).path
        if path == "/viewer-id":
            body, kind = self.token.encode("utf-8"), "text/plain; charset=utf-8"
        elif path in ("/", "/board.html"):
            kind = "text/html; charset=utf-8"
            try:
                body = (self.run / "board.html").read_bytes()
            except FileNotFoundError:
                self.send_error(404)
                return
            except PermissionError:  # the board is being replaced this instant; the page reloads and retries
                self.send_error(503)
                return
        else:
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        if not head_only:
            self.wfile.write(body)

    def do_GET(self) -> None:
        self.reply(head_only=False)

    def do_HEAD(self) -> None:
        self.reply(head_only=True)


class ViewerServer(ThreadingHTTPServer):
    # Windows lets SO_REUSEADDR share a listening port, which would hide a second viewer on it.
    allow_reuse_address = sys.platform != "win32"


def viewer_should_stop(run: Path) -> bool:
    try:
        state = json.loads(board_path(run).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return True
    except (PermissionError, json.JSONDecodeError):
        return False  # board.json is being replaced right now; look again next tick
    return state["phase"] == "closed" and elapsed_seconds(state["updated"]) > VIEWER_CLOSED_GRACE_SECONDS


def watch_run(run: Path, server: ThreadingHTTPServer, done: threading.Event) -> None:
    last_check = time.monotonic()
    while not done.wait(VIEWER_STOP_POLL_SECONDS):
        if (run / "viewer.stop").exists():
            server.shutdown()
            return
        if time.monotonic() - last_check >= VIEWER_WATCH_SECONDS:
            last_check = time.monotonic()
            if viewer_should_stop(run):
                server.shutdown()
                return


def serve_loop(run: Path, port: int, watch: bool) -> None:
    token = secrets.token_hex(16)
    server = ViewerServer(("127.0.0.1", port), functools.partial(ViewerHandler, run=run, token=token))
    bound = server.server_address[1]
    write_atomic(run / "viewer.json", json.dumps({"pid": os.getpid(), "port": bound, "token": token,
                                                   "started": now()}))
    done = threading.Event()
    if watch:
        threading.Thread(target=watch_run, args=(run, server, done), daemon=True).start()
    print(viewer_url(bound), flush=True)
    try:
        server.serve_forever()
    finally:
        done.set()
        info = read_viewer_info(run)
        if info and info["token"] == token:
            (run / "viewer.json").unlink(missing_ok=True)
        (run / "viewer.stop").unlink(missing_ok=True)
        server.server_close()


def cmd_serve_internal(args) -> None:
    serve_loop(args.run, args.port, watch=True)


# --------------------------------------------------------------------- rendering

def flat(text) -> str:
    return re.sub("\r\n|[\n\r\u2028\u2029\u0085]", " ", str(text))


def cell(text) -> str:
    return flat(text).replace("|", "\\|")


def report_label(card: dict) -> str:
    return ", ".join(f"{r['name']} {r['verdict']}" for r in card["reports"])


def render_md(state: dict) -> str:
    n = counts(state)
    at = datetime.now().astimezone()
    extras = header_extras(state, at)
    out = [f"# Construct: {flat(state['title'])}", "",
           f"{state['slug']} · {state['phase']} · parallel limit {state['limit']} · updated {hhmm(state['updated'])}",
           *(["", " · ".join(extras)] if extras else []),
           "", "> Generated by board.py. Don't edit by hand; change it with board.py.", "",
           "## Goal", "", state["goal"], "", "## Acceptance", ""]
    for a in state["acceptance"]:
        mark = "x" if a["status"] == "met" else " "
        flag = ", side effect" if a["side_effect"] else ""
        why = f" — {flat(a['why'])}" if a["why"] else ""
        out.append(f"- [{mark}] {a['id']}: {flat(a['text'])} ({a['status']}{flag}){why}")
    out += ["", "## Team", "", "| agent | role | tier |", "|---|---|---|"]
    out += [f"| {cell(t['agent'])} | {t['role']} | {cell(t['tier'])} |" for t in state["team"]]
    out += ["", "## Repos", "", "| name | path | original branch | base | run branch |", "|---|---|---|---|---|"]
    out += [f"| {cell(r['name'])} | {cell(r['path'])} | {cell(r['original_branch'])} | {r['base'][:7]} | "
            f"{cell(r['branch'] or '(no branch)')} |" for r in state["repos"]]
    merges = [f"- {flat(r['name'])}: merged {flat(m['ref'])} ({m['ref_sha'][:7]}) as {m['sha'][:7]}"
              + (f", {len(m['whole_file_from_ref'])} paths took its whole file" if m["whole_file_from_ref"] else "")
              for r in state["repos"] for m in r.get("merges", [])]
    out += ["", *merges] if merges else []
    dropped = f" · {n['dropped']} dropped" if n["dropped"] else ""
    out += ["", "## Board", "", f"{n['done']}/{n['total']} done{dropped}", "",
            "| id | card | status | owner | deps | tries | bounces | since | kind | repo | resources | commit | est | actual |",
            "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for c in sorted(state["cards"], key=card_num):
        since = hhmm(c["since"]) if c["since"] else ""
        out.append(f"| {c['id']} | {cell(c['title'])} | {c['status']} | {cell(owner_of(c))} | "
                   f"{', '.join(c['deps'])} | {c['tries']} | {c['bounces']} | {since} | {c['kind']} | "
                   f"{cell(c['repo'] or '')} | {cell(', '.join(c['resources']))} | {c.get('commit', '')[:7]} | "
                   f"{est_label(c)} | {actual_label(state, c, at)} |")
    out += ["", "## Cards", ""]
    for c in sorted(state["cards"], key=card_num):
        extra = ("" if c["kind"] == "build" else f" · {c['kind']} card")
        extra += f" · repo: {flat(c['repo'])}" if c["repo"] else ""
        extra += f" · resources: {flat(', '.join(c['resources']))}" if c["resources"] else ""
        extra += f" · commit: {c['commit'][:7]}{dropped_label(c)}" if c.get("commit") else ""
        out.append(f"- {c['id']}: {flat(c['title'])} → cards/{c['id']}.md · files: {', '.join(c['files'])}"
                   f" · reports: {report_label(c)}{extra}")
    mix = dispatch_mix(state)
    if mix:
        out += ["", "## Dispatch mix", "", *[f"- {line}" for line in mix]]
    out += ["", "## Log", ""]
    for e in state["log"]:
        card = f" {e['card']}" if e["card"] else ""
        arrow = f" {e['from']}→{e['to']}" if e["from"] and e["to"] else ""
        out.append(f"- {hhmm(e['t'])}{card}{arrow} {e['who']}: {flat(e['why'])}")
    return "\n".join(out) + "\n"


CSS = """
:root{--bg:#f6f7f9;--fg:#1c2024;--panel:#fff;--line:#d9dde3;--mute:#667085;--green:#1a7f37;--red:#c62828;--amber:#b26a00;--blue:#1f6feb}
@media (prefers-color-scheme:dark){:root{--bg:#14171a;--fg:#e6e8eb;--panel:#1d2125;--line:#333a42;--mute:#98a2b3;--green:#4ac26b;--red:#f2625c;--amber:#e3a234;--blue:#58a6ff}}
*{box-sizing:border-box}body{margin:0;padding:16px;background:var(--bg);color:var(--fg);font:14px/1.4 system-ui,sans-serif}
header{display:flex;flex-wrap:wrap;gap:8px 16px;align-items:baseline;margin-bottom:12px}
h1{font-size:20px;margin:0}h2{font-size:13px;text-transform:uppercase;letter-spacing:.05em;color:var(--mute);margin:0 0 8px}
.badge{border:1px solid var(--line);border-radius:10px;padding:1px 8px;font-size:12px;background:var(--panel)}
.phase{color:var(--blue);border-color:var(--blue)}.mute{color:var(--mute)}
.team{display:flex;flex-wrap:wrap;gap:6px;margin-bottom:12px}
.chip{border:1px solid var(--line);background:var(--panel);border-radius:12px;padding:2px 10px;font-size:12px}
.chip.active{border-color:var(--blue)}
.layout{display:grid;grid-template-columns:minmax(0,1fr) 300px;gap:16px}
@media (max-width:1100px){.layout{grid-template-columns:1fr}}
.board{display:grid;grid-template-columns:repeat(5,minmax(150px,1fr)) minmax(110px,.55fr);gap:8px}
.col{background:var(--panel);border:1px solid var(--line);border-radius:8px;padding:8px;min-height:120px}
.card{border:1px solid var(--line);border-radius:6px;padding:6px 8px;margin-bottom:6px;background:var(--bg)}
.card .id{font-weight:600}.card div{margin-top:2px}
.note{font-size:12px;color:var(--mute);border-left:2px solid var(--line);padding-left:6px}
.side{background:var(--panel);border:1px solid var(--line);border-radius:8px;padding:10px}
.side ul{margin:0 0 14px;padding-left:18px}.side li{margin-bottom:3px}
.badge.question{color:var(--amber);border-color:var(--amber)}.chip.commit{font-family:monospace}
.card .chips{display:flex;flex-wrap:wrap;gap:4px}.card .chip{padding:0 8px}
.PASS{color:var(--green);border-color:var(--green)}.FAIL{color:var(--red);border-color:var(--red)}
.BLOCKED{color:var(--amber);border-color:var(--amber)}
.st-todo,.node.todo{--f:var(--panel);--s:var(--line);--w:1.5px;--dash:none}
.st-doing,.node.doing{--f:color-mix(in srgb,var(--blue) 20%,var(--panel));--s:var(--blue);--w:3px;--dash:none}
.st-review,.node.review{--f:color-mix(in srgb,var(--amber) 20%,var(--panel));--s:var(--amber);--w:3px;--dash:none}
.st-done,.node.done{--f:color-mix(in srgb,var(--green) 20%,var(--panel));--s:var(--green);--w:1.5px;--dash:none}
.st-blocked,.node.blocked{--f:color-mix(in srgb,var(--red) 18%,var(--panel));--s:var(--red);--w:1.5px;--dash:none}
.st-dropped,.node.dropped{--f:color-mix(in srgb,var(--mute) 15%,var(--panel));--s:var(--mute);--w:1.5px;--dash:5 4}
.card{border-left:4px solid var(--s)}
.card.st-dropped{opacity:.65}.card.st-dropped .t{text-decoration:line-through}
.tabs{display:flex;gap:4px;margin-bottom:12px;border-bottom:1px solid var(--line)}
.tabs a{padding:4px 14px;color:var(--mute);text-decoration:none;border:1px solid transparent;border-bottom:0;border-radius:6px 6px 0 0}
[data-tab=board] .tabs a[href="#board"],[data-tab=graph] .tabs a[href="#graph"]{color:var(--fg);background:var(--panel);border-color:var(--line)}
[data-tab=board] #tab-graph,[data-tab=graph] #tab-board{display:none}
#graph-scroll{overflow:auto;border:1px solid var(--line);border-radius:8px;background:var(--panel);padding:4px}
.legend{display:flex;flex-wrap:wrap;gap:12px;margin-bottom:8px;font-size:12px;color:var(--mute)}
.sw i{display:inline-block;width:16px;height:10px;margin-right:4px;vertical-align:middle;border-radius:3px;
background:var(--f);border:var(--w) solid var(--s)}
.sw.st-dropped i{border-style:dashed}
.node rect{fill:var(--f);stroke:var(--s);stroke-width:var(--w);stroke-dasharray:var(--dash)}
.node text{fill:var(--fg);font:12px system-ui,sans-serif}.node .nid{font-weight:600}
.edge{fill:none;stroke:var(--mute);stroke-width:1.2;stroke-linecap:round;stroke-linejoin:round;opacity:.5}
.arrowhead{fill:var(--mute);fill:context-stroke}
.edge.to-done,.edge.to-dropped{opacity:.22}
.edge.to-doing{stroke:var(--blue);stroke-width:2;opacity:1}
.edge.to-review{stroke:var(--amber);stroke-width:2;opacity:1}
.node{cursor:pointer}.strip-title{fill:var(--mute);font:12px system-ui,sans-serif;text-transform:uppercase;letter-spacing:.05em}
svg.focus .edge:not(.hl){opacity:.06}svg.focus .node:not(.hl){opacity:.25}
svg.focus .edge.hl{opacity:1;stroke-width:2.4}
.mix{margin-top:12px}.mix ul{margin:0;padding-left:18px}
"""

JS = """
function fmt(s){s=Math.max(0,Math.floor(s));if(s<3600)return Math.floor(s/60)+"m "+(s%60)+"s";
var m=Math.floor(s/60);if(m<1440)return Math.floor(m/60)+"h "+(m%60)+"m";return Math.floor(m/1440)+"d "+Math.floor(m%1440/60)+"h"}
function tick(){document.querySelectorAll("[data-since]").forEach(function(e){e.textContent=fmt((Date.now()-Date.parse(e.dataset.since))/1000)})}
tick();setInterval(tick,1000);
window.addEventListener("hashchange",tab);
var graph=document.getElementById("graph-scroll"),svg=graph.querySelector("svg");
function focusOn(id){svg.classList.toggle("focus",!!id);
svg.querySelectorAll(".hl").forEach(function(e){e.classList.remove("hl")});
if(!id)return;
var self=svg.querySelector('[data-card="'+id+'"]');if(self)self.classList.add("hl");
svg.querySelectorAll("[data-edge]").forEach(function(e){var ends=e.dataset.edge.split(">");
if(ends.indexOf(id)<0)return;e.classList.add("hl");
ends.forEach(function(n){var g=svg.querySelector('[data-card="'+n+'"]');if(g)g.classList.add("hl")})})}
svg.addEventListener("mouseover",function(ev){var g=ev.target.closest("[data-card]");if(g&&!pinned)focusOn(g.dataset.card)});
svg.addEventListener("mouseout",function(){if(!pinned)focusOn(null)});
svg.addEventListener("click",function(ev){var g=ev.target.closest("[data-card]");
pinned=g&&g.dataset.card!==pinned?g.dataset.card:null;focusOn(pinned)});
try{var saved=JSON.parse(sessionStorage.getItem("construct-scroll")||"null");
if(saved){window.scrollTo(0,saved.y);graph.scrollLeft=saved.gx;graph.scrollTop=saved.gy;
if(saved.pin){pinned=saved.pin;focusOn(pinned)}}}catch(e){}
"""

# Runs in the head so even a partially received page reloads. A reload that hits a stopped viewer would leave
# a dead tab, so the page first asks the server whether it is back (file:// pages cannot fetch themselves).
HEAD_JS = """
function tab(){document.documentElement.dataset.tab=location.hash==="#graph"?"graph":"board"}
tab();
var pinned=null;
function saveView(){try{var g=document.getElementById("graph-scroll");
sessionStorage.setItem("construct-scroll",JSON.stringify({y:window.scrollY,gx:g?g.scrollLeft:0,gy:g?g.scrollTop:0,pin:pinned}))}catch(e){}}
function arm(){setTimeout(() => {
if(location.protocol==="file:"){saveView();location.reload();return}
fetch(location.href,{cache:"no-store"}).then(function(r){if(r.ok){saveView();location.reload()}else{arm()}}).catch(function(){arm()})
},3000)}
arm();
"""


COLUMNS = [("todo", "Todo"), ("doing", "Doing"), ("review", "Review"), ("done", "Done"), ("blocked", "Blocked"),
           ("dropped", "Dropped")]


def esc(text) -> str:
    return html.escape(str(text))


def since_span(t: str) -> str:
    return f'<span data-since="{esc(t)}">{fmt_elapsed(elapsed_seconds(t))}</span>'


def verdict_class(verdict: str) -> str:
    word = verdict.split()[0].upper().strip(":.") if verdict.split() else ""
    return word if word in ("PASS", "FAIL", "BLOCKED") else "DONE"


def team_chip(state: dict, member: dict) -> str:
    if member["role"] == "builder":
        active = [c for c in state["cards"] if c["status"] == "doing" and c["builder"] == member["agent"]]
        doing = ", ".join(f"{esc(c['id'])} · {since_span(c['since'])}" for c in active)
        status = f"building {doing}" if active else "idle"
    else:
        active = [c for c in state["cards"] if c["status"] == "review" and c["reviewer"] == member["agent"]]
        reviewing = ", ".join(f"{esc(c['id'])} · {since_span(c['since'])}" for c in active)
        status = f"reviewing {reviewing}" if active else "idle"
    cls = "chip active" if active else "chip"
    return (f'<span class="{cls}"><b>{esc(member["agent"])}</b> · {esc(member["role"])} · '
            f'{esc(member["tier"])} — {status}</span>')


def last_why(state: dict, card: dict, to: str, frm: str | None = None) -> str:
    for e in reversed(state["log"]):
        if e["card"] == card["id"] and e["to"] == to and (frm is None or e["from"] == frm):
            return e["why"]
    return ""


def dispatch_chip(card: dict) -> str:
    role = {"doing": "builder", "review": "reviewer"}.get(card["status"])
    latest = next((d for d in reversed(card["dispatches"]) if d["role"] == role), None)
    if latest is None:
        return ""
    return f'<span class="chip dispatch">{esc(" · ".join(x for x in (latest["tier"], latest["effort"]) if x))}</span>'


def card_tile(state: dict, card: dict, at: datetime | None = None) -> str:
    at = at or datetime.now().astimezone()
    by_id = {c["id"]: c for c in state["cards"]}
    rows = [f'<div><span class="id">{esc(card["id"])}</span> <span class="t">{esc(card["title"])}</span></div>']
    if card["status"] == "doing":
        rows.append(f'<div class="mute">building · {esc(card["builder"])}</div>')
    elif card["status"] == "review":
        rows.append(f'<div class="mute">reviewing · {esc(card["reviewer"])}</div>')
    chips = [dispatch_chip(card)] if dispatch_chip(card) else []
    if card["estimate"]:
        chips.append(f'<span class="chip est">est {card["estimate"]}m</span>')
    if card["status"] == "done":
        chips.append(f'<span class="chip actual">actual ~{round(actual_minutes(state, card, at))}m</span>')
    if card["kind"] == "question":
        chips.append('<span class="badge question">question</span>')
    if card["repo"]:
        chips.append(f'<span class="chip repo">{esc(card["repo"])}</span>')
    chips += [f'<span class="chip resource">{esc(r)}</span>' for r in card["resources"]]
    if card.get("commit"):
        chips.append(f'<span class="chip commit">{esc(card["commit"][:7])}</span>')
    if chips:
        rows.append(f'<div class="chips">{"".join(chips)}</div>')
    badges = []
    if card["since"]:
        badges.append(since_span(card["since"]))
    if card["tries"] > 1:
        badges.append(f'try {card["tries"]}')
    if card["bounces"] > 0:
        badges.append(f'bounced {card["bounces"]}')
    rows.append("<div>" + " ".join(f'<span class="badge">{b}</span>' for b in badges) + "</div>" if badges else "")
    if card["status"] == "todo":
        waiting = [d for d in card["deps"] if by_id[d]["status"] not in SATISFIED]
        rows.append(f'<div class="mute">{"waits on " + esc(", ".join(waiting)) if waiting else "ready"}</div>')
    if card["status"] == "blocked":
        why = last_why(state, card, to="blocked")
        if why:
            rows.append(f'<div class="note">blocked: {esc(why)}</div>')
    if card["status"] == "dropped":
        why = last_why(state, card, to="dropped")
        if why:
            rows.append(f'<div class="note">dropped: {esc(why)}</div>')
    if card["status"] == "todo" and card["bounces"] > 0:
        why = last_why(state, card, to="todo", frm="review")
        if why:
            rows.append(f'<div class="note">bounced: {esc(why)}</div>')
    if card["progress"]:
        p = card["progress"][-1]
        rows.append(f'<div class="note">{esc(p["who"])}: {esc(p["text"])} · {since_span(p["t"])} ago</div>')
    if card["reports"]:
        verdict = card["reports"][-1]["verdict"]
        rows.append(f'<div><span class="badge {verdict_class(verdict)}">{esc(verdict)}</span></div>')
    return f'<div class="card st-{card["status"]}">' + "".join(rows) + "</div>"


NODE_W, NODE_H, NODE_GAP_X, NODE_GAP_Y, LANE_H, GRAPH_MARGIN = 170, 46, 70, 14, 10, 20
NODE_TITLE_CHARS = 28
GRAPH_SWEEPS = 4
STRIP_MIN_COLUMNS = 5
ARROW_DEFS = ('<defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" '
              'orient="auto-start-reverse"><path class="arrowhead" d="M0 1L10 5L0 9z"/></marker></defs>')


def graph_layers(state: dict) -> dict[str, int]:
    """Layer of each card: the longest dependency path from any root (deps cannot form cycles)."""
    deps = {c["id"]: c["deps"] for c in state["cards"]}

    @functools.cache
    def layer(cid: str) -> int:
        return 1 + max(map(layer, deps[cid])) if deps[cid] else 0
    return {cid: layer(cid) for cid in deps}


def transitive_reduction(state: dict) -> list[tuple[str, str]]:
    """(dep, dependent) pairs that no other dependency path of the dependent implies."""
    deps = {c["id"]: c["deps"] for c in state["cards"]}

    @functools.cache
    def ancestors(cid: str) -> frozenset:
        return frozenset().union(*({d} | ancestors(d) for d in deps[cid]))
    return [(d, c["id"]) for c in sorted(state["cards"], key=card_num) for d in c["deps"]
            if not any(d in ancestors(o) for o in c["deps"] if o != d)]


def count_crossings(order: dict[int, list[str]], links: list[tuple[str, str]]) -> int:
    """Pairs of links between the same two adjacent layers whose ends are in opposite order."""
    where = {n: (lay, i) for lay, ids in order.items() for i, n in enumerate(ids)}
    by_layer: dict[int, list[tuple[int, int]]] = {}
    for a, b in links:
        by_layer.setdefault(where[a][0], []).append((where[a][1], where[b][1]))
    return sum(1 for ls in by_layer.values() for i, (a1, b1) in enumerate(ls) for a2, b2 in ls[i + 1:]
               if (a1 - a2) * (b1 - b2) < 0)


def graph_layout(state: dict, reduce: bool = True, sweeps: int = GRAPH_SWEEPS, compact: bool = True) -> dict:
    """Layered layout: reduced edges, dummy points on multi-layer edges, barycenter ordering, positions.

    With `compact`, a card without deps sits one layer left of its nearest dependent instead of in layer 0,
    and cards with no drawn edge go to a strip below the layers. Returns the per-layer order, the link list,
    the crossing count, each item's box, each edge's waypoints and the strip.
    """
    layers = graph_layers(state)
    edges = transitive_reduction(state) if reduce else [(d, c["id"]) for c in state["cards"] for d in c["deps"]]
    strip = []
    if compact:
        succ: dict[str, list[str]] = {}
        for u, v in edges:
            succ.setdefault(u, []).append(v)
        drawn = {n for e in edges for n in e}
        strip = sorted((c for c in layers if c not in drawn), key=lambda cid: int(cid[1:]))
        deps = {c["id"]: c["deps"] for c in state["cards"]}
        layers = {cid: (min(layers[v] for v in succ[cid]) - 1 if not deps[cid] else lay)
                  for cid, lay in layers.items() if cid in drawn}
    level = dict(layers)
    sort_key = {cid: (int(cid[1:]), 0, 0) for cid in layers}
    chains, links = {}, []
    for u, v in edges:
        mids = [f"{u}>{v}#{i}" for i in range(1, layers[v] - layers[u])]
        for i, m in enumerate(mids, 1):
            level[m], sort_key[m] = layers[u] + i, (int(u[1:]), int(v[1:]), i)
        chains[(u, v)] = [u, *mids, v]
        links += list(zip(chains[(u, v)], chains[(u, v)][1:]))
    order: dict[int, list[str]] = {}
    for item, lay in level.items():
        order.setdefault(lay, []).append(item)
    for ids in order.values():
        ids.sort(key=sort_key.__getitem__)
    below, above = {}, {}
    for a, b in links:
        below.setdefault(b, []).append(a)
        above.setdefault(a, []).append(b)

    def reorder(lay: int, neighbours: dict) -> None:
        pos = {n: i for ids in order.values() for i, n in enumerate(ids)}
        def bary(n):
            near = neighbours.get(n)
            return (sum(pos[x] for x in near) / len(near) if near else pos[n], sort_key[n])
        order[lay].sort(key=bary)

    best, best_cross = {lay: list(ids) for lay, ids in order.items()}, count_crossings(order, links)
    top = max(order, default=0)
    for s in range(sweeps):
        for lay in (range(1, top + 1) if s % 2 == 0 else range(top - 1, -1, -1)):
            reorder(lay, below if s % 2 == 0 else above)
        crossing = count_crossings(order, links)
        if crossing < best_cross:
            best, best_cross = {lay: list(ids) for lay, ids in order.items()}, crossing
    order = best

    boxes, height = {}, 2 * GRAPH_MARGIN
    for lay, ids in order.items():
        x, y = GRAPH_MARGIN + lay * (NODE_W + NODE_GAP_X), GRAPH_MARGIN
        for n in ids:
            h = NODE_H if n in layers else LANE_H
            boxes[n] = (x, y, NODE_W, h)
            y += h + NODE_GAP_Y
        height = max(height, y - NODE_GAP_Y + GRAPH_MARGIN)
    width = 2 * GRAPH_MARGIN + len(order) * NODE_W + max(len(order) - 1, 0) * NODE_GAP_X
    heading = None
    if strip:
        width = max(width, 2 * GRAPH_MARGIN + STRIP_MIN_COLUMNS * NODE_W + (STRIP_MIN_COLUMNS - 1) * NODE_GAP_X)
        per_row = (width - 2 * GRAPH_MARGIN + NODE_GAP_X) // (NODE_W + NODE_GAP_X)
        heading = (GRAPH_MARGIN, height + 4)
        top = height + 14
        for i, n in enumerate(strip):
            boxes[n] = (GRAPH_MARGIN + i % per_row * (NODE_W + NODE_GAP_X),
                        top + i // per_row * (NODE_H + NODE_GAP_Y), NODE_W, NODE_H)
        height = top + ((len(strip) - 1) // per_row + 1) * (NODE_H + NODE_GAP_Y) - NODE_GAP_Y + GRAPH_MARGIN
    waypoints = {}
    for edge, chain in chains.items():
        pts = [(boxes[chain[0]][0] + NODE_W, boxes[chain[0]][1] + NODE_H // 2)]
        for m in chain[1:-1]:  # a lane through the column: enter at its left edge, leave at its right edge
            x, y, _, h = boxes[m]
            pts += [(x, y + h // 2), (x + NODE_W, y + h // 2)]
        pts.append((boxes[chain[-1]][0], boxes[chain[-1]][1] + NODE_H // 2))
        waypoints[edge] = pts
    return {"layers": layers, "order": order, "links": links, "crossings": best_cross, "boxes": boxes,
            "waypoints": waypoints, "width": width, "height": height, "strip": strip, "strip_heading": heading}


def smooth_path(points: list[tuple[int, int]]) -> str:
    """One path of cubic segments through the waypoints, horizontal where it meets each one."""
    d = [f"M{points[0][0]} {points[0][1]}"]
    for (x1, y1), (x2, y2) in zip(points, points[1:]):
        dx = (x2 - x1) // 2
        d.append(f"C{x1 + dx} {y1}, {x2 - dx} {y2}, {x2} {y2}")
    return " ".join(d)


def render_graph(state: dict) -> str:
    lay = graph_layout(state)
    by_id = {c["id"]: c for c in state["cards"]}
    edges, nodes = [], []
    for (u, v), pts in lay["waypoints"].items():
        edges.append(f'<path class="edge to-{by_id[v]["status"]}" data-edge="{u}>{v}" '
                     f'marker-end="url(#arrow)" d="{smooth_path(pts)}"/>')
    for c in sorted(state["cards"], key=card_num):
        x, y, _, _ = lay["boxes"][c["id"]]
        title = flat(c["title"])
        short = title[:NODE_TITLE_CHARS] + ("…" if len(title) > NODE_TITLE_CHARS else "")
        deps = f"\ndeps: {', '.join(c['deps'])}" if c["deps"] else ""
        nodes.append(f'<g class="node {c["status"]}" data-card="{c["id"]}" '
                     f'data-layer="{lay["layers"].get(c["id"], "")}" data-status="{c["status"]}">'
                     f'<title>{esc(c["id"])} {esc(title)}{esc(deps)}</title>'
                     f'<rect x="{x}" y="{y}" width="{NODE_W}" height="{NODE_H}" rx="8"/>'
                     f'<text class="nid" x="{x + 10}" y="{y + 19}">{esc(c["id"])}</text>'
                     f'<text x="{x + 10}" y="{y + 36}">{esc(short)}</text></g>')
    if lay["strip_heading"]:
        nodes.append(f'<text class="strip-title" x="{lay["strip_heading"][0]}" y="{lay["strip_heading"][1] + 4}">'
                     "No dependencies</text>")
    legend = "".join(f'<span class="sw st-{s}"><i></i>{s}</span>' for s in STATUSES)
    return (f'<div class="legend">{legend}<span>hover a card to follow its arrows, click to pin</span></div>'
            f'<div id="graph-scroll">'
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{lay["width"]}" height="{lay["height"]}" '
            f'viewBox="0 0 {lay["width"]} {lay["height"]}">{ARROW_DEFS}{"".join(edges)}{"".join(nodes)}</svg></div>')


def render_html(state: dict, lessons: int = 0) -> str:
    n = counts(state)
    at = datetime.now().astimezone()
    summary = (f"{n['done']}/{n['total']} done · {n['doing']} working · {n['review']} in review · "
               f"{n['todo']} waiting · {n['blocked']} blocked · {n['dropped']} dropped")
    extras = "".join(f'<span class="badge">{esc(x)}</span>' for x in header_extras(state, at))
    mix = dispatch_mix(state)
    mix_html = (f'<section class="mix"><h2>Dispatch mix</h2><ul>{"".join(f"<li>{esc(x)}</li>" for x in mix)}</ul>'
                "</section>") if mix else ""
    cols = []
    for status, label in COLUMNS:
        cards = sorted((c for c in state["cards"] if c["status"] == status), key=card_num)
        tiles = "".join(card_tile(state, c, at) for c in cards)
        cols.append(f'<section class="col" data-col="{status}"><h2>{label} ({len(cards)})</h2>{tiles}</section>')
    acceptance = "".join(
        f'<li>{"&#9745;" if a["status"] == "met" else "&#9744;"} {esc(a["id"])}: {esc(a["text"])} '
        f'<span class="mute">({esc(a["status"])}{", side effect" if a["side_effect"] else ""}'
        f'{" — " + esc(a["why"]) if a["why"] else ""})</span></li>' for a in state["acceptance"])
    log_lines = []
    for e in reversed(state["log"][-HTML_LOG_LINES:]):
        card = f" {esc(e['card'])}" if e["card"] else ""
        arrow = f" {esc(e['from'])}→{esc(e['to'])}" if e["from"] and e["to"] else ""
        log_lines.append(f"<li>{hhmm(e['t'])}{card}{arrow} {esc(e['who'])}: {esc(e['why'])}</li>")
    repos = "".join(f'<span class="chip">{esc(r["name"])} · {esc(r["branch"] or "no branch")}</span>'
                    for r in state["repos"])
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<link rel="icon" href="data:,">
<title>Construct: {esc(state['title'])}</title>
<script>{HEAD_JS}</script>
<style>{CSS}</style></head><body>
<header><h1>{esc(state['title'])}</h1><span class="badge phase">{esc(state['phase'])}</span>
<span>{summary}</span>{extras}<span class="badge">lessons: {lessons}</span>{repos}<span class="mute">updated {datetime.fromisoformat(state['updated']).strftime('%H:%M:%S')}</span></header>
<div class="team">{''.join(team_chip(state, m) for m in state['team'])}</div>
<nav class="tabs"><a href="#board">Board</a><a href="#graph">Graph</a></nav>
<div id="tab-board"><div class="layout"><div class="board">{''.join(cols)}</div>
<aside class="side"><h2>Goal</h2><p>{esc(state['goal'])}</p>
<h2>Acceptance</h2><ul>{acceptance}</ul>
<h2>Log</h2><ul>{''.join(log_lines)}</ul></aside></div>{mix_html}</div>
<div id="tab-graph">{render_graph(state)}</div>
<script>{JS}</script></body></html>
"""


# --------------------------------------------------------------------------- CLI

def unprivileged_port(text: str) -> int:
    value = int(text)
    if not 1024 <= value <= 65535:
        raise argparse.ArgumentTypeError(f"{text} must be a port from 1024 to 65535")
    return value


def positive_int(text: str) -> int:
    value = int(text)
    if value < 1:
        raise argparse.ArgumentTypeError(f"{text} must be at least 1")
    return value


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="board.py", description="Board tool for /construct.")
    sub = parser.add_subparsers(dest="command", required=True)

    def add(name, fn, help=None):
        p = sub.add_parser(name, help=help, description=help)
        p.add_argument("run", type=Path, metavar="RUN")
        p.set_defaults(fn=fn)
        return p

    p = add("init", cmd_init)
    p.add_argument("--route", required=True, choices=ROUTES,
                   help="single: one chain or about an hour of building, the lead builds it; lanes: a skeleton card, then lanes")
    p.add_argument("--title", required=True)
    p.add_argument("--limit", type=positive_int, default=2)

    p = add("set", cmd_set)
    p.add_argument("--goal")
    p.add_argument("--phase", choices=PHASES)
    p.add_argument("--limit", type=positive_int)
    p.add_argument("--next-input", help="what the lead needs from the user next; empty string clears")
    p.add_argument("--next-input-at", help="when, as HH:MM or an ISO time; empty string clears")
    p.add_argument("--availability", help='e.g. "away until 09:00" or "available"; empty string clears')

    p = add("accept", cmd_accept)
    p.add_argument("id")
    p.add_argument("--text")
    p.add_argument("--side-effect", action="store_true")
    p.add_argument("--status", choices=ACCEPT_STATUSES)
    p.add_argument("--why")

    p = add("team", cmd_team)
    p.add_argument("agent")
    p.add_argument("--role", required=True, choices=ROLES)
    p.add_argument("--tier", required=True)

    p = add("card", cmd_card)
    p.add_argument("id")
    p.add_argument("--update", action="store_true",
                   help="change fields of an existing todo or blocked card; only the given fields change")
    p.add_argument("--title")
    p.add_argument("--builder")
    p.add_argument("--reviewer")
    p.add_argument("--files", nargs="+",
                   help="concrete files the card may touch, not directories (a trailing / or \\ is refused)")
    p.add_argument("--deps", nargs="*")
    p.add_argument("--body-file", type=Path)
    p.add_argument("--repo", help="NAME of a registered repo; required when the card has files")
    p.add_argument("--kind", choices=KINDS, help="build (default) or question (no files, no repo)")
    p.add_argument("--resources", nargs="*", help="shared resources the card needs exclusively, e.g. stand")
    p.add_argument("--estimate", type=positive_int, help="minutes for build plus review, the lead's estimate")
    p.add_argument("--size", choices=SIZES, help="S, M or L (SKILL §Tiers); sets the builder's tier and effort")
    p.add_argument("--review", choices=REVIEWS, help="review depth when not the size's default (L: deep, else standard)")
    p.add_argument("--lane", help="the lane this card belongs to; one worker builds a lane's cards in order")

    p = add("move", cmd_move)
    p.add_argument("id")
    p.add_argument("status", choices=STATUSES)
    p.add_argument("--who", required=True)
    p.add_argument("--why", required=True)
    p.add_argument("--tier", choices=TIERS, help="model tier of this dispatch (doing or review)")
    p.add_argument("--effort", choices=EFFORTS, help="effort level of this dispatch (doing or review)")

    add("eligible", cmd_eligible)

    add("dispatch", cmd_dispatch, help="start every eligible card at its policy tier; print one Agent call per card")

    p = add("returned", cmd_returned,
            help="an agent came back: save its report and take the step its verdict calls for")
    p.add_argument("id")
    p.add_argument("--agent", help="the returned agent's id")
    p.add_argument("--saved", action="store_true", help="act on the report already saved for the current try")
    p.add_argument("--self", type=Path, metavar="FILE", help="the report of a card the lead built itself")
    p.add_argument("--projects-dir", type=Path)

    p = add("brief", cmd_brief, help="re-render a card's brief for its current status and print its Agent call")
    p.add_argument("id")

    p = add("watch", cmd_watch, help="background stall alarm: exits with a line per active card whose agent has gone "
                                     "silent; never stops an agent")
    p.add_argument("--silent", type=positive_int, default=10, help="minutes without a model step (default 10)")
    p.add_argument("--interval", type=positive_int, default=30, help="seconds between checks")
    p.add_argument("--heartbeat", type=float, default=15,
                   help="minutes after which watch exits anyway, waking a lead whose last turn errored (default 15)")
    p.add_argument("--once", action="store_true", help="check once and exit")
    p.add_argument("--projects-dir", type=Path)

    p = add("repo", cmd_repo)
    p.add_argument("path", type=Path)
    p.add_argument("--no-branch", action="store_true",
                   help="register without creating the run branch (a working tree other sessions share)")
    p.add_argument("--gate", help="mechanical gate run on a DONE card's files before review, e.g. "
                                  '"python -m ruff check {files} && python -m ruff format --check {files}"')
    p.add_argument("--gate-glob", default="*.py", help="which of the card's files the gate gets (default *.py)")

    p = add("checkpoint", cmd_checkpoint)
    p.add_argument("id")

    p = add("merge", cmd_merge, help="merge a ref into a repo's run branch as one merge commit (the lead's merge)")
    p.add_argument("repo", help="NAME of a registered repo with a run branch")
    p.add_argument("ref", help="the branch, tag or commit to merge, e.g. origin/main")
    p.add_argument("--conflicts", choices=["theirs"],
                   help="theirs: each conflicted path takes the ref's whole file; without it a conflict aborts")

    add("rollback", cmd_rollback)

    p = add("report", cmd_report)
    p.add_argument("id")
    p.add_argument("kind", choices=["build", "review"])
    p.add_argument("--agent", required=True)
    p.add_argument("--projects-dir", type=Path)

    p = add("handoff", cmd_handoff,
            help="print the Handoff section of each direct dependency's latest build report (read-only)")
    p.add_argument("id")

    p = add("progress", cmd_progress)
    p.add_argument("id")
    p.add_argument("--who", required=True)
    p.add_argument("--text", required=True)

    p = add("log", cmd_log)
    p.add_argument("--who", required=True)
    p.add_argument("--text", required=True)
    p.add_argument("--card")

    add("show", cmd_show)

    p = add("serve", cmd_serve,
            help="start the live viewer detached (idempotent) and print its URL; clears an earlier stop")
    p.add_argument("--foreground", action="store_true", help="serve in this process until interrupted (debugging)")
    p.add_argument("--port", type=unprivileged_port, default=0,
                   help="preferred port when no viewer is running (the exact port with --foreground); 0 picks one")

    add("stop", cmd_stop, help="stop the viewer and keep it stopped: board commands no longer restart it; "
                               "the next `serve` does")

    p = add("_serve", cmd_serve_internal)  # the detached viewer process; started by `serve`
    p.add_argument("--port", type=unprivileged_port, required=True)

    sub.metavar = "{" + ",".join(name for name in sub.choices if not name.startswith("_")) + "}"
    return parser


def main(argv: list[str]) -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    args = build_parser().parse_args(argv)
    args.fn(args)
    if args.command in MUTATING and not os.environ.get("CONSTRUCT_NO_VIEWER"):
        try:
            heal_viewer(args.run)
        except (Exception, SystemExit) as e:
            # The one deliberate report-instead-of-raise: the board change above already succeeded,
            # and a viewer that will not restart must not make that command look failed.
            print(f"viewer: could not restart: {flat(e)}", file=sys.stderr)


if __name__ == "__main__":
    main(sys.argv[1:])
