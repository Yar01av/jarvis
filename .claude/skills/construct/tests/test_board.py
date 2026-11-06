import json
import os
import re
import shlex
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

import pytest

import board


def run(*argv):
    board.main([str(a) for a in argv])


def load(run_dir: Path) -> dict:
    return json.loads((run_dir / "board.json").read_text(encoding="utf-8"))


def card_of(run_dir: Path, cid: str) -> dict:
    return next(c for c in load(run_dir)["cards"] if c["id"] == cid)


@pytest.fixture
def run_dir(tmp_path):
    d = tmp_path / "run1"
    run("init", d, "--title", "Demo", "--limit", "2", "--route", "lanes")
    run("team", d, "implementer", "--role", "builder", "--tier", "sonnet")
    run("team", d, "code-reviewer", "--role", "reviewer", "--tier", "opus")
    run("repo", d, make_repo(tmp_path, [".keep"], name="main"))
    return d


def add_card(run_dir, cid, files=None, deps=(), repo="main", kind=None, resources=()):
    body = run_dir / f"body-{cid}.txt"
    body.write_text(f"body of {cid}", encoding="utf-8")
    args = ["card", run_dir, cid, "--title", f"Title {cid}", "--builder", "implementer",
            "--reviewer", "code-reviewer", "--body-file", body]
    if files:
        args += ["--files", *files]
    if repo and kind != "question":
        args += ["--repo", repo]
    if kind:
        args += ["--kind", kind]
    if resources:
        args += ["--resources", *resources]
    if deps:
        args += ["--deps", *deps]
    run(*args)


def move(run_dir, cid, status, **kw):
    args = ["move", run_dir, cid, status, "--who", "lead", "--why", "test"]
    for k, v in kw.items():
        args += [f"--{k}", v]
    run(*args)


def test_init_creates_layout_and_refuses_existing(tmp_path):
    d = tmp_path / "my-run"
    run("init", d, "--title", "T", "--route", "lanes")
    for sub in ("cards", "reports", "out"):
        assert (d / sub).is_dir()
    state = load(d)
    assert state["slug"] == "my-run"
    assert state["phase"] == "shaping"
    assert state["limit"] == 2
    assert (d / "board.md").read_text(encoding="utf-8").startswith("# Construct: T")
    assert (d / "board.html").exists()
    with pytest.raises(SystemExit):
        run("init", d, "--title", "T", "--route", "lanes")


def test_card_rejects_same_builder_and_reviewer(run_dir):
    run("team", run_dir, "implementer", "--role", "reviewer", "--tier", "sonnet")
    body = run_dir / "b.txt"
    body.write_text("x", encoding="utf-8")
    with pytest.raises(SystemExit, match="builder and reviewer"):
        run("card", run_dir, "C1", "--title", "t", "--builder", "implementer",
            "--reviewer", "implementer", "--files", "a.py", "--repo", "main", "--body-file", body)


def test_card_rejects_agent_missing_from_team_role(run_dir):
    body = run_dir / "b.txt"
    body.write_text("x", encoding="utf-8")
    with pytest.raises(SystemExit, match="ghost"):
        run("card", run_dir, "C1", "--title", "t", "--builder", "ghost",
            "--reviewer", "code-reviewer", "--files", "a.py", "--repo", "main", "--body-file", body)
    # code-reviewer is only a reviewer, so it cannot build
    with pytest.raises(SystemExit, match="code-reviewer"):
        run("card", run_dir, "C1", "--title", "t", "--builder", "code-reviewer",
            "--reviewer", "code-reviewer", "--files", "a.py", "--repo", "main", "--body-file", body)
    with pytest.raises(SystemExit, match="ghost"):
        run("card", run_dir, "C1", "--title", "t", "--builder", "implementer",
            "--reviewer", "ghost", "--files", "a.py", "--repo", "main", "--body-file", body)


def test_card_rejects_unknown_dep(run_dir):
    with pytest.raises(SystemExit, match="C9"):
        add_card(run_dir, "C1", ["a.py"], deps=["C9"])


def test_illegal_transition_refused(run_dir):
    add_card(run_dir, "C1", ["a.py"])
    with pytest.raises(SystemExit, match="illegal transition todo→done for C1"):
        move(run_dir, "C1", "done")


def test_dead_agent_retry_is_not_a_bounce(run_dir):
    add_card(run_dir, "C1", ["a.py"])
    move(run_dir, "C1", "doing")
    move(run_dir, "C1", "todo")
    assert card_of(run_dir, "C1")["since"] is None
    move(run_dir, "C1", "doing")
    c = card_of(run_dir, "C1")
    assert (c["tries"], c["bounces"]) == (2, 0)
    assert c["since"] is not None


def test_review_fail_counts_bounce(run_dir):
    add_card(run_dir, "C1", ["a.py"])
    move(run_dir, "C1", "doing")
    move(run_dir, "C1", "review")
    move(run_dir, "C1", "todo")
    c = card_of(run_dir, "C1")
    assert (c["tries"], c["bounces"], c["status"], c["since"]) == (1, 1, "todo", None)
    log = load(run_dir)["log"]
    assert log[-1]["from"] == "review" and log[-1]["to"] == "todo"


def test_doing_refused_when_dep_not_done(run_dir):
    add_card(run_dir, "C1", ["a.py"])
    add_card(run_dir, "C2", ["b.py"], deps=["C1"])
    with pytest.raises(SystemExit, match="C1"):
        move(run_dir, "C2", "doing")
    assert card_of(run_dir, "C2")["status"] == "todo"


def test_doing_refused_on_file_overlap_with_review_card(run_dir):
    add_card(run_dir, "C1", ["a.py"])
    add_card(run_dir, "C2", ["a.py", "b.py"])
    move(run_dir, "C1", "doing")
    move(run_dir, "C1", "review")
    with pytest.raises(SystemExit, match="a.py"):
        move(run_dir, "C2", "doing")


def test_directory_entry_overlaps_the_files_inside_it(run_dir, capsys):
    add_card(run_dir, "C1", ["pkg"])
    add_card(run_dir, "C2", ["pkg/x.py"])
    add_card(run_dir, "C3", ["pkgx.py"])
    capsys.readouterr()
    run("eligible", run_dir)
    # C2 sits inside C1's entry; C3 merely shares a prefix and is independent
    assert capsys.readouterr().out.split() == ["C1", "C3"]
    move(run_dir, "C1", "doing")
    with pytest.raises(SystemExit, match="pkg/x.py is in use by C1"):
        move(run_dir, "C2", "doing")


def test_doing_refused_at_limit(run_dir):
    for i in (1, 2, 3):
        add_card(run_dir, f"C{i}", [f"f{i}.py"])
    move(run_dir, "C1", "doing")
    move(run_dir, "C2", "doing")
    with pytest.raises(SystemExit, match="limit"):
        move(run_dir, "C3", "doing")


def test_eligible_respects_limit_order_and_batch_overlap(run_dir, capsys):
    run("set", run_dir, "--limit", "3")
    add_card(run_dir, "C10", ["j.py"])
    add_card(run_dir, "C2", ["shared.py"])
    add_card(run_dir, "C3", ["shared.py"])
    add_card(run_dir, "C4", ["d.py"])
    add_card(run_dir, "C5", ["e.py"])
    add_card(run_dir, "C6", ["z.py"], deps=["C5"])
    capsys.readouterr()
    run("eligible", run_dir)
    # numeric order, C3 skipped (overlaps C2 in the batch), C6 waits on C5, limit 3
    assert capsys.readouterr().out.split() == ["C2", "C4", "C5"]
    run("set", run_dir, "--limit", "10")
    capsys.readouterr()
    run("eligible", run_dir)
    assert capsys.readouterr().out.split() == ["C2", "C4", "C5", "C10"]
    run("set", run_dir, "--limit", "2")
    move(run_dir, "C2", "doing")
    capsys.readouterr()
    run("eligible", run_dir)
    # one free slot; C3 overlaps doing C2
    assert capsys.readouterr().out.split() == ["C4"]


def git(repo, *args):
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


def test_eligible_repo_dirty_file_blocks_unless_owned_by_done_card(run_dir, tmp_path, capsys):
    repo = make_repo(tmp_path, ["a.py", "b.py"])
    run("repo", run_dir, repo, "--no-branch")
    (repo / "a.py").write_text("2", encoding="utf-8")
    (repo / "b.py").write_text("2", encoding="utf-8")

    add_card(run_dir, "C1", ["a.py"], repo="repo")
    add_card(run_dir, "C2", ["b.py"], repo="repo")
    add_card(run_dir, "C3", ["a.py"], repo="repo")
    capsys.readouterr()
    run("eligible", run_dir)
    assert capsys.readouterr().out.split() == []
    with pytest.raises(SystemExit, match="a.py"):
        move(run_dir, "C1", "doing")

    # C1 finishes: a.py is owned by a done card, so it stops blocking C3
    git(repo, "checkout", "--", "a.py")
    move(run_dir, "C1", "doing")
    (repo / "a.py").write_text("2", encoding="utf-8")
    move(run_dir, "C1", "review")
    move(run_dir, "C1", "done")
    capsys.readouterr()
    run("eligible", run_dir)
    assert capsys.readouterr().out.split() == ["C3"]
    move(run_dir, "C3", "doing")


