"""dispatch, returned, watch and the plan's shape: the commands that run the lead's loop for it."""
import json
import os
import re
import sys
from datetime import datetime, timedelta

import pytest

import board
from test_board import add_card, card_of, git_out, load, make_repo, make_transcript, run, run_dir  # noqa: F401


def dispatches_of(out: str) -> list[dict]:
    return [json.loads(ln[len("dispatch "):]) for ln in out.splitlines() if ln.startswith("dispatch ")]


def sized_card(run_dir, cid, size=None, files=None, deps=(), kind=None, review=None):
    add_card(run_dir, cid, files, deps=deps, kind=kind)
    extra = (["--size", size] if size else []) + (["--review", review] if review else [])
    if extra:
        run("card", run_dir, cid, "--update", *extra)


def returns(run_dir, projects, cid, agent, message, capsys):
    make_transcript(projects, agent, [message], sub=agent)
    capsys.readouterr()
    run("returned", run_dir, cid, "--agent", agent, "--projects-dir", projects)
    return capsys.readouterr().out


def test_dispatch_starts_eligible_cards_at_their_size_tier_and_fills_the_brief(run_dir, capsys):
    run("set", run_dir, "--limit", "3")
    sized_card(run_dir, "C1", "S", ["a.py"])
    sized_card(run_dir, "C2", "L", ["b.py"])
    sized_card(run_dir, "C3", None, ["c.py"])  # an unsized build card counts as M
    sized_card(run_dir, "C4", "S", ["d.py"], deps=["C1"])
    capsys.readouterr()
    run("dispatch", run_dir)
    got = {d["card"]: d for d in dispatches_of(capsys.readouterr().out)}
    assert sorted(got) == ["C1", "C2", "C3"]
    assert (got["C1"]["model"], got["C1"]["effort"]) == ("sonnet", "medium")
    assert (got["C2"]["model"], got["C2"]["effort"]) == ("opus", "high")
    assert (got["C3"]["model"], got["C3"]["effort"]) == ("opus", "medium")
    assert got["C1"]["subagent_type"] == "implementer" and got["C1"]["run_in_background"] is True
    brief = run_dir / "briefs" / "C1-build-1.md"
    assert str(brief) in got["C1"]["prompt"]
    assert "builder for card C1 of construct run run1" in got["C1"]["prompt"]
    text = brief.read_text(encoding="utf-8")
    assert "card C1 of construct run run1" in text and str(run_dir / "cards" / "C1.md") in text
    assert not re.search(r"\{\w+\}", text), "an unfilled placeholder"
    assert "Earlier tries" not in text  # first try: the retry line is left out
    c1 = card_of(run_dir, "C1")
    assert c1["status"] == "doing" and c1["dispatches"][-1]["tier"] == "sonnet"
    assert card_of(run_dir, "C4")["status"] == "todo"


def test_fill_keeps_a_tagged_line_only_when_its_condition_holds():
    template = "a {x}\n[if yes] kept {x}\n[if no] dropped\n{unknown} stays"
    assert board.fill(template, {"x": 1}, {"yes": True, "no": False}) == "a 1\nkept 1\n{unknown} stays"


def test_question_card_gets_the_question_brief_and_sonnet(run_dir, capsys):
    run("team", run_dir, "experimenter", "--role", "builder", "--tier", "sonnet")
    body = run_dir / "q.txt"
    body.write_text("q", encoding="utf-8")
    run("card", run_dir, "C1", "--title", "Q", "--builder", "experimenter", "--reviewer", "code-reviewer",
        "--kind", "question", "--body-file", body)
    capsys.readouterr()
    run("dispatch", run_dir)
    (d,) = dispatches_of(capsys.readouterr().out)
    assert d["model"] == "sonnet" and "answering question card C1" in d["prompt"]
    brief = (run_dir / "briefs" / "C1-build-1.md").read_text(encoding="utf-8")
    assert brief.startswith("You are answering question card C1")


