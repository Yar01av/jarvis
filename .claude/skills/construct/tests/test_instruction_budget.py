"""A ratchet against instruction creep, not a behaviour test: it fails when a skill file outgrows its budget.

The lead reads these files at every run, and the briefs go to every agent. If this fails, cut something first:
evidence and anecdotes belong in the project's planning notes, and a rule a tool enforces needs one line.
If the growth is worth it, raise the budget here and give the reason in a comment beside it.
"""
from pathlib import Path

import pytest

SKILLS = Path(__file__).resolve().parent.parent.parent
BUDGETS = {  # bytes, counted with LF line endings; set 2026-10-27 at the trimmed sizes plus about 500
    "construct/SKILL.md": 24_360,  # +600 on 2026-11-05: the single-lane route and lanes
    "construct/briefs.md": 10_967,  # +500 on 2026-11-05: re-review judges the fix; entry points map errors; realistic-input FAILs
    "construct/testing-practices.md": 9_400,
    "board/SKILL.md": 2_000,
}


@pytest.mark.parametrize("name", sorted(BUDGETS))
def test_skill_file_stays_within_its_budget(name):
    size = len((SKILLS / name).read_bytes().replace(b"\r\n", b"\n"))  # a CRLF checkout must not fail it
    assert size <= BUDGETS[name], (f"{name} is {size:,} bytes, over its {BUDGETS[name]:,} budget: cut first, or raise "
                                   f"the budget with a reason")