def make_transcript(projects, agent_id, messages, session="sess", sub="x", ensure_ascii=True):
    path = projects / session / sub / "subagents" / f"agent-{agent_id}.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    for m in messages:
        if m is None:
            rows.append({"message": {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": "t", "content": "ok"}]}})
        else:
            rows.append({"message": {"role": "assistant", "content": [
                {"type": "text", "text": "thinking"},
                {"type": "tool_use", "name": "SubagentHandback", "input": {"message": m}}]}})
    path.write_text("\n".join(json.dumps(r, ensure_ascii=ensure_ascii) for r in rows) + "\n",
                    encoding="utf-8")
    return path


@pytest.fixture
def doing_card(run_dir):
    add_card(run_dir, "C1", ["a.py"])
    move(run_dir, "C1", "doing")
    return run_dir


def report(run_dir, projects, kind="build", agent="abc"):
    run("report", run_dir, "C1", kind, "--agent", agent, "--projects-dir", projects)


def test_report_saves_last_handback(doing_card, tmp_path, capsys):
    projects = tmp_path / "projects"
    make_transcript(projects, "abc", ["DONE first\nold", None, "PASS final\ndetails here"])
    move(doing_card, "C1", "review")
    capsys.readouterr()
    report(doing_card, projects, "review")
    out = capsys.readouterr().out.splitlines()
    saved = doing_card / "reports" / "C1-review-1.md"
    assert out[0] == "PASS final"
    assert out[1] == str(saved)
    assert saved.read_text(encoding="utf-8") == "PASS final\ndetails here"
    assert card_of(doing_card, "C1")["reports"] == [{"name": "review-1", "verdict": "PASS final"}]
    last = load(doing_card)["log"][-1]
    assert last["who"] == "lead" and last["why"] == "saved review-1: PASS final"


def test_report_fails_without_handback(doing_card, tmp_path):
    projects = tmp_path / "projects"
    path = projects / "s" / "x" / "subagents" / "agent-abc.jsonl"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({"message": {"role": "assistant", "content": [
        {"type": "text", "text": "hi"}]}}) + "\n", encoding="utf-8")
    with pytest.raises(SystemExit, match="SubagentHandback"):
        report(doing_card, projects)


def test_report_fails_on_zero_or_multiple_transcripts(doing_card, tmp_path):
    projects = tmp_path / "projects"
    projects.mkdir()
    with pytest.raises(SystemExit, match="found 0"):
        report(doing_card, projects)
    make_transcript(projects, "abc", ["DONE"], session="s1")
    make_transcript(projects, "abc", ["DONE"], session="s2")
    with pytest.raises(SystemExit, match="found 2"):
        report(doing_card, projects)


def test_report_refuses_overwrite(doing_card, tmp_path):
    projects = tmp_path / "projects"
    make_transcript(projects, "abc", ["DONE"])
    report(doing_card, projects)
    with pytest.raises(SystemExit, match="exists"):
        report(doing_card, projects)
    assert len(card_of(doing_card, "C1")["reports"]) == 1


def test_progress_only_while_active_and_capped(run_dir):
    add_card(run_dir, "C1", ["a.py"])
    with pytest.raises(SystemExit):
        run("progress", run_dir, "C1", "--who", "w", "--text", "x")
    move(run_dir, "C1", "doing")
    log_len = len(load(run_dir)["log"])
    run("progress", run_dir, "C1", "--who", "w", "--text", "y" * 300)
    assert len(card_of(run_dir, "C1")["progress"][0]["text"]) == 200
    for i in range(25):
        run("progress", run_dir, "C1", "--who", "w", "--text", f"n{i}")
    notes = card_of(run_dir, "C1")["progress"]
    assert len(notes) == 20 and notes[-1]["text"] == "n24" and notes[0]["text"] == "n5"
    assert len(load(run_dir)["log"]) == log_len


def test_render_places_cards_in_columns_and_shows_owner(run_dir):
    add_card(run_dir, "C1", ["a.py"])
    add_card(run_dir, "C2", ["b.py"], deps=["C1"])
    move(run_dir, "C1", "doing")
    run("progress", run_dir, "C1", "--who", "implementer", "--text", "<b>wired</b>")
    html_text = (run_dir / "board.html").read_text(encoding="utf-8")
    assert "setTimeout" in html_text and "location.reload()" in html_text
    assert 'http-equiv="refresh"' not in html_text
    assert "<b>wired</b>" not in html_text and "&lt;b&gt;wired&lt;/b&gt;" in html_text

    assert "C1" in section(html_text, "doing") and "building · implementer" in section(html_text, "doing")
    assert "C2" in section(html_text, "todo") and "waits on C1" in section(html_text, "todo")
    assert 'class="id">C1<' not in section(html_text, "todo")
    assert "1 working" in html_text and "building C1" in html_text

    md = (run_dir / "board.md").read_text(encoding="utf-8")
    assert md.startswith("# Construct: Demo")
    assert "| C1 | Title C1 | doing | implementer | " in md
    assert "| C2 | Title C2 | todo | " in md


def test_lock_timeout_fails(run_dir, monkeypatch):
    (run_dir / "board.lock").write_text("", encoding="utf-8")
    monkeypatch.setattr(board, "LOCK_TIMEOUT", 0.3)
    with pytest.raises(SystemExit, match="board locked"):
        run("set", run_dir, "--goal", "x")
    assert (run_dir / "board.lock").exists()


# ------------------------------------------------------------------ helpers (repo, html)

def make_repo(tmp_path, files, name="repo"):
    repo = tmp_path / name
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
    git(repo, "config", "user.email", "t@example.com")
    git(repo, "config", "user.name", "t")
    git(repo, "config", "core.autocrlf", "false")
    for name in files:
        (repo / name).write_text("1", encoding="utf-8")
    git(repo, "add", ".")
    git(repo, "commit", "-m", "init")
    return repo


def section(html_text, name):
    start = html_text.index(f'data-col="{name}"')
    nxt = html_text.find('data-col="', start + 10)
    return html_text[start:nxt if nxt != -1 else len(html_text)]


def html_of(run_dir):
    return (run_dir / "board.html").read_text(encoding="utf-8")


def eligible(run_dir, capsys, *extra):
    capsys.readouterr()
    run("eligible", run_dir, *extra)
    return capsys.readouterr()


# ------------------------------------------------------------------ blockers

def test_bounced_card_restarts_under_repo(run_dir, tmp_path, capsys):
    repo = make_repo(tmp_path, ["a.py"])
    run("repo", run_dir, repo)
    add_card(run_dir, "C1", ["a.py"], repo="repo")
    move(run_dir, "C1", "doing")
    (repo / "a.py").write_text("2", encoding="utf-8")
    move(run_dir, "C1", "review")
    move(run_dir, "C1", "todo")
    assert eligible(run_dir, capsys).out.split() == ["C1"]
    move(run_dir, "C1", "doing")
    assert card_of(run_dir, "C1")["status"] == "doing"


def test_first_dispatch_dirt_blocks_and_eligible_names_the_skip_on_stderr(run_dir, tmp_path, capsys):
    repo = make_repo(tmp_path, ["a.py"])
    run("repo", run_dir, repo)
    (repo / "a.py").write_text("2", encoding="utf-8")
    add_card(run_dir, "C1", ["a.py"], repo="repo")
    add_card(run_dir, "C2", ["b.py"], deps=["C1"], repo="repo")
    out = eligible(run_dir, capsys)
    assert out.out == ""
    lines = out.err.strip().split("\n")
    assert lines[0].startswith("C1 skipped: ") and "a.py" in lines[0]
    assert lines[1] == "C2 skipped: waits on C1"


def test_refusal_does_not_repeat_the_card_id(run_dir):
    add_card(run_dir, "C1", ["a.py"])
    add_card(run_dir, "C2", ["b.py"], deps=["C1"])
    with pytest.raises(SystemExit) as e:
        move(run_dir, "C2", "doing")
    assert str(e.value) == "C2 cannot start: waits on C1"


# ------------------------------------------------------------------ transcripts

def test_report_survives_raw_unicode_line_separators(doing_card, tmp_path):
    projects = tmp_path / "projects"
    make_transcript(projects, "abc", ["PASS a b\nmore\u0085end"], ensure_ascii=False)
    report(doing_card, projects)
    saved = (doing_card / "reports" / "C1-build-1.md").read_text(encoding="utf-8")
    assert saved == "PASS a b\nmore\u0085end"
    assert card_of(doing_card, "C1")["reports"][0]["verdict"] == "PASS a b"


def test_verdict_is_first_non_blank_line(doing_card, tmp_path):
    projects = tmp_path / "projects"
    make_transcript(projects, "abc", ["\n  \nPASS late\nrest"])
    report(doing_card, projects)
    assert card_of(doing_card, "C1")["reports"][0]["verdict"] == "PASS late"


def test_report_skips_malformed_rows(doing_card, tmp_path):
    projects = tmp_path / "projects"
    path = make_transcript(projects, "abc", ["PASS ok"])
    junk = [{"message": None}, {"type": "summary"},
            {"message": {"role": "assistant", "content": "plain string"}},
            {"message": {"role": "assistant", "content": [{"text": "no type"}]}}]
    path.write_text("\n".join(json.dumps(r) for r in junk) + "\n" + path.read_text(encoding="utf-8"),
                    encoding="utf-8")
    report(doing_card, projects)
    assert card_of(doing_card, "C1")["reports"][0]["verdict"] == "PASS ok"


def test_report_rerecords_identical_file_but_refuses_different_text(doing_card, tmp_path):
    projects = tmp_path / "projects"
    make_transcript(projects, "abc", ["PASS same\nbody"])
    saved = doing_card / "reports" / "C1-build-1.md"
    saved.write_bytes("PASS same\nbody".encode("utf-8"))
    report(doing_card, projects)
    assert card_of(doing_card, "C1")["reports"] == [{"name": "build-1", "verdict": "PASS same"}]
    move(doing_card, "C1", "review")
    other = doing_card / "reports" / "C1-review-1.md"
    other.write_text("different", encoding="utf-8")
    with pytest.raises(SystemExit, match="exists"):
        report(doing_card, projects, "review")
    assert other.read_text(encoding="utf-8") == "different"


# ------------------------------------------------------------------ save / lock / encoding

def test_save_retries_permission_error_then_gives_up(run_dir, monkeypatch):
    monkeypatch.setattr(board, "REPLACE_DELAY", 0)
    real = Path.replace
    calls = {"n": 0}

    def flaky(self, target):
        if Path(target).name != "board.json":
            return real(self, target)
        calls["n"] += 1
        if calls["n"] <= 3:
            raise PermissionError("held open")
        return real(self, target)

    monkeypatch.setattr(Path, "replace", flaky)
    run("set", run_dir, "--goal", "g")
    assert calls["n"] == 4 and load(run_dir)["goal"] == "g"

    calls["n"] = -1000
    with pytest.raises(PermissionError):
        run("set", run_dir, "--goal", "h")
    assert calls["n"] == -1000 + board.REPLACE_ATTEMPTS
    assert not (run_dir / "board.lock").exists()


def test_show_survives_a_non_cp1252_title_under_captured_output(tmp_path):
    d = tmp_path / "run1"
    run("init", d, "--title", "Demo", "--route", "lanes")
    run("team", d, "implementer", "--role", "builder", "--tier", "sonnet")
    run("team", d, "code-reviewer", "--role", "reviewer", "--tier", "opus")
    run("repo", d, make_repo(tmp_path, [".keep"], name="main"))
    body = d / "b.txt"
    body.write_text("x", encoding="utf-8")
    run("card", d, "C1", "--title", "a → b", "--builder", "implementer", "--reviewer", "code-reviewer",
        "--files", "b.py", "--repo", "main", "--body-file", body)
    env = {k: v for k, v in os.environ.items() if k not in ("PYTHONIOENCODING", "PYTHONUTF8")}
    done = subprocess.run([sys.executable, board.__file__, "show", str(d)], capture_output=True, env=env)
    assert done.returncode == 0, done.stderr.decode("utf-8", "replace")
    assert "a → b" in done.stdout.decode("utf-8")
    assert "main" in done.stdout.decode("utf-8") and "build" in done.stdout.decode("utf-8")


def test_lock_holds_pid_and_timeout_message_names_it(run_dir, monkeypatch):
    with board.locked(run_dir):
        content = (run_dir / "board.lock").read_text(encoding="utf-8")
    assert content.startswith(f"pid={os.getpid()} since=")
    (run_dir / "board.lock").write_text("pid=4242 since=2026-01-01T00:00:00", encoding="utf-8")
    monkeypatch.setattr(board, "LOCK_TIMEOUT", 0.2)
    with pytest.raises(SystemExit) as e:
        run("set", run_dir, "--goal", "x")
    assert "pid=4242" in str(e.value) and "if that process is gone, delete board.lock" in str(e.value)


# ------------------------------------------------------------------ porcelain

def test_non_ascii_dirty_path_owned_by_done_card_does_not_block(run_dir, tmp_path, capsys):
    repo = make_repo(tmp_path, ["café.py"])
    run("repo", run_dir, repo, "--no-branch")
    add_card(run_dir, "C1", ["café.py"], repo="repo")
    add_card(run_dir, "C2", ["café.py"], repo="repo")
    move(run_dir, "C1", "doing")
    (repo / "café.py").write_text("2", encoding="utf-8")
    move(run_dir, "C1", "review")
    move(run_dir, "C1", "done")
    assert board.porcelain_paths(repo, ["café.py"]) == ["café.py"]
    assert eligible(run_dir, capsys).out.split() == ["C2"]


def test_rename_counts_both_paths(tmp_path):
    repo = make_repo(tmp_path, ["a.py"])
    git(repo, "mv", "a.py", "b.py")
    assert sorted(board.porcelain_paths(repo, ["a.py", "b.py"])) == ["a.py", "b.py"]


def test_card_refuses_directory_entries(run_dir):
    for entry in ("pkg/", "pkg\\"):
        with pytest.raises(SystemExit, match="concrete files"):
            add_card(run_dir, "C1", [entry])


# ------------------------------------------------------------------ card --update

def test_card_update_replaces_only_given_fields(run_dir):
    add_card(run_dir, "C1", ["a.py"])
    add_card(run_dir, "C2", ["b.py"])
    body = run_dir / "new.txt"
    body.write_text("new body", encoding="utf-8")
    run("card", run_dir, "C2", "--update", "--title", "Renamed", "--files", "c.py", "d.py",
        "--deps", "C1", "--body-file", body)
    c = card_of(run_dir, "C2")
    assert (c["title"], c["files"], c["deps"], c["builder"]) == ("Renamed", ["c.py", "d.py"], ["C1"], "implementer")
    assert (run_dir / "cards" / "C2.md").read_text(encoding="utf-8") == "new body"
    run("card", run_dir, "C2", "--update", "--title", "Again")
    c = card_of(run_dir, "C2")
    assert (c["title"], c["files"], c["deps"]) == ("Again", ["c.py", "d.py"], ["C1"])
    assert load(run_dir)["log"][-1]["why"] == "card C2 updated"


def test_card_update_guards(run_dir):
    add_card(run_dir, "C1", ["a.py"])
    with pytest.raises(SystemExit, match="already exists"):
        add_card(run_dir, "C1", ["a.py"])
    with pytest.raises(SystemExit, match="unknown dep C9"):
        run("card", run_dir, "C1", "--update", "--deps", "C9")
    with pytest.raises(SystemExit, match="concrete files"):
        run("card", run_dir, "C1", "--update", "--files", "pkg/")
    with pytest.raises(SystemExit, match="ghost"):
        run("card", run_dir, "C1", "--update", "--builder", "ghost")
    with pytest.raises(SystemExit, match="unknown card"):
        run("card", run_dir, "C7", "--update", "--title", "x")
    move(run_dir, "C1", "doing")
    with pytest.raises(SystemExit, match="only todo or blocked"):
        run("card", run_dir, "C1", "--update", "--title", "x")
    move(run_dir, "C1", "blocked")
    run("card", run_dir, "C1", "--update", "--title", "ok")
    assert card_of(run_dir, "C1")["title"] == "ok"


# ------------------------------------------------------------------ limits and transitions

def test_limit_must_be_positive(run_dir):
    with pytest.raises(SystemExit):
        run("set", run_dir, "--limit", "0")
    with pytest.raises(SystemExit):
        run("init", run_dir.parent / "other", "--title", "T", "--limit", "0", "--route", "lanes")


def test_review_card_does_not_use_a_slot(run_dir, capsys):
    run("set", run_dir, "--limit", "1")
    add_card(run_dir, "C1", ["a.py"])
    add_card(run_dir, "C2", ["b.py"])
    move(run_dir, "C1", "doing")
    move(run_dir, "C1", "review")
    assert eligible(run_dir, capsys).out.split() == ["C2"]


def test_blocked_card_is_never_eligible_and_cannot_restart_directly(run_dir, capsys):
    add_card(run_dir, "C1", ["a.py"])
    move(run_dir, "C1", "doing")
    move(run_dir, "C1", "blocked")
    assert card_of(run_dir, "C1")["status"] == "blocked"
    assert eligible(run_dir, capsys).out.split() == []
    with pytest.raises(SystemExit, match="illegal transition blocked→doing"):
        move(run_dir, "C1", "doing")
    move(run_dir, "C1", "todo")
    assert eligible(run_dir, capsys).out.split() == ["C1"]


# ------------------------------------------------------------------ rendering

def test_card_title_is_escaped_in_tile(run_dir):
    body = run_dir / "b.txt"
    body.write_text("x", encoding="utf-8")
    run("card", run_dir, "C1", "--title", "<script>alert(1)</script>", "--builder", "implementer",
        "--reviewer", "code-reviewer", "--files", "a.py", "--repo", "main", "--body-file", body)
    text = html_of(run_dir)
    assert "<script>alert(1)</script>" not in text
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in section(text, "todo")


def test_md_flattens_newlines_in_cells_and_items(run_dir):
    body = run_dir / "b.txt"
    body.write_text("x", encoding="utf-8")
    run("card", run_dir, "C1", "--title", "A\nB", "--builder", "implementer",
        "--reviewer", "code-reviewer", "--files", "a.py", "--repo", "main", "--body-file", body)
    run("accept", run_dir, "A1", "--text", "one\ntwo")
    md = (run_dir / "board.md").read_text(encoding="utf-8")
    assert "| C1 | A B | todo |" in md
    assert "- C1: A B " in md
    assert "A1: one two" in md


def test_viewer_favicon_blocked_reason_bounce_reason_and_reviewer_elapsed(run_dir):
    add_card(run_dir, "C1", ["a.py"])
    add_card(run_dir, "C2", ["b.py"])
    assert '<link rel="icon" href="data:,">' in html_of(run_dir)
    move(run_dir, "C1", "doing")
    move(run_dir, "C1", "blocked", why="needs creds")
    move(run_dir, "C2", "doing")
    move(run_dir, "C2", "review")
    text = html_of(run_dir)
    assert "needs creds" in section(text, "blocked")
    assert "reviewing C2 · <span data-since=" in text
    move(run_dir, "C2", "todo", why="tests missing")
    text = html_of(run_dir)
    assert "bounced 1" in section(text, "todo") and "tests missing" in section(text, "todo")


# ------------------------------------------------------------------ held files

def test_update_cannot_adopt_foreign_dirt_after_a_retry(run_dir, tmp_path, capsys):
    repo = make_repo(tmp_path, ["a.py", "b.py", "u.py"])
    run("repo", run_dir, repo)
    add_card(run_dir, "C1", ["a.py"], repo="repo")
    move(run_dir, "C1", "doing")
    move(run_dir, "C1", "todo")
    (repo / "b.py").write_text("2", encoding="utf-8")
    (repo / "u.py").write_text("2", encoding="utf-8")
    run("card", run_dir, "C1", "--update", "--files", "a.py", "b.py", "u.py")
    out = eligible(run_dir, capsys)
    assert out.out == "" and "b.py" in out.err
    with pytest.raises(SystemExit, match="b.py"):
        move(run_dir, "C1", "doing")


def test_retry_refused_when_a_blocked_sibling_holds_the_shared_file(run_dir, tmp_path):
    repo = make_repo(tmp_path, ["a.py", "s.py"])
    run("repo", run_dir, repo)
    add_card(run_dir, "C1", ["a.py", "s.py"], repo="repo")
    add_card(run_dir, "C2", ["s.py"], repo="repo")
    move(run_dir, "C2", "doing")
    move(run_dir, "C2", "todo")
    move(run_dir, "C1", "doing")
    (repo / "s.py").write_text("half", encoding="utf-8")
    move(run_dir, "C1", "blocked")
    with pytest.raises(SystemExit, match="s.py"):
        move(run_dir, "C2", "doing")


def test_directory_entry_without_slash_is_refused_by_name(run_dir, tmp_path):
    repo = make_repo(tmp_path, ["a.py"])
    run("repo", run_dir, repo)
    (repo / "pkg").mkdir()
    (repo / "pkg" / "x.py").write_text("2", encoding="utf-8")
    add_card(run_dir, "C1", ["pkg"], repo="repo")
    with pytest.raises(SystemExit, match="file-set entry pkg matches pkg/x.py; list concrete files"):
        move(run_dir, "C1", "doing")


def test_literal_pathspecs_do_not_glob(run_dir, tmp_path, capsys):
    repo = make_repo(tmp_path, ["a.py"])
    run("repo", run_dir, repo)
    (repo / "a.py").write_text("2", encoding="utf-8")
    add_card(run_dir, "C1", ["[ab].py"], repo="repo")
    assert eligible(run_dir, capsys).out.split() == ["C1"]


def test_card_refuses_absolute_and_parent_paths(run_dir):
    for entry in ("/etc/x.py", "C:/x.py", "C:\\x.py", "../x.py", "a/../../x.py"):
        with pytest.raises(SystemExit, match="relative"):
            add_card(run_dir, "C1", [entry])


# ------------------------------------------------------------------ deps graph

def test_update_refuses_cycles_and_self_dep_and_can_clear(run_dir):
    add_card(run_dir, "C1", ["a.py"])
    add_card(run_dir, "C2", ["b.py"], deps=["C1"])
    add_card(run_dir, "C3", ["c.py"], deps=["C2"])
    with pytest.raises(SystemExit, match="deps would create a cycle C1→C2→C1"):
        run("card", run_dir, "C1", "--update", "--deps", "C2")
    with pytest.raises(SystemExit, match="deps would create a cycle C1→C3→C2→C1"):
        run("card", run_dir, "C1", "--update", "--deps", "C3")
    with pytest.raises(SystemExit, match="cycle C1→C1"):
        run("card", run_dir, "C1", "--update", "--deps", "C1")
    run("card", run_dir, "C3", "--update", "--deps")
    assert card_of(run_dir, "C3")["deps"] == []


def test_update_needs_a_field(run_dir):
    add_card(run_dir, "C1", ["a.py"])
    with pytest.raises(SystemExit, match="nothing to update"):
        run("card", run_dir, "C1", "--update")


# ------------------------------------------------------------------ report

def test_report_retry_after_failed_save_records_once_with_lf_bytes(doing_card, tmp_path, monkeypatch):
    projects = tmp_path / "projects"
    make_transcript(projects, "abc", ["PASS x\nbody"])
    real = board.save
    calls = {"n": 0}

    def fail_once(run_dir, state):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("disk")
        real(run_dir, state)

    monkeypatch.setattr(board, "save", fail_once)
    with pytest.raises(RuntimeError):
        report(doing_card, projects)
    assert card_of(doing_card, "C1")["reports"] == []
    report(doing_card, projects)
    assert card_of(doing_card, "C1")["reports"] == [{"name": "build-1", "verdict": "PASS x"}]
    assert (doing_card / "reports" / "C1-build-1.md").read_bytes() == b"PASS x\nbody"
    assert len([e for e in load(doing_card)["log"] if e["why"].startswith("saved")]) == 1


def test_report_kind_must_match_card_status(doing_card, tmp_path):
    projects = tmp_path / "projects"
    make_transcript(projects, "abc", ["PASS x"])
    with pytest.raises(SystemExit, match="review report needs a card in review"):
        report(doing_card, projects, "review")
    move(doing_card, "C1", "review")
    with pytest.raises(SystemExit, match="build report needs a card in doing"):
        report(doing_card, projects, "build")


def test_report_refuses_when_entry_exists_but_file_is_missing(doing_card, tmp_path):
    projects = tmp_path / "projects"
    make_transcript(projects, "abc", ["PASS x"])
    report(doing_card, projects)
    (doing_card / "reports" / "C1-build-1.md").unlink()
    with pytest.raises(SystemExit, match="already recorded"):
        report(doing_card, projects)
    assert len(card_of(doing_card, "C1")["reports"]) == 1


# ------------------------------------------------------------------ transitions, md

def test_review_card_cannot_be_updated_and_review_to_blocked_is_legal(run_dir):
    add_card(run_dir, "C1", ["a.py"])
    move(run_dir, "C1", "doing")
    move(run_dir, "C1", "review")
    with pytest.raises(SystemExit, match="only todo or blocked"):
        run("card", run_dir, "C1", "--update", "--title", "x")
    move(run_dir, "C1", "blocked")
    assert card_of(run_dir, "C1")["status"] == "blocked"


def test_md_flattens_log_reasons_and_unicode_separators(run_dir):
    run("log", run_dir, "--who", "w", "--text", "a\nb\u2028c")
    md = (run_dir / "board.md").read_text(encoding="utf-8")
    assert " w: a b c\n" in md
    assert board.flat("a\u2028b\u2029c\u0085d\r\ne") == "a b c d e"


# ------------------------------------------------------------------ lock edge cases

def test_lock_write_failure_releases_the_lock(run_dir, monkeypatch):
    def boom():
        raise RuntimeError("clock")

    monkeypatch.setattr(board, "now", boom)
    with pytest.raises(RuntimeError):
        board.mutate(run_dir, lambda state: None)
    assert not (run_dir / "board.lock").exists()


def test_lock_vanishing_while_timing_out_is_a_retry(run_dir, monkeypatch):
    lock = run_dir / "board.lock"
    lock.write_text("pid=1 since=x", encoding="utf-8")
    monkeypatch.setattr(board, "LOCK_TIMEOUT", 0)
    real = Path.read_text

    def vanish(self, *a, **kw):
        if self == lock:
            lock.unlink()
            raise FileNotFoundError(str(self))
        return real(self, *a, **kw)

    monkeypatch.setattr(Path, "read_text", vanish)
    run("set", run_dir, "--goal", "g")
    assert load(run_dir)["goal"] == "g"


# ------------------------------------------------------------------ run repos and git

def git_out(repo, *args):
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True,
                          text=True).stdout.strip()


def bare_run(tmp_path, name="run2"):
    d = tmp_path / name
    run("init", d, "--title", "Demo", "--limit", "3", "--route", "lanes")
    run("team", d, "implementer", "--role", "builder", "--tier", "sonnet")
    run("team", d, "code-reviewer", "--role", "reviewer", "--tier", "opus")
    return d


def test_repo_registers_and_switches_branch(tmp_path):
    d = bare_run(tmp_path)
    repo = make_repo(tmp_path, ["a.py"], name="proj")
    original = git_out(repo, "branch", "--show-current")
    base = git_out(repo, "rev-parse", "HEAD")
    run("repo", d, repo)
    assert git_out(repo, "branch", "--show-current") == "construct/run2"
    assert load(d)["repos"] == [{"path": repo.resolve().as_posix(), "name": "proj",
                                 "original_branch": original, "base": base, "branch": "construct/run2",
                                 "gate": None, "gate_glob": "*.py"}]
    assert load(d)["log"][-1]["why"].startswith("repo proj")


def test_repo_refuses_duplicate_branch_and_non_repo(tmp_path):
    d = bare_run(tmp_path)
    plain = tmp_path / "plain"
    plain.mkdir()
    with pytest.raises(SystemExit, match="not a git repo"):
        run("repo", d, plain)
    repo = make_repo(tmp_path, ["a.py"], name="proj")
    run("repo", d, repo)
    with pytest.raises(SystemExit, match="already registered"):
        run("repo", d, repo)
    # the branch exists already in another repo state: a fresh run slug colliding with it
    other = make_repo(tmp_path, ["a.py"], name="other")
    git(other, "branch", "construct/run2")
    with pytest.raises(SystemExit, match="branch construct/run2 already exists"):
        run("repo", d, other)
    assert len(load(d)["repos"]) == 1
    detached = make_repo(tmp_path, ["a.py"], name="detached")
    git(detached, "checkout", "--detach")
    with pytest.raises(SystemExit, match="detached"):
        run("repo", d, detached)


def test_card_with_files_requires_registered_repo(tmp_path):
    d = bare_run(tmp_path)
    body = d / "b.txt"
    body.write_text("x", encoding="utf-8")
    base = ["card", d, "C1", "--title", "t", "--builder", "implementer", "--reviewer", "code-reviewer",
            "--files", "a.py", "--body-file", body]
    with pytest.raises(SystemExit, match="--repo NAME is required"):
        run(*base)
    with pytest.raises(SystemExit, match="unknown repo ghost"):
        run(*base, "--repo", "ghost")
    run("repo", d, make_repo(tmp_path, ["a.py"], name="proj"))
    run(*base, "--repo", "proj")
    assert card_of(d, "C1")["repo"] == "proj"


def test_same_path_in_two_repos_is_not_an_overlap(run_dir, tmp_path, capsys):
    run("repo", run_dir, make_repo(tmp_path, ["a.py"], name="second"))
    add_card(run_dir, "C1", ["a.py"], repo="main")
    add_card(run_dir, "C2", ["a.py"], repo="second")
    add_card(run_dir, "C3", ["a.py"], repo="main")
    run("set", run_dir, "--limit", "3")
    assert eligible(run_dir, capsys).out.split() == ["C1", "C2"]
    move(run_dir, "C1", "doing")
    move(run_dir, "C2", "doing")
    with pytest.raises(SystemExit, match="file a.py is in use by C1"):
        move(run_dir, "C3", "doing")


def test_question_card_has_no_files_and_counts_toward_limit(run_dir):
    run("set", run_dir, "--limit", "1")
    add_card(run_dir, "C1", kind="question")
    c = card_of(run_dir, "C1")
    assert (c["kind"], c["files"], c["repo"]) == ("question", [], None)
    add_card(run_dir, "C2", ["a.py"])
    move(run_dir, "C1", "doing")
    with pytest.raises(SystemExit, match="limit"):
        move(run_dir, "C2", "doing")


def test_question_card_refuses_files_and_checkpoint(run_dir):
    body = run_dir / "b.txt"
    body.write_text("x", encoding="utf-8")
    with pytest.raises(SystemExit, match="question cards have no files"):
        run("card", run_dir, "C1", "--title", "t", "--builder", "implementer", "--reviewer", "code-reviewer",
            "--kind", "question", "--files", "a.py", "--body-file", body)
    add_card(run_dir, "C1", kind="question")
    move(run_dir, "C1", "doing")
    move(run_dir, "C1", "review")
    with pytest.raises(SystemExit, match="question"):
        run("checkpoint", run_dir, "C1")


def test_resource_is_exclusive_across_doing_review_and_batch(run_dir, capsys):
    run("set", run_dir, "--limit", "3")
    add_card(run_dir, "C1", ["a.py"], resources=["stand"])
    add_card(run_dir, "C2", ["b.py"], resources=["stand", "other"])
    add_card(run_dir, "C3", ["c.py"], resources=["other"])
    out = eligible(run_dir, capsys)
    assert out.out.split() == ["C1", "C3"]
    assert "C2 skipped: resource stand is in use by C1" in out.err
    move(run_dir, "C1", "doing")
    with pytest.raises(SystemExit, match="resource stand is in use by C1"):
        move(run_dir, "C2", "doing")
    move(run_dir, "C1", "review")
    with pytest.raises(SystemExit, match="resource stand is in use by C1"):
        move(run_dir, "C2", "doing")
    move(run_dir, "C1", "done")
    move(run_dir, "C2", "doing")


def test_card_update_changes_repo_kind_and_resources(run_dir, tmp_path):
    run("repo", run_dir, make_repo(tmp_path, [".keep"], name="second"))
    add_card(run_dir, "C1", ["a.py"])
    run("card", run_dir, "C1", "--update", "--repo", "second", "--resources", "stand")
    c = card_of(run_dir, "C1")
    assert (c["repo"], c["resources"]) == ("second", ["stand"])
    with pytest.raises(SystemExit, match="unknown repo ghost"):
        run("card", run_dir, "C1", "--update", "--repo", "ghost")
    run("card", run_dir, "C1", "--update", "--resources")
    assert card_of(run_dir, "C1")["resources"] == []
    run("card", run_dir, "C1", "--update", "--kind", "question")
    c = card_of(run_dir, "C1")
    assert (c["kind"], c["files"], c["repo"]) == ("question", [], None)
    with pytest.raises(SystemExit, match="--files is required"):
        run("card", run_dir, "C1", "--update", "--kind", "build")


def passing_review(run_dir, tmp_path, cid="C1", edit=None):
    """Move a card through doing -> review with a build report and a PASS review report; `edit` plays
    the builder's edits."""
    projects = tmp_path / "projects"
    make_transcript(projects, f"b{cid}", ["DONE built\nbody"])
    make_transcript(projects, f"r{cid}", ["PASS reviewed\nbody"])
    move(run_dir, cid, "doing")
    if edit:
        edit()
    run("report", run_dir, cid, "build", "--agent", f"b{cid}", "--projects-dir", projects)
    move(run_dir, cid, "review")
    run("report", run_dir, cid, "review", "--agent", f"r{cid}", "--projects-dir", projects)


def test_checkpoint_commits_only_card_files_and_records_sha(run_dir, tmp_path, capsys):
    repo = tmp_path / "main"
    add_card(run_dir, "C1", ["a.py"])
    add_card(run_dir, "C2", ["b.py"])
    passing_review(run_dir, tmp_path, edit=lambda: (repo / "a.py").write_text("mine", encoding="utf-8"))
    move(run_dir, "C2", "doing")
    (repo / "b.py").write_text("sibling", encoding="utf-8")
    capsys.readouterr()
    run("checkpoint", run_dir, "C1")
    sha = git_out(repo, "rev-parse", "HEAD")
    assert capsys.readouterr().out.split() == [sha]
    assert card_of(run_dir, "C1")["commit"] == sha
    assert git_out(repo, "show", "--name-only", "--format=", "HEAD").split() == ["a.py"]
    assert git_out(repo, "status", "--porcelain").split() == ["??", "b.py"]
    message = git_out(repo, "log", "-1", "--format=%B")
    assert message.splitlines()[0] == "construct(run1): C1 Title C1"
    assert "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>" in message
    assert "checkpoint" in load(run_dir)["log"][-1]["why"]


def test_checkpoint_refuses_without_pass_or_off_branch(run_dir, tmp_path):
    repo = tmp_path / "main"
    add_card(run_dir, "C1", ["a.py"])
    with pytest.raises(SystemExit, match="needs a card in review"):
        run("checkpoint", run_dir, "C1")
    move(run_dir, "C1", "doing")
    (repo / "a.py").write_text("mine", encoding="utf-8")
    move(run_dir, "C1", "review")
    with pytest.raises(SystemExit, match="PASS"):
        run("checkpoint", run_dir, "C1")
    projects = tmp_path / "projects"
    make_transcript(projects, "r1", ["FAIL nope"])
    run("report", run_dir, "C1", "review", "--agent", "r1", "--projects-dir", projects)
    with pytest.raises(SystemExit, match="PASS"):
        run("checkpoint", run_dir, "C1")
    move(run_dir, "C1", "todo")
    passing_review(run_dir, tmp_path)
    git(repo, "switch", "-c", "elsewhere")
    with pytest.raises(SystemExit, match="construct/run1"):
        run("checkpoint", run_dir, "C1")
    assert "commit" not in card_of(run_dir, "C1")


def test_checkpoint_refuses_when_nothing_changed(run_dir, tmp_path):
    add_card(run_dir, "C1", ["a.py"])
    passing_review(run_dir, tmp_path)
    with pytest.raises(SystemExit, match="nothing changed"):
        run("checkpoint", run_dir, "C1")


def test_rollback_prints_plan_and_applying_it_restores_base(run_dir, tmp_path, capsys):
    repo = tmp_path / "main"
    state = load(run_dir)["repos"][0]
    add_card(run_dir, "C1", ["a.py"])
    passing_review(run_dir, tmp_path, edit=lambda: (repo / "a.py").write_text("mine", encoding="utf-8"))
    run("checkpoint", run_dir, "C1")
    sha = card_of(run_dir, "C1")["commit"]
    (repo / "stray.py").write_text("dirt", encoding="utf-8")
    before = (run_dir / "board.json").read_text(encoding="utf-8")
    capsys.readouterr()
    run("rollback", run_dir)
    out = capsys.readouterr().out
    assert (run_dir / "board.json").read_text(encoding="utf-8") == before
    assert git_out(repo, "branch", "--show-current") == "construct/run1"
    assert state["base"] in out and "1 commit" in out and f"{sha[:7]} C1 Title C1" in out
    assert f'git -C "{state["path"]}" revert {sha}' in out
    assert "uncommitted" in out.lower()
    commands = [ln.strip() for ln in out.splitlines() if ln.strip().startswith("git -C")
                and " revert " not in ln]
    assert commands == [f'git -C "{state["path"]}" switch {state["original_branch"]}',
                        f'git -C "{state["path"]}" branch -D construct/run1']
    for cmd in commands:
        subprocess.run(shlex.split(cmd), check=True, capture_output=True)
    assert git_out(repo, "rev-parse", "HEAD") == state["base"]
    assert git_out(repo, "branch", "--show-current") == state["original_branch"]


def test_dirty_check_uses_card_repo(run_dir, tmp_path, capsys):
    other = make_repo(tmp_path, ["a.py"], name="other")
    run("repo", run_dir, other)
    (other / "a.py").write_text("dirt", encoding="utf-8")
    add_card(run_dir, "C1", ["a.py"], repo="other")
    add_card(run_dir, "C2", ["a.py"], repo="main")
    out = eligible(run_dir, capsys)
    assert out.out.split() == ["C2"]
    assert "C1 skipped" in out.err and "a.py" in out.err


# ------------------------------------------------------------------ lessons

def test_lessons_section_collected_and_none_skipped(run_dir, tmp_path):
    projects = tmp_path / "projects"
    add_card(run_dir, "C1", ["a.py"])
    move(run_dir, "C1", "doing")
    make_transcript(projects, "b1", ["PASS built\n\n## Lessons\n- stand needs a restart\n- second\n"
                                     "## Notes\nunrelated"])
    run("report", run_dir, "C1", "build", "--agent", "b1", "--projects-dir", projects)
    lessons = run_dir / "lessons.md"
    text = lessons.read_text(encoding="utf-8")
    assert text.startswith("# Lessons from run run1\n")
    assert re.search(r"### C1 build-1 \(implementer\), \d\d:\d\d\n", text)
    assert "- stand needs a restart\n- second" in text and "unrelated" not in text
    move(run_dir, "C1", "review")
    make_transcript(projects, "r1", ["PASS ok\n## Lessons\nNone"])
    run("report", run_dir, "C1", "review", "--agent", "r1", "--projects-dir", projects)
    assert lessons.read_text(encoding="utf-8") == text
    move(run_dir, "C1", "todo")
    move(run_dir, "C1", "doing")
    make_transcript(projects, "b2", ["PASS again\n## Lessons\n   \n"])
    run("report", run_dir, "C1", "build", "--agent", "b2", "--projects-dir", projects)
    move(run_dir, "C1", "review")
    make_transcript(projects, "r2", ["PASS ok\n## Lessons\n- reviewer saw it"])
    run("report", run_dir, "C1", "review", "--agent", "r2", "--projects-dir", projects)
    text = lessons.read_text(encoding="utf-8")
    assert re.search(r"### C1 review-2 \(code-reviewer\), \d\d:\d\d\n- reviewer saw it", text)
    assert text.count("### ") == 2


def test_report_without_lessons_creates_no_file(doing_card, tmp_path):
    projects = tmp_path / "projects"
    make_transcript(projects, "abc", ["PASS x\n## Lessons learned\nnot the heading"])
    report(doing_card, projects)
    assert not (doing_card / "lessons.md").exists()


# ------------------------------------------------------------------ handoff

def handoff(run_dir, cid, capsys):
    capsys.readouterr()
    run("handoff", run_dir, cid)
    return capsys.readouterr().out


def finish_report(run_dir, projects, cid, kind, agent, text):
    make_transcript(projects, agent, [text])
    run("report", run_dir, cid, kind, "--agent", agent, "--projects-dir", projects)


def test_handoff_prints_each_direct_dependency_from_its_latest_build_report(run_dir, tmp_path, capsys):
    projects = tmp_path / "projects"
    add_card(run_dir, "C1", ["a.py"])
    add_card(run_dir, "C2", kind="question")
    add_card(run_dir, "C3", ["b.py"])
    add_card(run_dir, "C4", ["c.py"], deps=["C1", "C2", "C3"])
    add_card(run_dir, "C5", ["d.py"], deps=["C4"])
    move(run_dir, "C2", "doing")
    finish_report(run_dir, projects, "C2", "build", "q1", "DONE\nverdict\n## Handoff\nNone\n## Lessons\nnone")
    move(run_dir, "C1", "doing")
    finish_report(run_dir, projects, "C1", "build", "b1", "DONE\n## Handoff\nold facts\n## Lessons\nnone")
    move(run_dir, "C1", "review")
    finish_report(run_dir, projects, "C1", "review", "r1", "FAIL\nbroken")
    move(run_dir, "C1", "todo")
    move(run_dir, "C1", "doing")
    finish_report(run_dir, projects, "C1", "build", "b2",
                  "DONE\n```\n## Handoff\nfenced fake\n```\n## Handoff\n- `a.py:3` holds `f(x)`\n"
                  "- run `pytest -k f`\n## Lessons\nnone")

    out = handoff(run_dir, "C4", capsys)
    reports = run_dir / "reports"
    assert out.index("### C1: Title C1 (doing)") < out.index("### C2: Title C2 (doing)") < out.index("### C3:")
    assert f"- `a.py:3` holds `f(x)`\n- run `pytest -k f`\nFull report: {reports / 'C1-build-2.md'}\n" in out
    assert "old facts" not in out and "fenced fake" not in out and "Lessons" not in out
    assert f"No handoff; read {reports / 'C2-build-1.md'}" in out
    assert "### C3: Title C3 (todo)\nNo report yet.\n" in out

    out = handoff(run_dir, "C5", capsys)  # direct dependencies only
    assert "### C4:" in out and "C1" not in out and "C2" not in out
    assert handoff(run_dir, "C1", capsys) == "C1 has no dependencies.\n"


def test_handoff_names_a_missing_report_file_and_a_dropped_dependency(run_dir, tmp_path, capsys):
    projects = tmp_path / "projects"
    add_card(run_dir, "C1", kind="question")
    add_card(run_dir, "C2", kind="question")
    add_card(run_dir, "C3", ["c.py"], deps=["C1", "C2"])
    move(run_dir, "C1", "doing")
    finish_report(run_dir, projects, "C1", "build", "q1", "DONE\n## Handoff\nfacts")
    (run_dir / "reports" / "C1-build-1.md").unlink()
    move(run_dir, "C2", "dropped", why="folded into C9.")
    out = handoff(run_dir, "C3", capsys)
    assert f"Report missing: {run_dir / 'reports' / 'C1-build-1.md'}" in out
    assert "### C2: Title C2 (dropped)\nDropped: folded into C9. Nothing of it is in the code.\n" in out


def test_card_warns_when_its_body_cites_a_report_its_deps_lack(run_dir, tmp_path, capsys):
    add_card(run_dir, "C1", kind="question")
    add_card(run_dir, "C2", kind="question")
    body = tmp_path / "body.md"
    body.write_text("knowledge: <RUN>/reports/C1-build-1.md §5, C2's answer, C3's report, C4 alone", encoding="utf-8")
    capsys.readouterr()
    run("card", run_dir, "C3", "--title", "t", "--builder", "implementer", "--reviewer", "code-reviewer",
        "--files", "x.py", "--repo", "main", "--deps", "C2", "--body-file", body)
    err = capsys.readouterr().err
    assert "C3's body cites C1 but its deps don't list them" in err
    run("card", run_dir, "C3", "--update", "--deps", "C1", "C2", "--body-file", body)
    assert capsys.readouterr().err == ""


def test_show_warns_only_when_an_always_read_file_is_over_its_budget(run_dir, capsys):
    for name, cap in board.READ_BUDGETS.items():
        path = run_dir / name
        path.write_bytes(b"x" * cap)
        capsys.readouterr()
        run("show", run_dir)
        assert "budget:" not in capsys.readouterr().out
        path.write_bytes(b"x" * (cap + 1))
        run("show", run_dir)
        assert f"budget: {name} is {cap + 1:,} bytes, over its {cap:,};" in capsys.readouterr().out
        path.unlink()


def test_card_warns_only_when_its_body_is_over_budget(run_dir, tmp_path, capsys):
    body = tmp_path / "body.md"
    body.write_bytes(b"x" * board.CARD_BUDGET)
    capsys.readouterr()
    run("card", run_dir, "C1", "--title", "t", "--builder", "implementer", "--reviewer", "code-reviewer",
        "--kind", "question", "--body-file", body)
    assert capsys.readouterr().err == ""
    body.write_bytes(b"x" * (board.CARD_BUDGET + 1))
    run("card", run_dir, "C1", "--update", "--body-file", body)
    assert f"C1's body is {board.CARD_BUDGET + 1:,} bytes, over its" in capsys.readouterr().err


def test_handoff_changes_nothing_on_the_board(run_dir, tmp_path, capsys):
    add_card(run_dir, "C1", kind="question")
    add_card(run_dir, "C2", ["b.py"], deps=["C1"])
    before = {p.name: p.read_bytes() for p in run_dir.iterdir() if p.is_file()}
    handoff(run_dir, "C2", capsys)
    assert {p.name: p.read_bytes() for p in run_dir.iterdir() if p.is_file()} == before
    assert "handoff" not in board.MUTATING


# ------------------------------------------------------------------ render

def test_render_shows_repo_kind_resources_commit_and_lessons_count(run_dir, tmp_path, capsys):
    repo = tmp_path / "main"
    add_card(run_dir, "C1", ["a.py"], resources=["stand"])
    add_card(run_dir, "C2", kind="question")
    projects = tmp_path / "projects"
    move(run_dir, "C1", "doing")
    (repo / "a.py").write_text("mine", encoding="utf-8")
    make_transcript(projects, "b1", ["PASS built\n## Lessons\n- one"])
    run("report", run_dir, "C1", "build", "--agent", "b1", "--projects-dir", projects)
    move(run_dir, "C1", "review")
    make_transcript(projects, "r1", ["PASS reviewed"])
    run("report", run_dir, "C1", "review", "--agent", "r1", "--projects-dir", projects)
    run("checkpoint", run_dir, "C1")
    sha = card_of(run_dir, "C1")["commit"]
    md =(run_dir / "board.md").read_text(encoding="utf-8")
    entry = load(run_dir)["repos"][0]
    assert "## Repos" in md
    assert (f"| main | {entry['path']} | {entry['original_branch']} | {entry['base'][:7]} | "
            "construct/run1 |") in md
    assert sha[:7] in md and "stand" in md and "question" in md
    page = html_of(run_dir)
    assert "main" in page and "construct/run1" in page
    assert "lessons: 1" in page
    assert f'<span class="chip commit">{sha[:7]}</span>' in page
    assert '<span class="chip resource">stand</span>' in page
    assert '<span class="badge question">question</span>' in section(page, "todo")
    assert '<span class="chip repo">main</span>' in page
    capsys.readouterr()
    run("show", run_dir)
    shown = capsys.readouterr().out
    assert any("C1" in ln and "main" in ln and "build" in ln for ln in shown.splitlines())
    assert any("C2" in ln and "question" in ln for ln in shown.splitlines())


# ------------------------------------------------------------------ no-branch repos

def test_no_branch_repo_registers_without_switching(tmp_path):
    d = bare_run(tmp_path)
    repo = make_repo(tmp_path, ["a.py"], name="shared")
    original = git_out(repo, "branch", "--show-current")
    base = git_out(repo, "rev-parse", "HEAD")
    run("repo", d, repo, "--no-branch")
    assert git_out(repo, "branch", "--show-current") == original
    assert load(d)["repos"] == [{"path": repo.resolve().as_posix(), "name": "shared",
                                 "original_branch": original, "base": base, "branch": None,
                                 "gate": None, "gate_glob": "*.py"}]
    # a branch of that name existing is irrelevant when none is created
    git(repo, "branch", "construct/run2")
    other = make_repo(tmp_path, ["a.py"], name="shared2")
    git(other, "branch", "construct/run2")
    run("repo", d, other, "--no-branch")
    assert len(load(d)["repos"]) == 2


def test_checkpoint_refuses_no_branch_repo(tmp_path):
    d = bare_run(tmp_path)
    repo = make_repo(tmp_path, ["a.py"], name="shared")
    run("repo", d, repo, "--no-branch")
    add_card(d, "C1", ["a.py"], repo="shared")
    passing_review(d, tmp_path, edit=lambda: (repo / "a.py").write_text("mine", encoding="utf-8"))
    with pytest.raises(SystemExit, match="no-branch repo shared: changes stay uncommitted by design"):
        run("checkpoint", d, "C1")
    assert git_out(repo, "status", "--porcelain").split() == ["M", "a.py"]


def test_rollback_plan_for_no_branch_repo_lists_files(tmp_path, capsys):
    d = bare_run(tmp_path)
    repo = make_repo(tmp_path, ["a.py", "b.py"], name="shared")
    run("repo", d, repo, "--no-branch")
    path = load(d)["repos"][0]["path"]
    add_card(d, "C1", ["a.py"], repo="shared")
    add_card(d, "C2", ["b.py"], repo="shared")
    move(d, "C1", "doing")
    (repo / "a.py").write_text("edited", encoding="utf-8")
    move(d, "C1", "review")
    move(d, "C1", "done")
    capsys.readouterr()
    run("rollback", d)
    out = capsys.readouterr().out
    assert f'git -C "{path}" status --porcelain -- a.py' in out
    assert f'git -C "{path}" checkout -- a.py' in out
    assert "discards those edits" in out
    assert "a.py (C1 done)" in out
    assert "b.py" not in out
    assert " switch " not in out and "branch -D" not in out


# ------------------------------------------------------------------ checkpoint verdict and scope

def commit_all(repo, message="seed"):
    git(repo, "add", ".")
    git(repo, "commit", "-m", message)


def test_checkpoint_refuses_a_stale_review_pass_and_a_build_pass(run_dir, tmp_path):
    repo = tmp_path / "main"
    projects = tmp_path / "projects"
    add_card(run_dir, "C1", ["a.py"])
    move(run_dir, "C1", "doing")
    (repo / "a.py").write_text("mine", encoding="utf-8")
    make_transcript(projects, "b1", ["PASS built but not reviewed"])
    run("report", run_dir, "C1", "build", "--agent", "b1", "--projects-dir", projects)
    move(run_dir, "C1", "review")
    with pytest.raises(SystemExit, match="needs a PASS review-1"):
        run("checkpoint", run_dir, "C1")
    make_transcript(projects, "r1", ["PASS ok"])
    run("report", run_dir, "C1", "review", "--agent", "r1", "--projects-dir", projects)
    move(run_dir, "C1", "todo")
    move(run_dir, "C1", "doing")
    move(run_dir, "C1", "review")
    with pytest.raises(SystemExit, match="needs a PASS review-2"):
        run("checkpoint", run_dir, "C1")
    assert "commit" not in card_of(run_dir, "C1")


def test_checkpoint_refuses_a_card_that_is_already_committed(run_dir, tmp_path):
    add_card(run_dir, "C1", ["a.py"])
    passing_review(run_dir, tmp_path, edit=lambda: (tmp_path / "main" / "a.py").write_text("x", encoding="utf-8"))
    run("checkpoint", run_dir, "C1")
    with pytest.raises(SystemExit, match="already committed"):
        run("checkpoint", run_dir, "C1")


def test_checkpoint_leaves_an_already_staged_sibling_file_staged(run_dir, tmp_path):
    repo = tmp_path / "main"
    add_card(run_dir, "C1", ["a.py"])
    add_card(run_dir, "C2", ["b.py"])
    passing_review(run_dir, tmp_path, edit=lambda: (repo / "a.py").write_text("mine", encoding="utf-8"))
    move(run_dir, "C2", "doing")
    (repo / "b.py").write_text("sibling", encoding="utf-8")
    git(repo, "add", "b.py")
    run("checkpoint", run_dir, "C1")
    assert git_out(repo, "show", "--name-only", "--format=", "HEAD").split() == ["a.py"]
    assert git_out(repo, "status", "--porcelain").split() == ["A", "b.py"]


def test_checkpoint_commits_only_paths_that_exist_and_are_not_ignored(run_dir, tmp_path):
    repo = tmp_path / "main"
    (repo / ".gitignore").write_text("*.log\n", encoding="utf-8")
    commit_all(repo)
    (repo / "ig.log").write_text("ignored", encoding="utf-8")
    add_card(run_dir, "C1", ["a.py", "maybe_new.py", "ig.log"])
    passing_review(run_dir, tmp_path, edit=lambda: (repo / "a.py").write_text("mine", encoding="utf-8"))
    run("checkpoint", run_dir, "C1")
    assert git_out(repo, "show", "--name-only", "--format=", "HEAD").split() == ["a.py"]


def test_checkpoint_treats_file_names_literally(run_dir, tmp_path):
    repo = tmp_path / "main"
    (repo / "a.py").write_text("1", encoding="utf-8")
    commit_all(repo)
    add_card(run_dir, "C1", ["[ab].py"])

    def edits():
        (repo / "a.py").write_text("dirty", encoding="utf-8")
        (repo / "[ab].py").write_text("new", encoding="utf-8")

    passing_review(run_dir, tmp_path, edit=edits)
    run("checkpoint", run_dir, "C1")
    assert git_out(repo, "show", "--name-only", "--format=", "HEAD").split() == ["[ab].py"]
    assert git_out(repo, "status", "--porcelain").split() == ["M", "a.py"]


def test_checkpoint_refuses_a_commit_that_swept_in_foreign_changes(run_dir, tmp_path):
    repo = tmp_path / "main"
    (repo / "b.py").write_text("1", encoding="utf-8")
    commit_all(repo)
    (repo / ".git" / "hooks" / "pre-commit").write_text("#!/bin/sh\ngit add -u\n", encoding="utf-8")
    add_card(run_dir, "C1", ["a.py"])

    def edits():
        (repo / "a.py").write_text("mine", encoding="utf-8")
        (repo / "b.py").write_text("sibling", encoding="utf-8")

    passing_review(run_dir, tmp_path, edit=edits)
    with pytest.raises(SystemExit, match="commit [0-9a-f]{7} made but not recorded"):
        run("checkpoint", run_dir, "C1")
    assert "commit" not in card_of(run_dir, "C1")


def test_legacy_card_with_files_but_no_repo_fails_clearly(run_dir, tmp_path, capsys):
    add_card(run_dir, "C1", ["a.py"])
    state = load(run_dir)
    state["cards"][0]["repo"] = None
    (run_dir / "board.json").write_text(json.dumps(state), encoding="utf-8")
    out = eligible(run_dir, capsys)
    assert "C1 has files but no repo" in out.err
    state["cards"][0]["status"] = "review"
    (run_dir / "board.json").write_text(json.dumps(state), encoding="utf-8")
    with pytest.raises(SystemExit, match="C1 has files but no repo"):
        run("checkpoint", run_dir, "C1")


# ------------------------------------------------------------------ held files, per repo

def test_retargeting_a_blocked_card_keeps_its_held_files(run_dir, tmp_path):
    repo = tmp_path / "main"
    run("repo", run_dir, make_repo(tmp_path, [".keep"], name="other"))
    add_card(run_dir, "C1", ["s.py"])
    add_card(run_dir, "C2", ["s.py"])
    move(run_dir, "C1", "doing")
    (repo / "s.py").write_text("half", encoding="utf-8")
    move(run_dir, "C1", "blocked")
    run("card", run_dir, "C1", "--update", "--repo", "other")
    with pytest.raises(SystemExit, match="s.py"):
        move(run_dir, "C2", "doing")
    run("card", run_dir, "C1", "--update", "--kind", "question")
    with pytest.raises(SystemExit, match="s.py"):
        move(run_dir, "C2", "doing")
    assert load(run_dir)["cards"][0]["held"] == [["main", "s.py"]]


def test_old_boards_get_held_entries_paired_with_the_cards_repo(run_dir):
    add_card(run_dir, "C1", ["a.py"])
    state = load(run_dir)
    state["cards"][0]["held"] = ["a.py"]
    (run_dir / "board.json").write_text(json.dumps(state), encoding="utf-8")
    assert board.load(run_dir)["cards"][0]["held"] == [["main", "a.py"]]


def test_done_files_and_held_files_are_keyed_per_repo(run_dir, tmp_path):
    main = tmp_path / "main"
    other = make_repo(tmp_path, ["a.py"], name="other")
    run("repo", run_dir, other, "--no-branch")
    # done in `other` does not make a.py in `main` owned
    add_card(run_dir, "C1", ["a.py"], repo="other")
    move(run_dir, "C1", "doing")
    move(run_dir, "C1", "review")
    move(run_dir, "C1", "done")
    (main / "a.py").write_text("foreign", encoding="utf-8")
    add_card(run_dir, "C2", ["a.py"], repo="main")
    with pytest.raises(SystemExit, match="uncommitted changes outside done cards: a.py"):
        move(run_dir, "C2", "doing")
    # a held a.py in `other` does not take over C3's own half-edit of a.py in `main`
    run("set", run_dir, "--limit", "3")
    (main / "a.py").unlink()
    add_card(run_dir, "C3", ["a.py"], repo="main")
    move(run_dir, "C3", "doing")
    (main / "a.py").write_text("half", encoding="utf-8")
    move(run_dir, "C3", "todo")
    add_card(run_dir, "C4", ["a.py"], repo="other")
    move(run_dir, "C4", "doing")
    move(run_dir, "C4", "blocked")
    move(run_dir, "C3", "doing")
    assert card_of(run_dir, "C3")["status"] == "doing"


# ------------------------------------------------------------------ resources, branch guard, done

def test_question_card_resources_block_build_cards(run_dir):
    add_card(run_dir, "C1", kind="question", resources=["stand"])
    add_card(run_dir, "C2", ["a.py"], resources=["stand"])
    move(run_dir, "C1", "doing")
    with pytest.raises(SystemExit, match="resource stand is in use by C1"):
        move(run_dir, "C2", "doing")


def test_build_card_resources_block_question_cards(run_dir):
    add_card(run_dir, "C1", ["a.py"], resources=["stand"])
    add_card(run_dir, "C2", kind="question", resources=["stand"])
    move(run_dir, "C1", "doing")
    with pytest.raises(SystemExit, match="resource stand is in use by C1"):
        move(run_dir, "C2", "doing")


def test_doing_refused_when_the_repo_is_off_its_run_branch(run_dir, tmp_path):
    git(tmp_path / "main", "switch", "-c", "elsewhere")
    add_card(run_dir, "C1", ["a.py"])
    with pytest.raises(SystemExit, match="repo main is on elsewhere, not construct/run1"):
        move(run_dir, "C1", "doing")


def test_done_refused_for_an_uncommitted_build_card_in_a_branch_repo(run_dir, tmp_path, capsys):
    repo = tmp_path / "main"
    add_card(run_dir, "C1", ["a.py"])
    passing_review(run_dir, tmp_path, edit=lambda: (repo / "a.py").write_text("mine", encoding="utf-8"))
    with pytest.raises(SystemExit, match="C1 cannot be done: uncommitted changes in a.py; run `checkpoint` first"):
        move(run_dir, "C1", "done")
    capsys.readouterr()
    run("rollback", run_dir)
    assert "uncommitted: a.py (C1 review)" in capsys.readouterr().out
    run("checkpoint", run_dir, "C1")
    move(run_dir, "C1", "done")
    assert card_of(run_dir, "C1")["status"] == "done"


# ------------------------------------------------------------------ rollback and repo output

def apply_plan(out, skip=(" revert ", " status ", "clean -n")):
    for line in out.splitlines():
        line = line.strip()
        if line.startswith("git -C") and not any(word in line for word in skip):
            subprocess.run(shlex.split(line), check=True, capture_output=True)


def test_no_branch_rollback_undo_handles_new_files_and_restores_a_clean_tree(tmp_path, capsys):
    d = bare_run(tmp_path)
    repo = make_repo(tmp_path, ["a.py"], name="shared")
    run("repo", d, repo, "--no-branch")
    add_card(d, "C1", ["a.py", "new.py"], repo="shared")
    add_card(d, "C2", ["c.py"], repo="shared")
    move(d, "C1", "doing")
    (repo / "a.py").write_text("edited", encoding="utf-8")
    (repo / "new.py").write_text("new", encoding="utf-8")
    move(d, "C1", "review")
    move(d, "C1", "done")
    move(d, "C2", "doing")
    (repo / "c.py").write_text("half", encoding="utf-8")
    capsys.readouterr()
    run("rollback", d)
    out = capsys.readouterr().out
    assert "c.py (C2 doing)" in out and "new.py (C1 done)" in out
    assert "git -C" in out and "clean -n -- " in out and "deletes these new files" in out
    apply_plan(out)
    assert git_out(repo, "status", "--porcelain") == ""


def test_rollback_keeps_commits_that_are_not_from_this_run(run_dir, tmp_path, capsys):
    repo = tmp_path / "main"
    add_card(run_dir, "C1", ["a.py"])
    passing_review(run_dir, tmp_path, edit=lambda: (repo / "a.py").write_text("mine", encoding="utf-8"))
    run("checkpoint", run_dir, "C1")
    (repo / "mine.txt").write_text("user work", encoding="utf-8")
    commit_all(repo, "my own work")
    extra = git_out(repo, "rev-parse", "HEAD")
    capsys.readouterr()
    run("rollback", run_dir)
    out = capsys.readouterr().out
    assert "not from this run" in out and "my own work" in out
    assert "branch -D" not in out
    assert "branch -m construct/run1 construct/run1-discarded" in out
    assert "cherry-pick" in out
    apply_plan(out)
    assert extra in git_out(repo, "rev-parse", "construct/run1-discarded")


def test_rollback_continues_past_a_run_branch_that_is_already_gone(run_dir, tmp_path, capsys):
    main = tmp_path / "main"
    run("repo", run_dir, make_repo(tmp_path, [".keep"], name="second"))
    original = load(run_dir)["repos"][0]["original_branch"]
    git(main, "switch", original)
    git(main, "branch", "-D", "construct/run1")
    capsys.readouterr()
    run("rollback", run_dir)
    out = capsys.readouterr().out
    assert "run branch construct/run1 already gone" in out
    assert "repo second" in out and "branch -D construct/run1" in out


def test_repo_lists_the_uncommitted_changes_that_move_to_the_run_branch(tmp_path, capsys):
    d = bare_run(tmp_path)
    repo = make_repo(tmp_path, ["a.py"], name="proj")
    (repo / "a.py").write_text("dirty", encoding="utf-8")
    capsys.readouterr()
    run("repo", d, repo)
    out = capsys.readouterr().out
    assert "these uncommitted changes move to the run branch" in out and "a.py" in out
    assert "1 uncommitted paths" in load(d)["log"][-1]["why"]


# ------------------------------------------------------------------ lessons parsing

def test_lessons_parsing_handles_fences_trailing_spaces_and_none_variants():
    section = board.lessons_section
    assert section("PASS\n```\n## Lessons\nfake\n```\n## Lessons\nreal") == "real"
    assert section("PASS\n## Lessons \n- a\n") == "- a"
    inside = section("PASS\n## Lessons\n- a\n```\n## not a heading\n```\n- b\n## Next\nx")
    assert "## not a heading" in inside and "- b" in inside and "x" not in inside.replace("not", "")
    assert section("PASS\n## Lessons\nold\n## Lessons\nnew") == "new"
    assert board.report_section("DONE\n## Handoff\n- x\n## Lessons\n- y", "Handoff") == "- x"
    quoted_later = board.report_section("DONE\n## Handoff\nreal\n```\n## Handoff\nquoted\n```", "Handoff")
    assert quoted_later == "real\n```\n## Handoff\nquoted\n```"
    for text in ("none", "None.", "- none", "N/A", " n/a \n"):
        assert section(f"PASS\n## Lessons\n{text}") == ""


def test_lessons_are_not_duplicated_when_a_report_is_retried(doing_card, tmp_path, monkeypatch):
    projects = tmp_path / "projects"
    make_transcript(projects, "abc", ["PASS x\n## Lessons\n- keep"])
    real = board.save
    calls = {"n": 0}

    def fail_once(run_dir, state):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("disk")
        real(run_dir, state)

    monkeypatch.setattr(board, "save", fail_once)
    with pytest.raises(RuntimeError):
        report(doing_card, projects)
    report(doing_card, projects)
    assert (doing_card / "lessons.md").read_text(encoding="utf-8").count("### C1 build-1") == 1


# ------------------------------------------------------------------ dropped status

def test_dropped_is_legal_from_todo_and_blocked_only(run_dir):
    add_card(run_dir, "C1", ["a.py"])
    add_card(run_dir, "C2", ["b.py"])
    add_card(run_dir, "C3", ["c.py"])
    move(run_dir, "C1", "dropped", why="no longer needed")
    assert card_of(run_dir, "C1")["status"] == "dropped"
    assert load(run_dir)["log"][-1]["to"] == "dropped"
    move(run_dir, "C2", "doing")
    with pytest.raises(SystemExit, match="illegal transition doing→dropped"):
        move(run_dir, "C2", "dropped")
    move(run_dir, "C2", "blocked")
    move(run_dir, "C2", "dropped")
    assert card_of(run_dir, "C2")["status"] == "dropped"
    for status in ("todo", "doing"):
        with pytest.raises(SystemExit, match="illegal transition dropped→"):
            move(run_dir, "C1", status)
    move(run_dir, "C3", "doing")
    move(run_dir, "C3", "review")
    with pytest.raises(SystemExit, match="illegal transition review→dropped"):
        move(run_dir, "C3", "dropped")


def test_dropping_needs_why(run_dir):
    add_card(run_dir, "C1", ["a.py"])
    with pytest.raises(SystemExit):
        run("move", run_dir, "C1", "dropped", "--who", "lead")
    assert card_of(run_dir, "C1")["status"] == "todo"


def test_dropped_card_is_never_eligible_and_satisfies_deps(run_dir, capsys):
    add_card(run_dir, "C1", ["a.py"])
    add_card(run_dir, "C2", ["b.py"], deps=["C1"])
    assert eligible(run_dir, capsys).out.split() == ["C1"]
    move(run_dir, "C1", "dropped")
    got = eligible(run_dir, capsys)
    assert got.out.split() == ["C2"]
    assert "C1" not in got.err
    assert "ready" in section(html_of(run_dir), "todo")
    move(run_dir, "C2", "doing")


def test_move_to_dropped_lists_dependents_on_stderr(run_dir, capsys):
    add_card(run_dir, "C1", ["a.py"])
    add_card(run_dir, "C2", ["b.py"], deps=["C1"])
    add_card(run_dir, "C3", ["c.py"], deps=["C1"])
    add_card(run_dir, "C4", ["d.py"])
    capsys.readouterr()
    move(run_dir, "C1", "dropped")
    assert "re-check dependents: C2, C3" in capsys.readouterr().err
    move(run_dir, "C4", "dropped")
    assert "re-check" not in capsys.readouterr().err


def test_dropped_renders_in_a_sixth_column_md_show_and_header(run_dir, capsys):
    add_card(run_dir, "C1", ["a.py"])
    add_card(run_dir, "C2", ["b.py"])
    move(run_dir, "C1", "dropped", why="superseded by <b>C2</b>")
    text = html_of(run_dir)
    col = section(text, "dropped")
    assert "C1" in col and "Dropped (1)" in col
    assert "superseded by &lt;b&gt;C2&lt;/b&gt;" in col
    assert "line-through" in text
    assert "1 dropped" in text
    assert "| C1 | Title C1 | dropped |" in (run_dir / "board.md").read_text(encoding="utf-8")
    capsys.readouterr()
    run("show", run_dir)
    out = capsys.readouterr().out
    assert "1 dropped" in out and "\nDROPPED\nC1" in out


# ------------------------------------------------------------------ graph tab

def chain_and_diamond(run_dir):
    add_card(run_dir, "C1", ["a.py"])
    add_card(run_dir, "C2", ["b.py"], deps=["C1"])
    add_card(run_dir, "C3", ["c.py"], deps=["C2"])
    add_card(run_dir, "C4", ["d.py"], deps=["C1"])
    add_card(run_dir, "C5", ["e.py"], deps=["C1"])
    add_card(run_dir, "C6", ["f.py"], deps=["C4", "C5"])


def test_graph_layers_are_the_longest_dep_path(run_dir):
    chain_and_diamond(run_dir)
    layers = board.graph_layers(board.load(run_dir))
    assert layers == {"C1": 0, "C2": 1, "C3": 2, "C4": 1, "C5": 1, "C6": 2}


def test_graph_has_a_node_per_card_and_an_edge_per_dep(run_dir):
    chain_and_diamond(run_dir)
    text = html_of(run_dir)
    assert len(re.findall(r'<g [^>]*data-card="C\d"', text)) == 6
    assert '<g class="node todo" data-card="C1"' in text
    edges = re.findall(r'data-edge="(C\d>C\d)"', text)
    assert sorted(edges) == ["C1>C2", "C1>C4", "C1>C5", "C2>C3", "C4>C6", "C5>C6"]
    assert 'marker-end="url(#arrow)"' in text


def test_graph_escapes_titles_and_marks_dropped_nodes(run_dir):
    body = run_dir / "b.txt"
    body.write_text("x", encoding="utf-8")
    run("card", run_dir, "C1", "--title", "<script>alert(1)</script> and a much longer tail of words",
        "--builder", "implementer", "--reviewer", "code-reviewer", "--files", "a.py",
        "--repo", "main", "--body-file", body)
    move(run_dir, "C1", "dropped")
    text = html_of(run_dir)
    assert "<script>alert(1)" not in text
    graph = text[text.index("<svg"):text.index("</svg>")]
    assert "&lt;script&gt;" in graph
    assert 'class="node dropped"' in graph
    assert "a much longer tail" in graph.split("<title>")[1].split("</title>")[0]
    assert "a much longer tail" not in graph.split("</title>")[1]


def test_tabs_and_hash_script_are_present_and_refresh_keeps_scroll(run_dir):
    text = html_of(run_dir)
    assert 'href="#board"' in text and 'href="#graph"' in text
    assert "location.hash" in text
    assert "setTimeout(" in text and "location.reload()" in text
    assert "sessionStorage" in text and "try{" in text.replace(" ", "")
    assert '<link rel="icon" href="data:,">' in text
    assert 'http-equiv="refresh"' not in text


# ------------------------------------------------------------------ persistent viewer

def fetch(port, name="board.html"):
    import urllib.request
    return urllib.request.urlopen(f"http://127.0.0.1:{port}/{name}", timeout=3)


def http_status(port, path, host=None):
    import http.client
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=3)
    conn.putrequest("GET", path, skip_host=host is not None)
    if host is not None:
        conn.putheader("Host", host)
    conn.endheaders()
    status = conn.getresponse().status
    conn.close()
    return status