@pytest.fixture
def gated(tmp_path):
    def make(exit_code):
        d = tmp_path / "gated"
        repo = make_repo(tmp_path, ["a.py"], name="g")
        run("init", d, "--title", "Gated", "--limit", "2", "--route", "lanes")
        run("team", d, "implementer", "--role", "builder", "--tier", "sonnet")
        run("team", d, "code-reviewer", "--role", "reviewer", "--tier", "opus")
        run("repo", d, repo, "--gate", f'"{sys.executable}" -c "import sys; sys.exit({exit_code})" {{files}}')
        add_card(d, "C1", ["a.py"], repo="g")
        run("card", d, "C1", "--update", "--size", "S")
        run("dispatch", d)
        (repo / "a.py").write_text("changed", encoding="utf-8")
        return d
    return make


def test_returned_done_with_a_green_gate_goes_to_review_with_a_reviewer_dispatch(gated, tmp_path, capsys):
    d = gated(0)
    out = returns(d, tmp_path / "p", "C1", "b1", "DONE built\n## Handoff\nnone", capsys)
    c1 = card_of(d, "C1")
    assert c1["status"] == "review" and c1["bounces"] == 0
    (rv,) = dispatches_of(out)
    assert rv["subagent_type"] == "code-reviewer" and (rv["model"], rv["effort"]) == ("opus", "medium")
    assert "reviewer for card C1" in rv["prompt"]
    review_brief = (d / "briefs" / "C1-review-1.md").read_text(encoding="utf-8")
    assert "DEPTH: standard. BUDGET: at most ~25 tool calls." in review_brief
    assert 'diff -- "a.py"' in review_brief and "A question card has no diff" not in review_brief
    assert (d / "reports" / "C1-build-1.md").read_text(encoding="utf-8").startswith("DONE built")


def test_returned_done_with_a_red_gate_retries_without_a_bounce(gated, tmp_path, capsys):
    d = gated(1)
    out = returns(d, tmp_path / "p", "C1", "b1", "DONE built", capsys)
    c1 = card_of(d, "C1")
    assert (c1["status"], c1["tries"], c1["bounces"]) == ("doing", 2, 0)
    assert "gate red" in out
    assert (d / "reports" / "C1-gate-1.md").read_text(encoding="utf-8").startswith("$ ")
    (again,) = dispatches_of(out)
    assert again["model"] == "sonnet"  # a gate retry is not an escalation
    assert "C1-gate-1.md" in (d / "briefs" / "C1-build-2.md").read_text(encoding="utf-8")


def test_returned_pass_checkpoints_marks_done_and_dispatches_what_it_unblocked(run_dir, tmp_path, capsys):
    repo = tmp_path / "main"
    sized_card(run_dir, "C1", "M", ["a.py"])
    sized_card(run_dir, "C2", "S", deps=["C1"], kind="question")  # waits for done, unlike a build card
    run("dispatch", run_dir)
    (repo / "a.py").write_text("mine", encoding="utf-8")
    returns(run_dir, tmp_path / "p", "C1", "b1", "DONE", capsys)
    assert card_of(run_dir, "C2")["status"] == "todo"
    out = returns(run_dir, tmp_path / "p", "C1", "r1", "PASS fine", capsys)
    c1 = card_of(run_dir, "C1")
    assert c1["status"] == "done" and c1["commit"] == git_out(repo, "rev-parse", "HEAD")
    assert [d["card"] for d in dispatches_of(out)] == ["C2"] and card_of(run_dir, "C2")["status"] == "doing"
    assert "C1 review-1: PASS fine -> done, checkpoint" in out


def test_returned_fail_bounces_escalates_a_sonnet_card_and_dispatches_nothing(run_dir, tmp_path, capsys):
    sized_card(run_dir, "C1", "S", ["a.py"])
    sized_card(run_dir, "C2", "S", ["b.py"], deps=["C1"])
    run("dispatch", run_dir)
    returns(run_dir, tmp_path / "p", "C1", "b1", "DONE", capsys)
    out = returns(run_dir, tmp_path / "p", "C1", "r1", "FAIL\nthe guard is vacuous: a.py:3", capsys)
    c1 = card_of(run_dir, "C1")
    assert (c1["status"], c1["bounces"], c1["bump"]) == ("todo", 1, 1)
    assert dispatches_of(out) == [] and "defect class" in out
    assert "the guard is vacuous" in load(run_dir)["log"][-1]["why"]
    capsys.readouterr()
    run("dispatch", run_dir)
    (again,) = dispatches_of(capsys.readouterr().out)
    assert again["model"] == "opus"
    retry = (run_dir / "briefs" / "C1-build-2.md").read_text(encoding="utf-8")
    assert "C1-review-1.md" in retry and "C1-build-1.md" in retry


