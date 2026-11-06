"""Lanes: tests as the gate (--review none), a worker resumed per lane, stale handbacks refused, lead-built cards."""
import json

import pytest

from test_board import add_card, card_of, git_out, load, make_repo, make_transcript, run, run_dir  # noqa: F401
from test_dispatch import dispatches_of, returns


def lane_card(run_dir, cid, lane, files, deps=(), size="S"):
    add_card(run_dir, cid, files, deps=deps)
    run("card", run_dir, cid, "--update", "--size", size, "--review", "none", "--lane", lane)


def gated_none(tmp_path, exit_code):
    """A run whose repo gate exits with exit_code, and a --review none card C1 in doing with a changed file."""
    import sys
    d = tmp_path / "gn"
    repo = make_repo(tmp_path, ["a.py"], name="g")
    run("init", d, "--title", "Gated", "--limit", "2", "--route", "lanes")
    run("team", d, "implementer", "--role", "builder", "--tier", "sonnet")
    run("team", d, "code-reviewer", "--role", "reviewer", "--tier", "opus")
    run("repo", d, repo, "--gate", f'"{sys.executable}" -c "import sys; sys.exit({exit_code})" {{files}}')
    add_card(d, "C1", ["a.py"], repo="g")
    run("card", d, "C1", "--update", "--size", "S", "--review", "none")
    run("dispatch", d)
    (repo / "a.py").write_text("changed", encoding="utf-8")
    return d, repo


def test_a_review_none_card_is_committed_and_done_on_a_green_gate(tmp_path, capsys):
    d, repo = gated_none(tmp_path, 0)
    out = returns(d, tmp_path / "p", "C1", "b1", "DONE built", capsys)
    c1 = card_of(d, "C1")
    assert c1["status"] == "done" and c1["commit"] == git_out(repo, "rev-parse", "HEAD")
    assert dispatches_of(out) == [] and "done on its gate" in out


def test_a_review_none_card_with_a_red_gate_still_retries(tmp_path, capsys):
    d, _ = gated_none(tmp_path, 1)
    returns(d, tmp_path / "p", "C1", "b1", "DONE built", capsys)
    assert (card_of(d, "C1")["status"], card_of(d, "C1")["tries"], card_of(d, "C1")["commit"] if
            "commit" in card_of(d, "C1") else None) == ("doing", 2, None)


def test_the_next_card_of_a_lane_says_resume_its_worker(run_dir, tmp_path, capsys):
    repo = tmp_path / "main"
    lane_card(run_dir, "C1", "stats", ["a.py"])
    lane_card(run_dir, "C2", "stats", ["b.py"], deps=["C1"])
    capsys.readouterr()
    run("dispatch", run_dir)
    (first,) = dispatches_of(capsys.readouterr().out)
    assert (first["lane"], first["resume"]) == ("stats", False)  # nobody works the lane yet
    (repo / "a.py").write_text("mine", encoding="utf-8")
    out = returns(run_dir, tmp_path / "p", "C1", "w1", "DONE", capsys)
    (second,) = dispatches_of(out)
    assert (second["card"], second["lane"], second["resume"]) == ("C2", "stats", True)
    assert "Lane stats: one worker builds its cards" in (run_dir / "briefs" / "C2-build-1.md").read_text(encoding="utf-8")


def test_a_lane_whose_next_card_needs_another_tier_gets_a_fresh_worker(run_dir, tmp_path, capsys):
    repo = tmp_path / "main"
    lane_card(run_dir, "C1", "stats", ["a.py"], size="S")
    lane_card(run_dir, "C2", "stats", ["b.py"], deps=["C1"], size="M")  # sonnet built C1; C2 needs opus
    run("dispatch", run_dir)
    (repo / "a.py").write_text("mine", encoding="utf-8")
    (second,) = dispatches_of(returns(run_dir, tmp_path / "p", "C1", "w1", "DONE", capsys))
    assert (second["model"], second["resume"]) == ("opus", False)