def wait_for(port, up=True, seconds=6):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if board.accepts(port, 0.2) == up:
            return True
        time.sleep(0.1)
    return False


def viewer_info(run_dir):
    path = run_dir / "viewer.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def kill_pid(pid):
    if sys.platform == "win32":
        subprocess.run(["taskkill", "/PID", str(pid), "/F"], capture_output=True)
    else:
        os.kill(pid, 9)


def proc_alive(proc):
    return proc.poll() is None


@pytest.fixture
def viewer_run(run_dir):
    yield run_dir
    info = viewer_info(run_dir)
    if info:
        kill_pid(info["pid"])


class Listener:
    """A foreign HTTP listener on a port; answers /viewer-id with `answer`."""

    def __init__(self, answer="not-ours", port=0):
        import http.server
        import threading
        answer_bytes = answer.encode()

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(200)
                self.send_header("Content-Length", str(len(answer_bytes)))
                self.end_headers()
                self.wfile.write(answer_bytes)

            def log_message(self, *a):
                pass
        self.server = http.server.ThreadingHTTPServer(("127.0.0.1", port), Handler)
        self.port = self.server.server_address[1]
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def close(self):
        self.server.shutdown()
        self.server.server_close()


def start_inprocess_viewer(run_dir, monkeypatch, poll=0.1, watch=0.1, grace=0.3):
    import threading
    monkeypatch.setattr(board, "VIEWER_STOP_POLL_SECONDS", poll)
    monkeypatch.setattr(board, "VIEWER_WATCH_SECONDS", watch)
    monkeypatch.setattr(board, "VIEWER_CLOSED_GRACE_SECONDS", grace)
    port = board.free_port()
    thread = threading.Thread(target=run, args=("_serve", run_dir, "--port", port), daemon=True)
    thread.start()
    assert wait_for(port)
    return port, thread