def test_returned_fail_on_an_opus_card_does_not_escalate(run_dir, tmp_path, capsys):
    sized_card(run_dir, "C1", "M", ["a.py"])
    run("dispatch", run_dir)
    returns(run_dir, tmp_path / "p", "C1", "b1", "DONE", capsys)
    returns(run_dir, tmp_path / "p", "C1", "r1", "FAIL\nx", capsys)
    assert card_of(run_dir, "C1")["bump"] == 0


def test_returned_third_fail_blocks(run_dir, tmp_path, capsys):
    sized_card(run_dir, "C1", "M", ["a.py"])
    for n in (1, 2, 3):
        run("dispatch", run_dir)
        returns(run_dir, tmp_path / "p", "C1", f"b{n}", "DONE", capsys)
        out = returns(run_dir, tmp_path / "p", "C1", f"r{n}", "FAIL\nstill wrong", capsys)
    assert card_of(run_dir, "C1")["status"] == "blocked" and "third FAIL" in out


@pytest.mark.parametrize("verdict, bump", [("BLOCKED: refused: Permission denied", 0),
                                           ("BLOCKED: needs b.py: the helper lives there", 1)])
def test_returned_blocked_blocks_and_escalates_all_but_a_refusal(run_dir, tmp_path, capsys, verdict, bump):
    sized_card(run_dir, "C1", "S", ["a.py"])
    run("dispatch", run_dir)
    out = returns(run_dir, tmp_path / "p", "C1", "b1", verdict, capsys)
    c1 = card_of(run_dir, "C1")
    assert (c1["status"], c1["bump"]) == ("blocked", bump)
    assert ("refusal" in out) == (bump == 0)


def test_returned_refuses_a_card_that_is_not_active(run_dir, tmp_path):
    add_card(run_dir, "C1", ["a.py"])
    make_transcript(tmp_path / "p", "b1", ["DONE"], sub="b1")
    with pytest.raises(SystemExit, match="only doing or review cards return"):
        run("returned", run_dir, "C1", "--agent", "b1", "--projects-dir", tmp_path / "p")


def watched_transcript(projects, agent, slug, brief_name, rows):
    path = projects / "sess" / agent / "subagents" / f"agent-{agent}.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    first = {"type": "user", "timestamp": rows[0][0], "message": {
        "role": "user", "content": f"You are the builder for card C1 of construct run {slug}. Your brief is "
                                   f"x/briefs/{brief_name}: read it first"}}
    out = [first] + [{"type": kind, "timestamp": t, "message": {"role": kind, "content": content}}
                     for t, kind, content in rows[1:]]
    path.write_text("\n".join(json.dumps(r) for r in out) + "\n", encoding="utf-8")
    return path


def ago(minutes):
    return (datetime.now().astimezone() - timedelta(minutes=minutes)).isoformat()


@pytest.mark.parametrize("last, stalled", [
    (("user", [{"type": "tool_result", "tool_use_id": "t", "content": "ok"}]), True),  # the model never answered
    (("assistant", [{"type": "tool_use", "name": "Bash", "input": {"command": "pytest"}}]), False),  # 12 < 20 min
    (("assistant", [{"type": "text", "text": "waiting on my background run"}]), False),  # its turn ended
])
def test_watch_flags_silence_after_a_tool_result_but_not_a_running_tool_or_an_ended_turn(
        run_dir, tmp_path, capsys, last, stalled):
    sized_card(run_dir, "C1", "S", ["a.py"])
    run("dispatch", run_dir)
    watched_transcript(tmp_path / "p", "w1", "run1", "C1-build-1.md", [(ago(13), None, None), (ago(12), *last)])
    capsys.readouterr()
    run("watch", run_dir, "--once", "--silent", "10", "--projects-dir", tmp_path / "p")
    out = capsys.readouterr().out
    assert ("stall: C1 builder (implementer)" in out) == stalled, out


