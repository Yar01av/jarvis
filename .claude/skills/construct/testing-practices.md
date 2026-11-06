# Testing practices for construct cards

Read the sections your brief names.
- **§A** applies to every card that writes or changes tests.
- **§B** applies to cards that parse, decode, validate or normalize input, and only in a repo that already has a property-testing library.
- **§C** applies to any code that reads input it doesn't control.
- **§D** applies to every card that writes tests or checks.

> **Provenance.** Adapted excerpts: trimmed, examples rewritten in Python, lines conflicting with construct removed.
> - **§A** is from obra/superpowers, `skills/test-driven-development/writing-good-tests.md`, at commit `2ce8aa15d05bd57213e6f746f953aafb7ded7a8b`. MIT License, Copyright (c) 2025 Jesse Vincent. The permission notice: <https://github.com/obra/superpowers/blob/2ce8aa15d05bd57213e6f746f953aafb7ded7a8b/LICENSE>.
> - **§B** is from trailofbits/skills, `plugins/property-based-testing/skills/property-based-testing/` (`SKILL.md` and `references/generating.md`), at commit `196a9073ab10d35bacf111f945e02c00b2c6883a`. CC BY-SA 4.0, © Trail of Bits. This section is adapted and shared under the same licence.
> - **§C** and **§D** are our own, from our runs' lessons.
>
> Vendored 2026-10-26. Pinned: never refresh from upstream without reading the diff.

## §A. Every test names the break it catches and exercises the real thing