def test_serve_spawns_a_detached_viewer_and_is_idempotent(viewer_run, capsys, monkeypatch):
    capsys.readouterr()
    run("serve", viewer_run)
    url = capsys.readouterr().out.strip()
    port = load(viewer_run)["viewer"]["port"]
    info = viewer_info(viewer_run)
    assert url == f"http://127.0.0.1:{port}/board.html"
    assert info["port"] == port and board.viewer_alive(viewer_run, port)
    assert "pid" not in load(viewer_run)["viewer"]
    assert fetch(port).status == 200
    assert fetch(port, "viewer-id").read().decode() == info["token"]
    assert (viewer_run / "viewer.log").exists()

    def no_spawn(*a, **k):
        raise AssertionError("second serve must not spawn")
    monkeypatch.setattr(board, "spawn_viewer", no_spawn)
    run("serve", viewer_run)
    assert capsys.readouterr().out.strip() == url
    assert viewer_info(viewer_run) == info


def test_stop_asks_the_viewer_to_exit_and_is_sticky(viewer_run, capsys, monkeypatch):
    run("serve", viewer_run)
    port = load(viewer_run)["viewer"]["port"]
    capsys.readouterr()
    run("stop", viewer_run)
    assert "stopped" in capsys.readouterr().out
    assert wait_for(port, up=False)
    assert viewer_info(viewer_run) is None and not (viewer_run / "viewer.stop").exists()
    assert load(viewer_run)["viewer"] == {"port": port, "stopped": True, "stop_gen": 1}
    run("stop", viewer_run)
    assert "no viewer" in capsys.readouterr().out
    monkeypatch.delenv("CONSTRUCT_NO_VIEWER")
    run("log", viewer_run, "--who", "lead", "--text", "poke")  # heal skips a deliberately stopped viewer
    assert not board.accepts(port, 0.3)
    run("serve", viewer_run)
    assert "stopped" not in load(viewer_run)["viewer"] and wait_for(port)