def test_watch_flags_a_tool_call_past_the_command_cap_and_a_dispatch_with_no_transcript(run_dir, tmp_path, capsys):
    sized_card(run_dir, "C1", "S", ["a.py"])
    sized_card(run_dir, "C2", "S", ["b.py"])
    run("dispatch", run_dir)
    watched_transcript(tmp_path / "p", "w1", "run1", "C1-build-1.md",
                       [(ago(30), None, None),
                        (ago(25), "assistant", [{"type": "tool_use", "name": "Bash", "input": {"command": "x"}}])])
    state = load(run_dir)
    for card in state["cards"]:
        card["since"] = ago(40)  # both dispatched 40 min ago
    (run_dir / "board.json").write_text(json.dumps(state), encoding="utf-8")
    for p in (tmp_path / "p").rglob("*.jsonl"):
        os.utime(p, None)
    capsys.readouterr()
    run("watch", run_dir, "--once", "--projects-dir", tmp_path / "p")
    out = capsys.readouterr().out
    assert "C1 builder (implementer): one tool call running for 25 min" in out
    assert "C2 builder: no agent transcript names C2-build-1.md" in out


def test_watch_ignores_a_transcript_of_another_run_or_dispatch(run_dir, tmp_path, capsys):
    sized_card(run_dir, "C1", "S", ["a.py"])
    run("dispatch", run_dir)
    stale = [(ago(13), None, None), (ago(12), "user", [{"type": "tool_result", "tool_use_id": "t", "content": "x"}])]
    watched_transcript(tmp_path / "p", "w1", "other-run", "C1-build-1.md", stale)
    watched_transcript(tmp_path / "p", "w2", "run1", "C1-build-7.md", stale)
    capsys.readouterr()
    run("watch", run_dir, "--once", "--projects-dir", tmp_path / "p")
    assert capsys.readouterr().out.strip() == "watch: no stalls"


def test_plan_shape_counts_the_widest_layer_and_the_longest_chain(run_dir, capsys):
    for cid, deps in (("C1", ()), ("C2", ()), ("C3", ("C1",)), ("C4", ("C3",))):
        add_card(run_dir, cid, [f"{cid}.py"], deps=deps)
    assert board.plan_shape(board.load(run_dir)) == (2, 3)
    capsys.readouterr()
    run("show", run_dir)
    assert "plan: width 2, depth 3\n" in capsys.readouterr().out


def test_returned_saved_acts_on_a_report_a_dead_session_already_saved(run_dir, tmp_path, capsys):
    sized_card(run_dir, "C1", "M", ["a.py"])
    run("dispatch", run_dir)
    make_transcript(tmp_path / "p", "b1", ["DONE built"], sub="b1")
    run("report", run_dir, "C1", "build", "--agent", "b1", "--projects-dir", tmp_path / "p")  # then the lead died
    capsys.readouterr()
    run("returned", run_dir, "C1", "--saved")
    out = capsys.readouterr().out
    assert card_of(run_dir, "C1")["status"] == "review" and len(card_of(run_dir, "C1")["reports"]) == 1
    assert [d["subagent_type"] for d in dispatches_of(out)] == ["code-reviewer"]
    with pytest.raises(SystemExit, match="there is no"):
        run("returned", run_dir, "C1", "--saved")  # no review-1 saved yet
    with pytest.raises(SystemExit, match="give exactly one of --agent, --saved"):
        run("returned", run_dir, "C1")


def test_brief_relaunches_the_reviewer_at_its_recorded_tier(gated, tmp_path, capsys):
    d = gated(0)
    returns(d, tmp_path / "p", "C1", "b1", "DONE", capsys)
    (d / "briefs" / "C1-review-1.md").unlink()
    run("brief", d, "C1")
    (again,) = dispatches_of(capsys.readouterr().out)
    assert (again["subagent_type"], again["model"], again["effort"]) == ("code-reviewer", "opus", "medium")
    assert (d / "briefs" / "C1-review-1.md").exists()


def test_show_says_a_one_lane_plan_is_likely_faster_without_construct(run_dir, capsys):
    add_card(run_dir, "C1", ["a.py"])
    add_card(run_dir, "C2", ["b.py"], deps=["C1"])
    capsys.readouterr()
    run("show", run_dir)
    assert "plan: width 1, depth 2 · one lane" in capsys.readouterr().out