**Name the break first.** Before writing a test body, answer: *what production change would make this test fail, and is that change a bug or a decision?*
- **If you can't name one,** redesign the test around an observable behaviour.
- **If only intentional decisions can fail it** (a constant's value, exact wording, private structure), it's a change detector: it fires on redesign and sleeps through bugs. Test the behaviour that depends on the decision instead. Not `assert MAX_RETRIES == 5`, but "a failing call is retried 5 times and a 6th attempt never happens."
- **A pin test is not a behaviour test.** If your card adds a limit or a guard, test **both sides of the boundary**: just under it passes, at or over it is refused. Test the consumer-visible effect, not the constant.

**What counts as a red:** new tests fail on assertions against a signature-only skeleton, not on import. For a test-only card on working code, it's one named scratch mutant per guarded behaviour, each failing.

**Derive the expected values independently.** Use literals and hand-checked fixtures; table-driven tests with literal expected values are the preferred shape. An expectation computed by the code under test, or by its helpers, passes whatever that code does.

```python
# Mirror assertion: the same builder computes both sides, so it's always true
assert build_query(tag="urgent") == build_query(tag="urgent")
# Hand-derived literal
assert build_query(tag="urgent") == 'tag:"urgent"'
```

**Behaviour, not text.** A test asserting that a script, config or doc contains an exact line proves only that the source is the source. Run the thing against controlled inputs, and assert its outputs, side effects or exit codes.

**Your code, not the framework.** Test the contract your code makes at its boundaries: the payload you produce, the refusal you raise. Upstream mechanics are their maintainers' tests. If upstream behaviour surprised you, write one narrow characterization test that names the assumption.

**Exercise the real thing.**
- **Don't assert on a mock.** An assertion on a mock passes when the mock exists and says nothing about the component.
- **Mock at the right level.** Learn every side effect of the real method before replacing it, then mock only the slow or external part below what the test depends on.
- **Mirror the real data in full.** A mock response carries every documented field, not just the ones this test reads; otherwise integration breaks while the test passes.
- **Make doubles specific.** Assert the arguments and call counts when they're part of the contract, and give each branch (success, error, malformed) its own fixture.
- **A control must be able to fail.** A self-test or positive control that bypasses the code path it is meant to prove is vacuous. Run it once against a deliberately broken input, and see it fail.

**The mutation check, before you report DONE.** Mentally mutate the production code. At least one test must fail for each realistic mutation:
- a wrong constant or argument, `>=` vs `>`, an off-by-one;
- a wrong branch handler;
- a missing state change or side effect;
- an empty or default return;
- missing validation for zero, empty, `None`, unauthorized or malformed input.

A mutation that nothing catches marks the behaviour as unprotected. Fix the test, or say in your report which mutation stays uncaught and why.

**Warning signs:**
- the setup and the assertion share the same object;
- expected values hidden behind loops, builders or helpers;
- a test that fails only through a crash;
- a test that fails on every intentional change but never on accidental breakage;
- a test that greps source text;
- a test that only exists for coverage;
- mock setup that is more than half the test.

## §B. Property-based tests for parsers, decoders and validators

Use these where the code has an algebraic shape. Code without one gets example tests, and saying so is a valid outcome.

| Property | Formula | Where |
|---|---|---|
| Roundtrip | `decode(encode(x)) == x` | serializers, conversion pairs |
| Oracle | `new(x) == reference(x)` | a re-implementation, a pre-scan that must agree with the real parser |
| Idempotence | `f(f(x)) == f(x)` | normalizers, formatting |
| Invariant | holds before and after | any transformation |
| Easy to verify | `is_sorted(sort(x))` | a cheap checker for complex output |

Assert the strongest property the code supports. In order from weakest to strongest: no crash, type preservation, invariant, idempotence, roundtrip or oracle.

**The two ways a property test asserts nothing:**
- **A tautology:** `assert add(a, b) == a + b` restates the implementation. Pick a property that constrains the function without recomputing it.
- **Vacuity:** an `assume()` that filters out nearly every input passes without exercising anything. Push the constraints into the strategy instead (`st.integers(min_value=1)`, `st.builds`, `st.composite`), and keep `assume()` for relations between already-generated values.

**The error-path contract, the most useful one for parsers of untrusted input.** Run `st.binary()` (or a structured strategy) against the decoder, and catch **only** its documented exception, so that everything else fails the test. The contract is: "raises `MailUnreadable` (or whatever the decoder's own error is) or succeeds, never `IndexError`, `AttributeError`, `RecursionError`, and never hangs."

```python
@given(st.binary(max_size=4096))
@settings(max_examples=200, deadline=None)
def test_reader_raises_only_its_own_error(data):
    try:
        read_mail(data)
    except MailUnreadable:
        pass
```

**Mechanics:**
- Pin the edge cases you already know about with `@example`: empty, a single element, all duplicates, zero, negative, the maximum.
- Set `deadline=None` for anything doing real work, so that a slow machine doesn't produce flaky failures.
- Keep `max_examples` modest in the suite (about 100–200).
- Never add a property-testing library to a repo that lacks one. That's the user's call.

## §C. Untrusted input: the classes past runs bounced on

When your code reads input it doesn't control (mail, archives, documents, anything from a caller), these checks are part of the done-when.
- **A closed error mapping.** Every failure leaves through the module's own error type. Add a catch-all at the boundary that maps any other exception to it, plus a test that would see an escaping `IndexError`, `AttributeError` or `RecursionError`. Its test double raises more than one unrelated type (e.g. `OSError` and a plain `Exception` subclass), so a narrower `except` can't pass. Use §B's error-path contract where the repo has Hypothesis.
- **Bounded on every count dimension.** For each thing an input can multiply (parts, headers, entries, nesting depth, attachments, name lengths), write a doubling test: 2× the input must take at most about 2–3× the time. Cap the counts **before** the expensive work, not after it.
- **When the parser isn't ours** (stdlib `email`, `olefile`, …), its worst case is its own. Bound it from outside with a hard limit, such as a time or memory cap in a child process, rather than with a pre-scan whose rules differ from the parser's.
- **Nothing from inside the input reaches results, logs or history** unless the spec says so: no member names, no paths, no header values. Refer to things by position.

## §D. Checks our runs bounced on

- **Changing a shared closed list** (a `Literal`, enum, type set, reason table)? Grep its readers, run their tests too, and report each.
- **An artefact a tool loads** (manifest, interface yaml, config) is checked through that tool's own reader or validator, not by substrings alone.
- **External API error bodies** follow the endpoint's reference schema, not a guide's example; never JSON-parse one unconditionally.
- **A check script gives "broken" its own exit code**, so a crash never reads as its verdict.