def test_mutating_command_respawns_a_dead_viewer_on_the_same_port(viewer_run, monkeypatch):
    run("serve", viewer_run)
    port = load(viewer_run)["viewer"]["port"]
    kill_pid(viewer_info(viewer_run)["pid"])
    assert wait_for(port, up=False)
    monkeypatch.delenv("CONSTRUCT_NO_VIEWER")
    run("log", viewer_run, "--who", "lead", "--text", "poke")
    assert wait_for(port)
    assert fetch(port).status == 200
    assert load(viewer_run)["viewer"]["port"] == port
    assert board.viewer_alive(viewer_run, port)


def test_a_foreign_listener_on_the_recorded_port_gets_a_new_port_and_a_loud_note(viewer_run, capsys):
    foreign = Listener("not-ours")
    try:
        with board.locked(viewer_run):
            state = board.load(viewer_run)
            state["viewer"] = {"port": foreign.port}
            board.finish(viewer_run, state)
        capsys.readouterr()
        run("serve", viewer_run)
        out, err = capsys.readouterr()
        port = load(viewer_run)["viewer"]["port"]
        assert port != foreign.port and out.strip() == f"http://127.0.0.1:{port}/board.html"
        assert str(foreign.port) in err and "another program" in err and str(port) in err
        assert fetch(port).status == 200
        assert fetch(foreign.port).read() == b"not-ours"
    finally:
        foreign.close()


def test_stop_never_kills_anything_it_cannot_identify(viewer_run, monkeypatch, capsys):
    sleeper = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(120)"])
    foreign = Listener("the-token")
    try:
        monkeypatch.setattr(board, "VIEWER_STOP_WAIT", 0.5)
        with board.locked(viewer_run):
            state = board.load(viewer_run)
            state["viewer"] = {"port": foreign.port}
            board.finish(viewer_run, state)
        # a viewer.json naming the sleeper but with a token the port does not return
        (viewer_run / "viewer.json").write_text(json.dumps(
            {"pid": sleeper.pid, "port": foreign.port, "token": "other", "started": "x"}), encoding="utf-8")
        capsys.readouterr()
        run("stop", viewer_run)
        assert "no viewer" in capsys.readouterr().out
        assert proc_alive(sleeper) and board.accepts(foreign.port, 0.3)
        # a listener that returns the right token but ignores the stop flag: report, kill nothing
        (viewer_run / "viewer.json").write_text(json.dumps(
            {"pid": sleeper.pid, "port": foreign.port, "token": "the-token", "started": "x"}), encoding="utf-8")
        with pytest.raises(SystemExit, match=str(sleeper.pid)):
            run("stop", viewer_run)
        assert proc_alive(sleeper) and board.accepts(foreign.port, 0.3)
    finally:
        foreign.close()
        sleeper.kill()
        sleeper.wait()


def test_a_port_the_child_cannot_bind_falls_back_to_a_free_port(viewer_run, capsys):
    import socket
    squatter = socket.socket()
    squatter.bind(("127.0.0.1", 0))  # bound but not listening: connects are refused, binds fail
    try:
        bad = squatter.getsockname()[1]
        with board.locked(viewer_run):
            state = board.load(viewer_run)
            state["viewer"] = {"port": bad}
            board.finish(viewer_run, state)
        capsys.readouterr()
        started = time.monotonic()
        run("serve", viewer_run)
        out, err = capsys.readouterr()
        port = load(viewer_run)["viewer"]["port"]
        assert port != bad and out.strip() == f"http://127.0.0.1:{port}/board.html"
        assert f"http://127.0.0.1:{port}/board.html" in err and str(bad) in err
        assert "failed_at" not in load(viewer_run)["viewer"]  # the fallback came up
        assert fetch(port).status == 200
        assert time.monotonic() - started < 8
    finally:
        squatter.close()


def test_heal_backs_off_after_a_failure_and_retries_later(run_dir, monkeypatch, capsys):
    monkeypatch.delenv("CONSTRUCT_NO_VIEWER")
    port = board.free_port()
    calls = []

    def boom(*a, **k):
        calls.append(1)
        raise OSError("cannot spawn")
    monkeypatch.setattr(board, "spawn_viewer", boom)

    def record(failed_at):
        with board.locked(run_dir):
            state = board.load(run_dir)
            state["viewer"] = {"port": port, "failed_at": failed_at}
            board.finish(run_dir, state)
    record(board.now())
    capsys.readouterr()
    run("log", run_dir, "--who", "lead", "--text", "poke")
    assert calls == [] and capsys.readouterr().err == ""
    record((datetime.now().astimezone() - timedelta(hours=2)).isoformat(timespec="seconds"))
    run("log", run_dir, "--who", "lead", "--text", "poke")
    err = capsys.readouterr().err
    assert len(calls) == 1
    assert len(err.strip().splitlines()) == 1 and "viewer" in err and "cannot spawn" in err
    assert load(run_dir)["viewer"]["failed_at"]  # a failed spawn also starts the back-off


def test_self_heal_skips_closed_runs(run_dir, monkeypatch, capsys):
    monkeypatch.delenv("CONSTRUCT_NO_VIEWER")
    with board.locked(run_dir):
        state = board.load(run_dir)
        state["viewer"] = {"port": board.free_port()}
        state["phase"] = "closed"
        board.finish(run_dir, state)

    def boom(*a, **k):
        raise AssertionError("closed runs get no viewer")
    monkeypatch.setattr(board, "spawn_viewer", boom)
    capsys.readouterr()
    run("log", run_dir, "--who", "lead", "--text", "poke")
    assert capsys.readouterr().err == ""