def test_a_handback_older_than_the_dispatch_is_refused(run_dir, tmp_path, capsys):
    lane_card(run_dir, "C1", "stats", ["a.py"])
    run("dispatch", run_dir)
    path = make_transcript(tmp_path / "p", "w1", ["DONE the previous card"], sub="w1")
    rows = [json.loads(ln) for ln in path.read_text(encoding="utf-8").splitlines()]
    rows[-1]["timestamp"] = "2020-01-01T00:00:00Z"  # handed back long before C1 was dispatched
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    with pytest.raises(SystemExit, match="predates C1's dispatch"):
        run("returned", run_dir, "C1", "--agent", "w1", "--projects-dir", tmp_path / "p")
    assert card_of(run_dir, "C1")["status"] == "doing" and card_of(run_dir, "C1")["reports"] == []


def test_a_lead_built_card_dispatches_to_the_lead_and_returns_by_file(run_dir, tmp_path, capsys):
    repo = tmp_path / "main"
    body = run_dir / "b.txt"
    body.write_text("everything", encoding="utf-8")
    run("card", run_dir, "C1", "--title", "All of it", "--builder", "lead", "--reviewer", "code-reviewer",
        "--repo", "main", "--files", "a.py", "--body-file", body)
    capsys.readouterr()
    run("dispatch", run_dir)
    out = capsys.readouterr().out
    assert out.startswith("self C1: you build it") and dispatches_of(out) == []
    assert card_of(run_dir, "C1")["status"] == "doing" and not (run_dir / "briefs" / "C1-build-1.md").exists()
    (repo / "a.py").write_text("built by the lead", encoding="utf-8")
    report = tmp_path / "lead-report.md"
    report.write_text("DONE all of it\n## Handoff\nnone", encoding="utf-8")
    run("returned", run_dir, "C1", "--self", report)
    (rv,) = dispatches_of(capsys.readouterr().out)
    assert rv["subagent_type"] == "code-reviewer" and card_of(run_dir, "C1")["status"] == "review"
    assert (run_dir / "reports" / "C1-build-1.md").read_text(encoding="utf-8").startswith("DONE all of it")
    assert "### C1 build-1 (lead)" not in (run_dir / "lessons.md").read_text(encoding="utf-8") \
        if (run_dir / "lessons.md").exists() else True


def test_only_the_builder_role_may_be_the_lead(run_dir):
    body = run_dir / "b.txt"
    body.write_text("x", encoding="utf-8")
    with pytest.raises(SystemExit, match="lead is not on the team as reviewer"):
        run("card", run_dir, "C1", "--title", "T", "--builder", "implementer", "--reviewer", "lead",
            "--repo", "main", "--files", "a.py", "--body-file", body)
    assert load(run_dir)["cards"] == []


def test_init_needs_a_route_and_show_prints_it(tmp_path, capsys):
    with pytest.raises(SystemExit):
        run("init", tmp_path / "r", "--title", "T")  # no --route: argparse refuses
    run("init", tmp_path / "r", "--title", "T", "--route", "single")
    capsys.readouterr()
    run("show", tmp_path / "r")
    assert "[shaping, route single]" in capsys.readouterr().out


def test_watch_exits_on_its_heartbeat_with_no_stalls(run_dir, tmp_path, capsys):
    capsys.readouterr()
    run("watch", run_dir, "--heartbeat", "0", "--interval", "1", "--projects-dir", tmp_path / "p")
    assert capsys.readouterr().out.startswith("watch: heartbeat after 0 min, no stalls")


def test_init_reminds_that_lanes_are_opt_in_and_single_says_nothing(tmp_path, capsys):
    run("init", tmp_path / "lanes", "--title", "T", "--route", "lanes")
    assert "only when the user asked for lanes" in capsys.readouterr().err
    run("init", tmp_path / "single", "--title", "T", "--route", "single")
    assert capsys.readouterr().err == ""
