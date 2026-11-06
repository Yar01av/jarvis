"""Review off the critical path: a build card may start while its build deps are in review."""
import pytest

from test_board import add_card, card_of, make_transcript, move, run, run_dir  # noqa: F401
from test_dispatch import dispatches_of, returns, sized_card


def test_a_build_card_starts_while_its_build_dep_is_in_review(run_dir, capsys):
    add_card(run_dir, "C1", ["a.py"])
    add_card(run_dir, "C2", ["b.py"], deps=["C1"])
    move(run_dir, "C1", "doing")
    with pytest.raises(SystemExit, match="waits on C1"):
        move(run_dir, "C2", "doing")  # a dep still building holds it back
    move(run_dir, "C1", "review")
    move(run_dir, "C2", "doing")
    assert card_of(run_dir, "C2")["status"] == "doing"


def test_a_question_card_waits_for_its_deps_to_be_done(run_dir):
    add_card(run_dir, "C1", ["a.py"])
    add_card(run_dir, "C2", deps=["C1"], kind="question")  # e.g. the integration review
    move(run_dir, "C1", "doing")
    move(run_dir, "C1", "review")
    with pytest.raises(SystemExit, match="waits on C1"):
        move(run_dir, "C2", "doing")


def test_a_dependent_still_waits_for_a_file_its_dep_holds_in_review(run_dir):
    add_card(run_dir, "C1", ["a.py"])
    add_card(run_dir, "C2", ["a.py"], deps=["C1"])
    move(run_dir, "C1", "doing")
    move(run_dir, "C1", "review")
    with pytest.raises(SystemExit, match="file a.py is in use by C1"):
        move(run_dir, "C2", "doing")


def test_returned_puts_the_dependent_in_flight_as_soon_as_its_dep_goes_to_review(run_dir, tmp_path, capsys):
    sized_card(run_dir, "C1", "M", ["a.py"])
    sized_card(run_dir, "C2", "S", ["b.py"], deps=["C1"])
    run("dispatch", run_dir)
    out = returns(run_dir, tmp_path / "p", "C1", "b1", "DONE", capsys)
    assert sorted(d["subagent_type"] for d in dispatches_of(out)) == ["code-reviewer", "implementer"]
    assert (card_of(run_dir, "C1")["status"], card_of(run_dir, "C2")["status"]) == ("review", "doing")


def test_a_fail_names_the_dependents_that_started_on_the_unreviewed_result(run_dir, tmp_path, capsys):
    sized_card(run_dir, "C1", "M", ["a.py"])
    sized_card(run_dir, "C2", "S", ["b.py"], deps=["C1"])
    sized_card(run_dir, "C3", "S", ["c.py"], deps=["C1"])
    run("dispatch", run_dir)
    returns(run_dir, tmp_path / "p", "C1", "b1", "DONE", capsys)  # C2 and C3 start alongside C1's review
    run("set", run_dir, "--limit", "2")
    move(run_dir, "C3", "todo")  # pretend C3 died and waits again
    out = returns(run_dir, tmp_path / "p", "C1", "r1", "FAIL\nwrong format", capsys)
    assert "started on C1's unreviewed result: C2 (doing)" in out
    assert "C3" not in out.split("started on")[1].split("\n")[0]