def test_concurrent_heals_start_exactly_one_viewer(viewer_run, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    monkeypatch.delenv("CONSTRUCT_NO_VIEWER")
    port = board.free_port()
    with board.locked(viewer_run):
        state = board.load(viewer_run)
        state["viewer"] = {"port": port}
        board.finish(viewer_run, state)
    real, spawned = board.spawn_viewer, []

    def counting(*a, **k):
        spawned.append(1)
        return real(*a, **k)
    monkeypatch.setattr(board, "spawn_viewer", counting)
    with ThreadPoolExecutor(6) as ex:
        list(ex.map(lambda i: run("log", viewer_run, "--who", f"w{i}", "--text", f"note {i}"), range(6)))
    assert len(spawned) == 1
    assert wait_for(port) and board.viewer_alive(viewer_run, port)
    assert sum(1 for e in load(viewer_run)["log"] if e["why"].startswith("note ")) == 6


def test_a_viewer_that_cannot_start_never_loses_other_commands(viewer_run, monkeypatch):
    import socket
    from concurrent.futures import ThreadPoolExecutor
    monkeypatch.delenv("CONSTRUCT_NO_VIEWER")
    squatter = socket.socket()
    squatter.bind(("127.0.0.1", 0))
    try:
        with board.locked(viewer_run):
            state = board.load(viewer_run)
            state["viewer"] = {"port": squatter.getsockname()[1]}
            board.finish(viewer_run, state)
        started = time.monotonic()
        with ThreadPoolExecutor(8) as ex:
            list(ex.map(lambda i: run("log", viewer_run, "--who", f"w{i}", "--text", f"note {i}"), range(8)))
        assert time.monotonic() - started < 20
        assert sum(1 for e in load(viewer_run)["log"] if e["why"].startswith("note ")) == 8
        assert not (viewer_run / "board.lock").exists()
    finally:
        squatter.close()


def test_every_board_changing_command_heals_the_viewer(run_dir, monkeypatch):
    monkeypatch.delenv("CONSTRUCT_NO_VIEWER")
    seen = []
    monkeypatch.setattr(board, "heal_viewer", lambda r: seen.append(r))
    add_card(run_dir, "C1", ["a.py"])
    move(run_dir, "C1", "doing")
    run("progress", run_dir, "C1", "--who", "w", "--text", "n")
    run("log", run_dir, "--who", "lead", "--text", "x")
    assert len(seen) >= 4  # card, move, progress, log
    n = len(seen)
    run("progress", run_dir, "C1", "--who", "w", "--text", "n2")
    assert len(seen) == n + 1


def test_a_live_viewers_port_cannot_be_bound_a_second_time(run_dir, monkeypatch):
    import http.server
    port, thread = start_inprocess_viewer(run_dir, monkeypatch)
    try:
        with pytest.raises(OSError):
            board.ViewerServer(("127.0.0.1", port), http.server.BaseHTTPRequestHandler)
    finally:
        (run_dir / "viewer.stop").write_text("stop", encoding="utf-8")
        thread.join(timeout=5)
    assert not thread.is_alive()


def test_viewer_exits_on_the_stop_flag_and_cleans_up(run_dir, monkeypatch):
    port, thread = start_inprocess_viewer(run_dir, monkeypatch, watch=1000)
    assert viewer_info(run_dir)["port"] == port
    (run_dir / "viewer.stop").write_text("stop", encoding="utf-8")
    thread.join(timeout=5)
    assert not thread.is_alive()
    assert viewer_info(run_dir) is None and not (run_dir / "viewer.stop").exists()
    assert wait_for(port, up=False)


def test_viewer_shuts_itself_down_when_the_run_is_closed(run_dir, monkeypatch):
    port, thread = start_inprocess_viewer(run_dir, monkeypatch)
    time.sleep(0.6)
    assert thread.is_alive()  # still shaping
    run("set", run_dir, "--phase", "closed")
    thread.join(timeout=5)
    assert not thread.is_alive()
    assert wait_for(port, up=False)


def test_viewer_shuts_itself_down_when_board_json_is_gone(run_dir, monkeypatch):
    port, thread = start_inprocess_viewer(run_dir, monkeypatch)
    for attempt in range(50):  # the watcher may hold board.json open for a moment
        try:
            (run_dir / "board.json").unlink()
            break
        except PermissionError:
            time.sleep(0.05)
    thread.join(timeout=5)
    assert not thread.is_alive()


def test_viewer_serves_only_the_board_page_and_its_id_to_local_hosts(run_dir, monkeypatch):
    (run_dir / "reports" / "C1-build-1.md").write_text("report body", encoding="utf-8")
    port, thread = start_inprocess_viewer(run_dir, monkeypatch, watch=1000)
    try:
        token = viewer_info(run_dir)["token"]
        assert http_status(port, "/board.html") == 200 and http_status(port, "/") == 200
        assert fetch(port, "viewer-id").read().decode() == token
        for path in ("/board.json", "/board.md", "/reports/", "/reports/C1-build-1.md", "/viewer.log",
                     "/viewer.json", "/../board.json", "/%2e%2e/board.json", "/nope"):
            assert http_status(port, path) == 404, path
        assert http_status(port, "/board.html", host=f"localhost:{port}") == 200
        assert http_status(port, "/board.html", host="attacker.example") == 403
        assert http_status(port, "/board.html", host=f"attacker.example:{port}") == 403
        assert http_status(port, "/viewer-id", host="127.0.0.1:1") == 403
    finally:
        (run_dir / "viewer.stop").write_text("stop", encoding="utf-8")
        thread.join(timeout=5)


def test_the_viewer_is_spawned_away_from_the_callers_folder(viewer_run, monkeypatch):
    import tempfile
    seen = {}
    real = subprocess.Popen

    def spy(*args, **kwargs):
        seen.update(kwargs)
        return real(*args, **kwargs)
    monkeypatch.setattr(board.subprocess, "Popen", spy)
    run("serve", viewer_run)
    assert seen["cwd"] == tempfile.gettempdir()
    assert seen["stdin"] == subprocess.DEVNULL and seen["close_fds"] is True


def test_serve_port_sets_the_preferred_port_and_a_live_viewer_wins(viewer_run, capsys):
    want = board.free_port()
    capsys.readouterr()
    run("serve", viewer_run, "--port", want)
    assert capsys.readouterr().out.strip() == f"http://127.0.0.1:{want}/board.html"
    other = board.free_port()
    run("serve", viewer_run, "--port", other)
    out, err = capsys.readouterr()
    assert out.strip() == f"http://127.0.0.1:{want}/board.html"
    assert str(other) in err  # said, not silently ignored


def test_board_html_and_md_are_replaced_atomically_with_retry(run_dir, monkeypatch):
    monkeypatch.setattr(board, "REPLACE_DELAY", 0)
    real, pairs, fails = Path.replace, [], {"n": 0}

    def flaky(self, target):
        pairs.append((self.name, Path(target).name))
        if self.name == "board.html.tmp" and fails["n"] < 2:
            fails["n"] += 1
            raise PermissionError("held open")
        return real(self, target)
    monkeypatch.setattr(Path, "replace", flaky)
    run("set", run_dir, "--goal", "g")
    assert ("board.html.tmp", "board.html") in pairs and ("board.md.tmp", "board.md") in pairs
    assert pairs.count(("board.html.tmp", "board.html")) == 3
    assert "g" in html_of(run_dir)
    assert not list(run_dir.glob("*.tmp"))


def test_load_retries_a_permission_error_like_save_does(run_dir, monkeypatch):
    monkeypatch.setattr(board, "REPLACE_DELAY", 0)
    real, fails = Path.read_text, {"n": 0}

    def flaky(self, *a, **k):
        if self.name == "board.json" and fails["n"] < 3:
            fails["n"] += 1
            raise PermissionError("replaced right now")
        return real(self, *a, **k)
    monkeypatch.setattr(Path, "read_text", flaky)
    assert board.load(run_dir)["title"] == "Demo" and fails["n"] == 3


def test_reload_probes_the_server_first_and_rearms_when_it_is_down(run_dir):
    text = html_of(run_dir)
    head = text[:text.index("</head>")]
    assert "setTimeout" in head and "location.reload()" in head
    assert 'fetch(location.href' in head and "no-store" in head and ".ok" in head
    assert "arm()" in head  # a failed probe schedules the next attempt


def test_ages_over_an_hour_read_in_hours_and_days(run_dir):
    assert board.fmt_elapsed(59) == "0m 59s"
    assert board.fmt_elapsed(59 * 60 + 59) == "59m 59s"
    assert board.fmt_elapsed(125 * 60) == "2h 5m"
    assert board.fmt_elapsed((3 * 24 + 4) * 3600 + 7) == "3d 4h"
    at = (datetime.now().astimezone() - timedelta(minutes=125)).isoformat(timespec="seconds")
    assert "2h 5m" in board.since_span(at)
    assert "3600" in html_of(run_dir) and "1440" in html_of(run_dir)


# ------------------------------------------------------------------ estimates, actuals, ETA

T0 = datetime(2026, 10, 26, 9, 0).astimezone()


def iso(minutes):
    return (T0 + timedelta(minutes=minutes)).isoformat(timespec="seconds")


def timed_log(cid, *steps):
    """steps: (minute, from, to)."""
    return [{"t": iso(m), "card": cid, "from": f, "to": t, "who": "lead", "why": "x"} for m, f, t in steps]


def test_eta_is_the_larger_of_critical_path_and_load_over_limit(run_dir):
    for i in (1, 2, 3):
        add_card(run_dir, f"C{i}", [f"{i}.py"], deps=[f"C{i - 1}"] if i > 1 else ())
        run("card", run_dir, f"C{i}", "--update", "--estimate", "30")
    assert board.eta_minutes(board.load(run_dir)) == 90  # chain 90 vs 90/2
    wide = run_dir.parent / "wide"
    run("init", wide, "--title", "W", "--limit", "2", "--route", "lanes")
    run("team", wide, "implementer", "--role", "builder", "--tier", "sonnet")
    run("team", wide, "code-reviewer", "--role", "reviewer", "--tier", "opus")
    run("repo", wide, run_dir.parent / "main")
    for i in (1, 2, 3, 4):
        add_card(wide, f"C{i}", [f"{i}.py"])
        run("card", wide, f"C{i}", "--update", "--estimate", "30")
    assert board.eta_minutes(board.load(wide)) == 60  # 4*30/2 beats chain 30


def test_eta_falls_back_to_median_actual_then_25_and_skips_done_and_dropped(run_dir):
    for i in (1, 2, 3, 4):
        add_card(run_dir, f"C{i}", [f"{i}.py"])
    state = board.load(run_dir)
    state["limit"] = 1
    state["cards"][3]["status"] = "dropped"
    assert board.eta_minutes(state, T0) == 3 * 25
    for c in state["cards"][:2]:
        c["status"] = "done"
    state["log"] = (timed_log("C1", (0, "todo", "doing"), (10, "doing", "done"))
                    + timed_log("C2", (0, "todo", "doing"), (30, "doing", "done")))
    assert board.eta_minutes(state, T0) == 20  # one remaining card at the median 20
    state["cards"][2]["status"] = "done"
    assert board.eta_minutes(state, T0) is None


def test_set_next_input_and_availability_show_in_the_header_and_clear(run_dir, capsys):
    add_card(run_dir, "C1", ["a.py"])
    run("set", run_dir, "--next-input", "the stand password", "--next-input-at", "09:30",
        "--availability", "away until 09:00")
    text = html_of(run_dir)
    assert "next input: the stand password · ~09:30" in text
    assert "you: away until 09:00" in text
    assert "ETA ~" in text and "(est.)" in text
    md = (run_dir / "board.md").read_text(encoding="utf-8")
    assert "next input: the stand password" in md and "ETA ~" in md
    capsys.readouterr()
    run("show", run_dir)
    assert "ETA ~" in capsys.readouterr().out
    run("set", run_dir, "--next-input-at", "2026-10-26T14:05:00+00:00")
    assert re.search(r"· ~\d\d:05", html_of(run_dir))
    run("set", run_dir, "--next-input", "", "--next-input-at", "", "--availability", "")
    text = html_of(run_dir)
    assert "next input:" not in text and "you:" not in text
    with pytest.raises(SystemExit, match="next-input-at"):
        run("set", run_dir, "--next-input-at", "tomorrow-ish")


def test_header_shows_estimate_accuracy_and_tiles_show_est_and_actual(run_dir):
    add_card(run_dir, "C1", ["a.py"])
    add_card(run_dir, "C2", ["b.py"])
    run("card", run_dir, "C1", "--update", "--estimate", "30")
    run("card", run_dir, "C2", "--update", "--estimate", "30")
    state = board.load(run_dir)
    state["cards"][0]["status"] = "done"
    state["log"] = timed_log("C1", (0, "todo", "doing"), (42, "doing", "done"))
    text = board.render_html(state)
    assert "actual/est ×1.4" in text
    assert "est 30m" in section(text, "todo")
    assert "actual ~42m" in section(text, "done") and "est 30m" in section(text, "done")
    assert "actual ~42m" not in section(text, "todo")
    md = board.render_md(state)
    assert "~42m" in md


def test_card_estimate_must_be_positive_and_update_alone_is_a_field(run_dir):
    add_card(run_dir, "C1", ["a.py"])
    run("card", run_dir, "C1", "--update", "--estimate", "45")
    assert card_of(run_dir, "C1")["estimate"] == 45
    with pytest.raises(SystemExit):
        run("card", run_dir, "C1", "--update", "--estimate", "0")
    run("card", run_dir, "C1", "--update", "--title", "renamed")
    assert card_of(run_dir, "C1")["estimate"] == 45
    body = run_dir / "b.txt"
    body.write_text("x", encoding="utf-8")
    run("card", run_dir, "C2", "--title", "t", "--builder", "implementer", "--reviewer", "code-reviewer",
        "--files", "b.py", "--repo", "main", "--body-file", body, "--estimate", "20")
    assert card_of(run_dir, "C2")["estimate"] == 20


# ------------------------------------------------------------------ dispatch tier and effort

def test_move_records_tier_and_effort_per_dispatch(run_dir):
    add_card(run_dir, "C1", ["a.py"])
    move(run_dir, "C1", "doing", tier="sonnet", effort="medium")
    move(run_dir, "C1", "review", tier="opus", effort="high")
    d = card_of(run_dir, "C1")["dispatches"]
    assert [(x["role"], x["agent"], x["tier"], x["effort"]) for x in d] == [
        ("builder", "implementer", "sonnet", "medium"), ("reviewer", "code-reviewer", "opus", "high")]
    assert all("t" in x for x in d)
    with pytest.raises(SystemExit):
        move(run_dir, "C1", "todo", tier="opus")
    with pytest.raises(SystemExit):
        run("move", run_dir, "C1", "done", "--who", "l", "--why", "w", "--tier", "gpt")
    with pytest.raises(SystemExit):
        run("move", run_dir, "C1", "done", "--who", "l", "--why", "w", "--effort", "extreme")


def test_dispatch_chip_and_mix_summary(run_dir):
    add_card(run_dir, "C1", ["a.py"])
    add_card(run_dir, "C2", ["b.py"])
    move(run_dir, "C1", "doing", tier="sonnet", effort="medium")
    move(run_dir, "C2", "doing", tier="sonnet", effort="medium")
    move(run_dir, "C2", "review", tier="opus", effort="high")
    text = html_of(run_dir)
    assert "sonnet · medium" in section(text, "doing")
    assert "opus · high" in section(text, "review")
    assert "Dispatch mix" in text
    assert "builder · sonnet · medium: 2" in text and "reviewer · opus · high: 1" in text
    md = (run_dir / "board.md").read_text(encoding="utf-8")
    assert "## Dispatch mix" in md and "builder · sonnet · medium: 2" in md


def test_old_boards_without_the_new_fields_load_and_render(run_dir):
    add_card(run_dir, "C1", ["a.py"])
    state = load(run_dir)
    for c in state["cards"]:
        c.pop("dispatches", None)
        c.pop("estimate", None)
    for key in ("viewer", "next_input", "next_input_at", "availability"):
        state.pop(key, None)
    (run_dir / "board.json").write_text(json.dumps(state), encoding="utf-8")
    run("log", run_dir, "--who", "lead", "--text", "still fine")
    run("show", run_dir)
    assert "C1" in html_of(run_dir)


# ------------------------------------------------------------------ graph readability

def test_graph_draws_only_edges_no_other_path_implies(run_dir):
    add_card(run_dir, "C1", ["a.py"])
    add_card(run_dir, "C2", ["b.py"], deps=["C1"])
    add_card(run_dir, "C3", ["c.py"], deps=["C1"])
    add_card(run_dir, "C4", ["d.py"], deps=["C2", "C3", "C1"])
    state = board.load(run_dir)
    assert sorted(board.transitive_reduction(state)) == [("C1", "C2"), ("C1", "C3"), ("C2", "C4"), ("C3", "C4")]
    text = html_of(run_dir)
    assert 'data-edge="C1>C4"' not in text and 'data-edge="C2>C4"' in text
    assert "deps: C2, C3, C1" in text  # the hover title still lists every dep
    assert card_of(run_dir, "C4")["deps"] == ["C2", "C3", "C1"]


def test_barycenter_order_crosses_less_than_id_order(run_dir):
    add_card(run_dir, "C1", ["a.py"])
    add_card(run_dir, "C2", ["b.py"])
    add_card(run_dir, "C3", ["c.py"], deps=["C2"])
    add_card(run_dir, "C4", ["d.py"], deps=["C1"])
    state = board.load(run_dir)
    by_id = board.graph_layout(state, sweeps=0)
    swept = board.graph_layout(state)
    assert by_id["crossings"] == 1
    assert swept["crossings"] == 0
    assert swept["order"][1] == ["C4", "C3"]


def test_long_edge_runs_through_lanes_not_through_nodes(run_dir):
    add_card(run_dir, "C1", ["a.py"])
    add_card(run_dir, "C2", ["b.py"], deps=["C1"])
    add_card(run_dir, "C3", ["c.py"], deps=["C2"])
    add_card(run_dir, "C4", ["d.py"], deps=["C3"])
    add_card(run_dir, "C5", ["e.py"], deps=["C1"])
    add_card(run_dir, "C6", ["f.py"], deps=["C5", "C4"])
    state = board.load(run_dir)
    lay = board.graph_layout(state)
    points = lay["waypoints"][("C5", "C6")]
    assert len(points) == 2 + 2 * 2  # two dummy layers, entry and exit point each
    real = [lay["boxes"][c["id"]] for c in state["cards"]]
    for x, y in points[1:-1]:
        for bx, by, bw, bh in real:
            assert not (bx <= x <= bx + bw and by < y < by + bh), (x, y, (bx, by, bw, bh))
    assert [p[0] for p in points] == sorted(p[0] for p in points)
    path = re.search(r'<path[^>]*data-edge="C5>C6"[^>]*d="([^"]+)"', html_of(run_dir)).group(1)
    assert path.startswith("M") and path.count("C") == len(points) - 1


def test_graph_hover_focus_attributes_and_script(run_dir):
    chain_and_diamond(run_dir)
    text = html_of(run_dir)
    assert 'class="edge to-todo" data-edge="C1>C2"' in text
    assert 'data-card="C1"' in text
    for needle in ("mouseover", "mouseout", '"click"', "dataset.edge", "svg.focus", ".hl"):
        assert needle in text
    run_state = board.load(run_dir)
    run_state["cards"][1].update(status="doing", since=iso(0))
    page = board.render_html(run_state)
    assert 'class="edge to-doing" data-edge="C1>C2"' in page


def test_root_is_pulled_next_to_its_first_dependent(run_dir):
    add_card(run_dir, "C1", ["a.py"])
    add_card(run_dir, "C2", ["b.py"])
    add_card(run_dir, "C3", ["c.py"], deps=["C2"])
    add_card(run_dir, "C4", ["d.py"], deps=["C3"])
    add_card(run_dir, "C5", ["e.py"], deps=["C1", "C4"])
    state = board.load(run_dir)
    assert board.graph_layers(state)["C5"] == 3
    lay = board.graph_layout(state)
    assert lay["layers"]["C5"] == 3 and lay["layers"]["C1"] == 2 and lay["layers"]["C2"] == 0
    assert board.graph_layout(state, compact=False)["layers"]["C1"] == 0
    assert len(lay["waypoints"][("C1", "C5")]) == 2  # no lane points left


def test_isolated_cards_go_to_a_strip_below_the_layers(run_dir):
    add_card(run_dir, "C1", ["a.py"])
    add_card(run_dir, "C2", ["b.py"], deps=["C1"])
    for i in range(3, 12):
        add_card(run_dir, f"C{i}", [f"{i}.py"])
    state = board.load(run_dir)
    lay = board.graph_layout(state)
    assert lay["strip"] == [f"C{i}" for i in range(3, 12)]
    assert all(c not in lay["layers"] for c in lay["strip"])
    assert all(c not in ids for c in lay["strip"] for ids in lay["order"].values())
    dag_bottom = max(lay["boxes"][c][1] + lay["boxes"][c][3] for ids in lay["order"].values() for c in ids)
    assert all(lay["boxes"][c][1] > dag_bottom for c in lay["strip"])
    ys = {lay["boxes"][c][1] for c in lay["strip"]}
    assert len(ys) > 1  # wraps into rows
    text = html_of(run_dir)
    assert "No dependencies" in text and 'data-card="C11"' in text


def test_pulling_roots_does_not_add_crossings(run_dir):
    add_card(run_dir, "C1", ["a.py"])
    add_card(run_dir, "C2", ["b.py"])
    add_card(run_dir, "C3", ["c.py"], deps=["C2"])
    add_card(run_dir, "C4", ["d.py"], deps=["C1"])
    add_card(run_dir, "C5", ["e.py"], deps=["C3", "C4"])
    state = board.load(run_dir)
    assert board.graph_layout(state)["crossings"] <= board.graph_layout(state, compact=False)["crossings"]


def entry(minute, cid=None, frm=None, to=None):
    return {"t": iso(minute), "card": cid, "from": frm, "to": to, "who": "lead", "why": "x"}


def test_actual_minutes_drops_board_wide_idle_gaps_not_a_flat_cap(run_dir):
    add_card(run_dir, "C1", ["a.py"])
    state = board.load(run_dir)
    # the session dies at minute 20 and the card is only moved on after 3,440 idle minutes
    state["log"] = [entry(0, "C1", "todo", "doing"), entry(20), entry(3460, "C1", "doing", "review"),
                    entry(3470, "C1", "review", "done")]
    assert board.actual_minutes(state, state["cards"][0], T0 + timedelta(days=5)) == 20 + 10


def test_a_long_span_with_a_live_session_counts_in_full(run_dir):
    add_card(run_dir, "C1", ["a.py"])
    state = board.load(run_dir)
    state["log"] = ([entry(0, "C1", "todo", "doing")] + [entry(m) for m in range(60, 300, 60)]
                    + [entry(300, "C1", "doing", "review"), entry(310, "C1", "review", "done")])
    assert board.actual_minutes(state, state["cards"][0], T0 + timedelta(days=1)) == 300 + 10


def test_a_gap_is_idle_from_exactly_the_threshold(run_dir):
    add_card(run_dir, "C1", ["a.py"])
    state = board.load(run_dir)
    state["log"] = [entry(0, "C1", "todo", "doing"), entry(89), entry(89 + 90),
                    entry(89 + 90 + 5, "C1", "doing", "review"), entry(89 + 90 + 15, "C1", "review", "done")]
    assert board.actual_minutes(state, state["cards"][0], T0 + timedelta(days=1)) == 89 + 5 + 10


def test_an_open_span_counts_to_now_unless_the_session_is_idle(run_dir):
    add_card(run_dir, "C1", ["a.py"])
    state = board.load(run_dir)
    state["cards"][0]["status"] = "doing"
    state["log"] = [entry(0, "C1", "todo", "doing")]
    assert board.actual_minutes(state, state["cards"][0], T0 + timedelta(minutes=45)) == 45
    assert board.actual_minutes(state, state["cards"][0], T0 + timedelta(hours=9)) == 0


def test_estimate_accuracy_is_the_median_of_per_card_ratios(run_dir):
    for i in (1, 2, 3):
        add_card(run_dir, f"C{i}", [f"{i}.py"])
        run("card", run_dir, f"C{i}", "--update", "--estimate", "10")
    state = board.load(run_dir)
    for c in state["cards"]:
        c["status"] = "done"
    # actuals 10, 20 and 60 minutes against estimates of 10: ratios 1, 2, 6 (sum ratio would be 3.0)
    state["log"] = ([entry(0, "C1", "todo", "doing"), entry(10, "C1", "doing", "done"),
                     entry(10, "C2", "todo", "doing"), entry(30, "C2", "doing", "done"),
                     entry(30, "C3", "todo", "doing"), entry(60), entry(90, "C3", "doing", "done")])
    assert board.actual_minutes(state, state["cards"][2], T0 + timedelta(days=1)) == 60
    assert "actual/est ×2.0" in board.render_html(state)


def test_eta_is_hidden_when_closed_and_marks_later_days(run_dir):
    add_card(run_dir, "C1", ["a.py"])
    run("card", run_dir, "C1", "--update", "--estimate", "1800")  # 30 hours
    state = board.load(run_dir)
    extras = board.header_extras(state, T0)
    assert any(x.startswith("ETA ~") and " +1d" in x and x.endswith("(est.)") for x in extras), extras
    state["limit"] = 1
    state["cards"][0]["estimate"] = 30
    assert not any(" +" in x for x in board.header_extras(state, T0) if x.startswith("ETA"))
    state["cards"][0]["estimate"] = 3000  # ~2 days
    assert any(" +2d" in x for x in board.header_extras(state, T0))
    state["phase"] = "closed"
    assert not any(x.startswith("ETA") for x in board.header_extras(state, T0))


def test_a_card_in_progress_counts_what_is_left_of_its_estimate_with_a_floor(run_dir):
    add_card(run_dir, "C1", ["a.py"])
    run("card", run_dir, "C1", "--update", "--estimate", "30")
    state = board.load(run_dir)
    state["cards"][0]["status"] = "doing"
    state["log"] = [entry(0, "C1", "todo", "doing")]
    assert board.eta_minutes(state, T0 + timedelta(minutes=10)) == 20
    assert board.eta_minutes(state, T0 + timedelta(minutes=29)) == 6  # floor: 20% of the estimate


# ------------------------------------------------------------------ dropping and held files

def test_dropping_is_refused_while_the_cards_held_files_are_dirty(run_dir, tmp_path):
    repo = make_repo(tmp_path, ["a.py", "s.py"])
    run("repo", run_dir, repo)
    add_card(run_dir, "C1", ["a.py", "s.py"], repo="repo")
    add_card(run_dir, "C2", ["s.py"], repo="repo")
    move(run_dir, "C2", "doing")
    move(run_dir, "C2", "todo")
    move(run_dir, "C1", "doing")
    (repo / "s.py").write_text("half", encoding="utf-8")
    move(run_dir, "C1", "blocked")
    with pytest.raises(SystemExit, match="restore C1's files first: s.py"):
        move(run_dir, "C1", "dropped", why="superseded")
    assert card_of(run_dir, "C1")["status"] == "blocked"
    with pytest.raises(SystemExit, match="s.py"):
        move(run_dir, "C2", "doing")
    git(repo, "checkout", "--", "s.py")
    move(run_dir, "C1", "dropped", why="superseded")
    move(run_dir, "C2", "doing")
    assert card_of(run_dir, "C2")["status"] == "doing"


def test_a_clean_card_can_be_dropped_and_its_files_stop_holding(run_dir, tmp_path):
    repo = make_repo(tmp_path, ["s.py"])
    run("repo", run_dir, repo)
    add_card(run_dir, "C1", ["s.py"], repo="repo")
    add_card(run_dir, "C2", ["s.py"], repo="repo")
    move(run_dir, "C1", "doing")
    move(run_dir, "C1", "todo")
    move(run_dir, "C1", "dropped", why="not needed")
    move(run_dir, "C2", "doing")
    (repo / "s.py").write_text("own half-edit", encoding="utf-8")
    move(run_dir, "C2", "todo")
    move(run_dir, "C2", "doing")  # its own half-edit; the dropped card no longer holds the file
    assert card_of(run_dir, "C2")["status"] == "doing"


def test_dropped_cards_commit_is_labelled_in_rollback_show_and_md(run_dir, tmp_path, capsys):
    repo = make_repo(tmp_path, ["a.py"])
    run("repo", run_dir, repo)
    add_card(run_dir, "C1", ["a.py"], repo="repo")
    passing_review(run_dir, tmp_path, "C1", edit=lambda: (repo / "a.py").write_text("2", encoding="utf-8"))
    run("checkpoint", run_dir, "C1")
    sha = card_of(run_dir, "C1")["commit"][:7]
    move(run_dir, "C1", "blocked")
    move(run_dir, "C1", "dropped", why="superseded")
    capsys.readouterr()
    run("rollback", run_dir)
    assert any(sha in ln and "C1" in ln and "(dropped)" in ln for ln in capsys.readouterr().out.splitlines())
    run("show", run_dir)
    assert any("C1" in ln and sha in ln and "(dropped)" in ln for ln in capsys.readouterr().out.splitlines())
    assert f"commit: {sha} (dropped)" in (run_dir / "board.md").read_text(encoding="utf-8")


# ------------------------------------------------------------------ graph geometry

def test_an_edge_runs_from_the_deps_right_edge_to_the_dependents_left_edge(run_dir):
    add_card(run_dir, "C1", ["a.py"])
    add_card(run_dir, "C2", ["b.py"], deps=["C1"])
    lay = board.graph_layout(board.load(run_dir))
    d = re.search(r'data-edge="C1>C2"[^>]*d="([^"]+)"', html_of(run_dir)).group(1)
    nums = [int(n) for n in re.findall(r"-?\d+", d)]
    x1, y1, w1, h1 = lay["boxes"]["C1"]
    x2, y2, w2, h2 = lay["boxes"]["C2"]
    assert (nums[0], nums[1]) == (x1 + w1, y1 + board.NODE_H // 2)
    assert (nums[-2], nums[-1]) == (x2, y2 + board.NODE_H // 2)
    assert x1 + w1 < x2


# ------------------------------------------------------------------ stop races, heartbeats, failure memory

def test_a_stop_between_heals_check_and_its_lock_keeps_the_viewer_stopped(run_dir, monkeypatch):
    monkeypatch.delenv("CONSTRUCT_NO_VIEWER")
    port = board.free_port()
    with board.locked(run_dir):
        state = board.load(run_dir)
        state["viewer"] = {"port": port}
        board.finish(run_dir, state)
    real, calls = board.viewer_alive, {"n": 0}

    def alive(r, p, timeout=0.5):
        calls["n"] += 1
        found = real(r, p, timeout)
        if calls["n"] == 1:  # heal's unlocked check has just said "dead"; a stop lands now
            run("stop", r)
        return found
    monkeypatch.setattr(board, "viewer_alive", alive)

    def no_spawn(*a, **k):
        raise AssertionError("a stopped viewer must not be restarted")
    monkeypatch.setattr(board, "spawn_viewer", no_spawn)
    board.heal_viewer(run_dir)
    assert load(run_dir)["viewer"]["stopped"] is True
    assert not board.accepts(port, 0.3) and viewer_info(run_dir) is None


def test_ensure_viewer_leaves_stopped_and_closed_runs_alone(run_dir, monkeypatch):
    def no_spawn(*a, **k):
        raise AssertionError("must not spawn")
    monkeypatch.setattr(board, "spawn_viewer", no_spawn)
    with board.locked(run_dir):
        state = board.load(run_dir)
        state["viewer"] = {"port": board.free_port(), "stopped": True, "stop_gen": 1}
        board.finish(run_dir, state)
    assert board.ensure_viewer(run_dir) is None
    assert load(run_dir)["viewer"]["stopped"] is True
    with board.locked(run_dir):
        state = board.load(run_dir)
        state["viewer"].pop("stopped")
        state["phase"] = "closed"
        board.finish(run_dir, state)
    assert board.ensure_viewer(run_dir) is None


def test_a_stop_landing_while_serve_waits_wins_and_stays_sticky(viewer_run, monkeypatch):
    real, fired = board.wait_for_viewer, []

    def waiting(r, port, proc):
        if not fired:
            fired.append(1)
            run("stop", r)  # lands after serve spawned the viewer and released the lock
        return real(r, port, proc)
    monkeypatch.setattr(board, "wait_for_viewer", waiting)
    with pytest.raises(SystemExit, match="stop"):
        run("serve", viewer_run)
    viewer = load(viewer_run)["viewer"]
    assert viewer["stopped"] is True
    assert wait_for(viewer["port"], up=False, seconds=8)
    assert viewer_info(viewer_run) is None


def test_a_stop_while_serves_fallback_is_pending_does_not_launch_the_fallback(viewer_run, monkeypatch):
    import socket
    squatter = socket.socket()
    squatter.bind(("127.0.0.1", 0))  # bound, not listening: the child cannot bind it
    try:
        with board.locked(viewer_run):
            state = board.load(viewer_run)
            state["viewer"] = {"port": squatter.getsockname()[1]}
            board.finish(viewer_run, state)
        real, fired = board.wait_for_viewer, []

        def waiting(r, port, proc):
            found = real(r, port, proc)
            if not fired:
                fired.append(1)
                run("stop", r)  # lands between the failed first wait and the fallback decision
            return found
        monkeypatch.setattr(board, "wait_for_viewer", waiting)
        with pytest.raises(SystemExit, match="stop"):
            run("serve", viewer_run)
        assert load(viewer_run)["viewer"]["stopped"] is True
        assert viewer_info(viewer_run) is None
    finally:
        squatter.close()


def test_failed_at_is_set_only_when_the_last_attempt_fails(viewer_run, monkeypatch):
    class Dead:
        def poll(self):
            return 1
    monkeypatch.setattr(board, "spawn_viewer", lambda r, p: Dead())
    with pytest.raises(SystemExit, match="did not come up"):
        run("serve", viewer_run)
    assert load(viewer_run)["viewer"]["failed_at"]


def test_failed_at_clears_when_a_viewer_finally_comes_up(viewer_run):
    with board.locked(viewer_run):
        state = board.load(viewer_run)
        state["viewer"] = {"port": board.free_port(), "failed_at": "2020-01-01T00:00:00+00:00"}
        board.finish(viewer_run, state)
    run("serve", viewer_run)
    assert "failed_at" not in load(viewer_run)["viewer"]
    with board.locked(viewer_run):
        state = board.load(viewer_run)
        state["viewer"]["failed_at"] = board.now()
        board.finish(viewer_run, state)
    port = load(viewer_run)["viewer"]["port"]
    kill_pid(viewer_info(viewer_run)["pid"])
    assert wait_for(port, up=False)
    run("serve", viewer_run)  # explicit serve ignores the back-off and clears it on success
    assert "failed_at" not in load(viewer_run)["viewer"]


def test_progress_notes_and_dispatches_count_as_a_live_session(run_dir):
    add_card(run_dir, "C1", ["a.py"])
    state = board.load(run_dir)
    card = state["cards"][0]
    card["status"] = "done"
    card["progress"] = [{"t": iso(m), "who": "b", "text": "x"} for m in range(20, 120, 20)]
    state["log"] = [entry(0, "C1", "todo", "doing"), entry(120, "C1", "doing", "review"),
                    entry(125, "C1", "review", "done")]
    assert board.actual_minutes(state, card, T0 + timedelta(minutes=130)) == 125
    card["progress"] = []
    assert board.actual_minutes(state, card, T0 + timedelta(minutes=130)) == 5  # the same log alone is idle
    card["dispatches"] = [{"t": iso(m), "role": "builder", "agent": "a", "tier": None, "effort": None}
                          for m in (60,)]
    assert board.actual_minutes(state, card, T0 + timedelta(minutes=130)) == 125  # one dispatch in the middle splits the idle stretch


def test_done_cards_without_measured_time_are_left_out_of_the_accuracy(run_dir):
    for i in (1, 2):
        add_card(run_dir, f"C{i}", [f"{i}.py"])
        run("card", run_dir, f"C{i}", "--update", "--estimate", "10")
    state = board.load(run_dir)
    for c in state["cards"]:
        c["status"] = "done"
    state["log"] = [entry(0, "C1", "todo", "doing"), entry(20, "C1", "doing", "done")]  # C2 has no timing
    text = board.render_html(state)
    assert "actual/est ×2.0" in text


def test_serve_port_must_be_unprivileged(run_dir):
    for bad in ("80", "1023", "70000", "0"):
        with pytest.raises(SystemExit):
            run("serve", run_dir, "--port", bad)


def test_dropping_reports_a_git_failure_in_a_held_repo_in_one_line(run_dir, tmp_path):
    add_card(run_dir, "C1", ["a.py"])
    move(run_dir, "C1", "doing")
    move(run_dir, "C1", "todo")
    state = load(run_dir)
    state["repos"][0]["path"] = (tmp_path / "gone").as_posix()
    (run_dir / "board.json").write_text(json.dumps(state), encoding="utf-8")
    with pytest.raises(SystemExit, match="C1 cannot be dropped: git failed in repo main") as e:
        move(run_dir, "C1", "dropped", why="x")
    assert "\n" not in str(e.value)


# ------------------------------------------------------------------ lead merges

def commit_on(repo, branch, files, message):
    """Commit `files` (path -> text, None deletes it) on `branch`, then return to the branch checked out before."""
    back = git_out(repo, "branch", "--show-current")
    git(repo, "switch", branch)
    for name, text in files.items():
        if text is None:
            git(repo, "rm", "-q", "--", name)
        else:
            (repo / name).write_text(text, encoding="utf-8")
    git(repo, "add", "-A")
    git(repo, "commit", "-m", message)
    git(repo, "switch", back)
    return git_out(repo, "rev-parse", branch)


def blob(repo, rev_path):
    return subprocess.run(["git", "-C", str(repo), "cat-file", "-p", rev_path], check=True,
                          capture_output=True).stdout


def merge_run(tmp_path, files, ours, theirs):
    """A run whose repo has `files` at its root commit, a feature commit `ours` (path -> text, None deletes)
    that the run starts from, and an `upstream` branch from the root commit carrying `theirs`."""
    d = bare_run(tmp_path)
    repo = make_repo(tmp_path, files, name="proj")
    git(repo, "branch", "upstream")
    commit_on(repo, git_out(repo, "branch", "--show-current"), ours, "feature work")
    run("repo", d, repo)
    ref_sha = commit_on(repo, "upstream", theirs, "upstream work")
    return d, repo, ref_sha


def test_merge_without_conflicts_makes_one_merge_commit_and_records_it(run_dir, tmp_path, capsys, monkeypatch):
    repo = tmp_path / "main"
    base = load(run_dir)["repos"][0]["base"]
    git(repo, "branch", "upstream")
    commit_on(repo, "upstream", {"up.py": "1"}, "upstream one")
    ref_sha = commit_on(repo, "upstream", {"up2.py": "2"}, "upstream two")
    monkeypatch.delenv("CONSTRUCT_NO_VIEWER")
    healed = []
    monkeypatch.setattr(board, "heal_viewer", lambda r: healed.append(r))
    capsys.readouterr()
    run("merge", run_dir, "main", "upstream")
    sha = git_out(repo, "rev-parse", "HEAD")
    assert capsys.readouterr().out.split()[0] == sha
    # upstream is a fast-forward of the run branch; the merge is still one merge commit
    assert git_out(repo, "rev-parse", "HEAD^2") == ref_sha and git_out(repo, "rev-parse", "HEAD^1") == base
    assert git_out(repo, "rev-list", "--merges", f"{base}..HEAD").split() == [sha]
    assert git_out(repo, "branch", "--show-current") == "construct/run1"
    assert git_out(repo, "status", "--porcelain") == ""
    message = git_out(repo, "log", "-1", "--format=%B")
    assert message.splitlines()[0] == f"construct(run1): merge upstream ({ref_sha[:7]})"
    assert "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>" in message
    assert load(run_dir)["repos"][0]["merges"] == [{"sha": sha, "ref": "upstream", "ref_sha": ref_sha,
                                                    "whole_file_from_ref": []}]
    assert f"merge upstream ({ref_sha[:7]})" in load(run_dir)["log"][-1]["why"]
    md = (run_dir / "board.md").read_text(encoding="utf-8")
    assert f"- main: merged upstream ({ref_sha[:7]}) as {sha[:7]}" in md
    assert healed


def test_merge_with_conflicts_aborts_and_names_every_conflicted_path(tmp_path):
    d, repo, ref_sha = merge_run(tmp_path, ["a.py", "b.py", "c.py"], {"a.py": "ours", "b.py": "ours"},
                                 {"a.py": "theirs", "b.py": "theirs", "c.py": "theirs"})
    head = git_out(repo, "rev-parse", "HEAD")
    with pytest.raises(SystemExit, match="merge aborted") as e:
        run("merge", d, "proj", "upstream")
    assert "a.py" in str(e.value) and "b.py" in str(e.value) and "c.py" not in str(e.value)
    assert "--conflicts theirs" in str(e.value)
    assert not (repo / ".git" / "MERGE_HEAD").exists()
    assert git_out(repo, "rev-parse", "HEAD") == head
    assert git_out(repo, "status", "--porcelain") == ""
    assert (repo / "a.py").read_text(encoding="utf-8") == "ours"
    assert load(d)["repos"][0].get("merges", []) == []


def test_merge_conflicts_theirs_takes_the_refs_whole_file_and_records_the_paths(tmp_path, capsys):
    d, repo, ref_sha = merge_run(
        tmp_path, ["a.py", "b.py", "gone.py", "back.py"],
        {"a.py": "ours 1\nours 2\n", "gone.py": "ours edit", "back.py": None},
        {"a.py": "theirs 1\ntheirs 2\ntheirs 3\n", "gone.py": None, "back.py": "theirs edit", "new.py": "new"})
    pre = git_out(repo, "rev-parse", "HEAD")
    root = git_out(repo, "rev-parse", "upstream^1")
    capsys.readouterr()
    run("merge", d, "proj", "upstream", "--conflicts", "theirs")
    out = capsys.readouterr().out
    sha = git_out(repo, "rev-parse", "HEAD")
    assert out.split()[0] == sha
    assert git_out(repo, "rev-parse", "HEAD^2") == ref_sha
    assert (repo / "a.py").read_bytes() == blob(repo, "upstream:a.py")
    assert (repo / "back.py").read_bytes() == blob(repo, "upstream:back.py")
    assert not (repo / "gone.py").exists() and "gone.py" not in git_out(repo, "ls-files").split()
    assert (repo / "new.py").read_bytes() == blob(repo, "upstream:new.py")
    assert git_out(repo, "status", "--porcelain") == ""
    assert not re.search(r"^(<<<<<<< |>>>>>>> |=======$)", (repo / "a.py").read_text(encoding="utf-8"), re.M)
    whole = ["a.py", "back.py", "gone.py"]
    assert load(d)["repos"][0]["merges"][0]["whole_file_from_ref"] == whole
    assert all(p in out for p in whole)
    message = git_out(repo, "log", "-1", "--format=%B")
    assert all(f"- {p}" in message for p in whole)
    # our side is everything since the merge base, including the feature commit the run started from
    assert f"git diff {root} {pre} -- <path>" in message
    assert git_out(repo, "diff", root, pre, "--", "a.py")


def test_merge_conflicts_theirs_refuses_a_file_that_still_has_marker_lines(tmp_path):
    d, repo, _ = merge_run(tmp_path, ["a.py"], {"a.py": "ours"}, {"a.py": "theirs\n=======\nmore\n"})
    head = git_out(repo, "rev-parse", "HEAD")
    with pytest.raises(SystemExit, match="conflict marker.*a.py"):
        run("merge", d, "proj", "upstream", "--conflicts", "theirs")
    assert not (repo / ".git" / "MERGE_HEAD").exists()
    assert git_out(repo, "rev-parse", "HEAD") == head and git_out(repo, "status", "--porcelain") == ""
    assert load(d)["repos"][0].get("merges", []) == []


def test_merge_refusals_leave_repo_and_board_untouched(run_dir, tmp_path):
    repo = tmp_path / "main"
    base = load(run_dir)["repos"][0]["base"]
    git(repo, "branch", "upstream")
    commit_on(repo, "upstream", {"up.py": "1"}, "upstream one")
    shared = make_repo(tmp_path, ["a.py"], name="shared")
    git(shared, "branch", "upstream")
    run("repo", run_dir, shared, "--no-branch")
    with pytest.raises(SystemExit, match="unknown repo ghost"):
        run("merge", run_dir, "ghost", "upstream")
    with pytest.raises(SystemExit, match="no-branch repo shared"):
        run("merge", run_dir, "shared", "upstream")
    with pytest.raises(SystemExit, match="ref nope does not resolve"):
        run("merge", run_dir, "main", "nope")
    with pytest.raises(SystemExit, match="already contains"):
        run("merge", run_dir, "main", base)
    (repo / "x.txt").write_text("dirt", encoding="utf-8")
    with pytest.raises(SystemExit, match="uncommitted changes: x.txt"):
        run("merge", run_dir, "main", "upstream")
    (repo / "x.txt").unlink()
    git(repo, "switch", "-c", "elsewhere")
    with pytest.raises(SystemExit, match="main is on branch elsewhere, expected construct/run1"):
        run("merge", run_dir, "main", "upstream")
    git(repo, "switch", "construct/run1")
    assert git_out(repo, "rev-parse", "HEAD") == base
    assert all(not r.get("merges") for r in load(run_dir)["repos"])


def test_merge_refuses_a_commit_whose_second_parent_is_not_the_ref(run_dir, tmp_path):
    repo = tmp_path / "main"
    git(repo, "branch", "upstream")
    commit_on(repo, "upstream", {"up.py": "1"}, "upstream one")
    (repo / ".git" / "hooks" / "post-commit").write_text(
        '#!/bin/sh\n[ -n "$REWRITTEN" ] && exit 0\n'
        'git reset -q --soft HEAD^1 && REWRITTEN=1 git commit -q -m rewritten\n', encoding="utf-8")
    with pytest.raises(SystemExit, match="commit [0-9a-f]{7} made but not recorded"):
        run("merge", run_dir, "main", "upstream")
    assert load(run_dir)["repos"][0].get("merges", []) == []


def test_a_failed_merge_or_merge_commit_leaves_no_merge_in_progress(run_dir, tmp_path):
    repo = tmp_path / "main"
    base = load(run_dir)["repos"][0]["base"]
    git(repo, "branch", "upstream")
    commit_on(repo, "upstream", {"up.py": "1"}, "upstream one")
    (repo / ".git" / "index.lock").write_text("", encoding="utf-8")
    with pytest.raises(SystemExit, match="merge: git merge failed in main: "):
        run("merge", run_dir, "main", "upstream")
    (repo / ".git" / "index.lock").unlink()
    (repo / ".git" / "hooks" / "pre-commit").write_text("#!/bin/sh\necho hook says no\nexit 1\n", encoding="utf-8")
    with pytest.raises(SystemExit, match="merge: git commit failed in main, merge aborted: hook says no"):
        run("merge", run_dir, "main", "upstream")
    assert not (repo / ".git" / "MERGE_HEAD").exists()
    assert git_out(repo, "rev-parse", "HEAD") == base and git_out(repo, "status", "--porcelain") == ""
    assert load(run_dir)["repos"][0].get("merges", []) == []


def test_rollback_counts_what_each_merge_of_the_same_ref_brought_in(run_dir, tmp_path, capsys):
    repo = tmp_path / "main"
    git(repo, "branch", "upstream")
    commit_on(repo, "upstream", {"up.py": "1"}, "upstream one")
    commit_on(repo, "upstream", {"up2.py": "2"}, "upstream two")
    run("merge", run_dir, "main", "upstream")
    first = git_out(repo, "rev-parse", "HEAD")
    commit_on(repo, "upstream", {"up3.py": "3"}, "upstream three")
    run("merge", run_dir, "main", "upstream")
    second = git_out(repo, "rev-parse", "HEAD")
    capsys.readouterr()
    run("rollback", run_dir)
    out = capsys.readouterr().out
    assert f"merged in upstream at {first[:7]} (2 commits)" in out
    assert f"merged in upstream at {second[:7]} (1 commit)" in out
    assert "not from this run" not in out and "branch -D construct/run1" in out


def merged_run(run_dir, tmp_path):
    """C1 checkpointed on the run branch, then upstream (two commits) merged in. Returns (repo, merge sha)."""
    repo = tmp_path / "main"
    git(repo, "branch", "upstream")
    commit_on(repo, "upstream", {"up.py": "1"}, "upstream one")
    commit_on(repo, "upstream", {"up2.py": "2"}, "upstream two")
    add_card(run_dir, "C1", ["a.py"])
    passing_review(run_dir, tmp_path, edit=lambda: (repo / "a.py").write_text("mine", encoding="utf-8"))
    run("checkpoint", run_dir, "C1")
    run("merge", run_dir, "main", "upstream")
    return repo, git_out(repo, "rev-parse", "HEAD")


def test_rollback_after_a_recorded_merge_deletes_the_branch_and_summarises_the_merge(run_dir, tmp_path, capsys):
    repo, merge = merged_run(run_dir, tmp_path)
    state = load(run_dir)["repos"][0]
    capsys.readouterr()
    run("rollback", run_dir)
    out = capsys.readouterr().out
    assert "not from this run" not in out
    assert "upstream one" not in out and "upstream two" not in out
    assert f"merged in upstream at {merge[:7]} (2 commits)" in out
    assert f'git -C "{state["path"]}" revert -m 1 {merge}' in out
    assert "later cards may build on it" in out
    assert "branch -D construct/run1" in out and "-discarded" not in out
    apply_plan(out)
    assert git_out(repo, "rev-parse", "HEAD") == state["base"]
    assert git_out(repo, "branch", "--show-current") == state["original_branch"]


def test_rollback_after_a_merge_still_keeps_an_unrecorded_commit(run_dir, tmp_path, capsys):
    repo, _ = merged_run(run_dir, tmp_path)
    (repo / "mine.txt").write_text("user work", encoding="utf-8")
    commit_all(repo, "my own work")
    capsys.readouterr()
    run("rollback", run_dir)
    out = capsys.readouterr().out
    assert "not from this run" in out and "my own work" in out
    assert "upstream one" not in out and "upstream two" not in out
    assert "branch -m construct/run1 construct/run1-discarded" in out and "branch -D" not in out


def test_a_board_without_merges_loads_rolls_back_and_merges(run_dir, tmp_path, capsys):
    repo = tmp_path / "main"
    add_card(run_dir, "C1", ["a.py"])
    passing_review(run_dir, tmp_path, edit=lambda: (repo / "a.py").write_text("mine", encoding="utf-8"))
    run("checkpoint", run_dir, "C1")
    state = load(run_dir)
    for r in state["repos"]:
        r.pop("merges", None)
    (run_dir / "board.json").write_text(json.dumps(state), encoding="utf-8")
    capsys.readouterr()
    run("rollback", run_dir)
    out = capsys.readouterr().out
    assert "branch -D construct/run1" in out and "merged in" not in out and "revert -m" not in out
    run("show", run_dir)
    git(repo, "branch", "upstream", "HEAD^1")
    commit_on(repo, "upstream", {"up.py": "1"}, "upstream one")
    run("merge", run_dir, "main", "upstream")
    assert len(load(run_dir)["repos"][0]["merges"]) == 1


# ------------------------------------------------------------------ build cards without files

def test_a_fileless_build_card_needs_a_resource(run_dir):
    add_card(run_dir, "C1", repo=None, resources=["stand"])
    c = card_of(run_dir, "C1")
    assert (c["kind"], c["repo"], c["files"], c["resources"]) == ("build", None, [], ["stand"])
    with pytest.raises(SystemExit, match="--files is required.*--resources"):
        add_card(run_dir, "C2", repo=None)
    with pytest.raises(SystemExit, match="--files is required"):
        add_card(run_dir, "C3", resources=["stand"])  # a repo still needs its file set
    with pytest.raises(SystemExit, match="--files is required"):
        run("card", run_dir, "C1", "--update", "--resources")
    assert card_of(run_dir, "C1")["resources"] == ["stand"]


def test_a_fileless_build_card_runs_and_goes_done_without_a_commit(run_dir, tmp_path, capsys):
    add_card(run_dir, "C1", repo=None, resources=["stand"])
    add_card(run_dir, "C2", ["a.py"], deps=["C1"])
    add_card(run_dir, "C3", ["b.py"], resources=["stand"])
    out = eligible(run_dir, capsys)
    assert out.out.split() == ["C1"]
    assert "C3 skipped: resource stand is in use by C1" in out.err
    passing_review(run_dir, tmp_path)
    head = git_out(tmp_path / "main", "rev-parse", "HEAD")
    with pytest.raises(SystemExit, match="C1 has no files: nothing to commit; move it done after its review PASS"):
        run("checkpoint", run_dir, "C1")
    move(run_dir, "C1", "done")
    c = card_of(run_dir, "C1")
    assert c["status"] == "done" and "commit" not in c
    assert git_out(tmp_path / "main", "rev-parse", "HEAD") == head
    capsys.readouterr()
    run("handoff", run_dir, "C2")
    assert "### C1: Title C1 (done)" in capsys.readouterr().out
    assert eligible(run_dir, capsys).out.split() == ["C2", "C3"]
    run("show", run_dir)
    assert any(ln.startswith("C1") and "build -" in ln for ln in capsys.readouterr().out.splitlines())
    assert "C1: Title C1" in (run_dir / "board.md").read_text(encoding="utf-8")
    assert '<span class="chip resource">stand</span>' in section(html_of(run_dir), "done")
    run("rollback", run_dir)
    assert "branch -D construct/run1" in capsys.readouterr().out
