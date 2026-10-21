# `/build` — phase bodies

The operational detail for phases 0–13. `SKILL.md` holds what applies *throughout* a run
(orchestrator rules, checkpoints, the fix protocol, model tiering) plus the phase index; this
file holds what each phase actually does.

**Read the section for a phase before starting it.** The index line in `SKILL.md` names the
phase, it does not specify it — a phase run from the index alone will miss its gate, its
dispatch contract, or its close-out.

Why these are separate files: an invoked skill's body is re-attached after auto-compaction only
up to the first ~5,000 tokens. At 900 lines this document exceeded that by ~3x, so everything
past roughly phase 1 was silently dropped from a long run — precisely the runs that reach the
later phases. `SKILL.md` is kept under that budget so the always-applicable rules survive; these
bodies are re-read on demand instead, which costs one tool call and cannot be silently evicted.

---

## 0. Setup (orchestrator)

- Derive a short `<feature-slug>` from the arguments.
- **The repo you were invoked from is the home; building outside it needs
  express permission.** A session is scoped to one repo: subagents inherit
  that cwd, `/commit` runs there, worktrees branch there, recovery diffs read
  there. Holding another repo implicitly across twelve phases and a dozen
  delegations fails: an un-briefed librarian bootstraps the wrong `docs/` tree,
  a recovery revert wipes the wrong work. So an outside repo is never implicit:
  it is named by `--repo` or by a proposal the user accepts, and then runs under
  the mechanics in **Building in an outside repo** below. Without either, build in
  the home. When the deliverable plainly belongs elsewhere, don't refuse and don't
  quietly build in the home: propose the outside repo with your reason.
- If `docs/designs/<feature-slug>.md` exists **in the working tree or on
  `feature/<slug>`** — a consented-checkpoint run commits the doc there and
  leaves the tree clean, so from `main` it's invisible; check
  `git show feature/<slug>:docs/designs/<feature-slug>.md` before
  concluding the run is fresh (an error there just means it isn't on that
  branch): make sure you're on
  `feature/<slug>` first (`git checkout`; recreate the branch if it's gone),
  then read the checklist **and the state sections** (`## Experiments`, open
  unknowns, `## User testing`, the close-out ledger including its
  checkpoint-consent header) — the boxes alone don't carry loop counters,
  checkpoint consent, or deferred close-out work. Tell the user where you're
  picking up. A fresh session typically starts on main — resuming without the
  checkout writes feature code to the wrong branch. **With outside repos the
  checkout happens in each outside repo, and the home's branch is left alone
  unless the deliverable changes the home** (see below).
- Otherwise (a genuinely fresh run): **if the tree is dirty, stop and confirm
  before branching** (an unbranched home in outside-repo mode is exempt, per the
  section below; each outside repo gets the same check) — a branch cut over someone else's uncommitted work carries
  it along, and the checkpoint chain then commits it as yours. Then create
  `feature/<slug>` from the current HEAD (in the home only when the deliverable
  changes the home; outside repos get theirs per the section below)
  and seed the design doc with this checklist (applying
  `--from`, below, before you start work):

  ```markdown
  # <Feature name>

  ## Phases
  <!-- [ ] todo · [x] done · [-] skipped (--from) -->
  - [ ] 1 Research
  - [ ] 2 Go/no-go
  - [ ] 3 Requirements (grill)
  - [ ] 4 Architecture (incl. experiments + validation contract)
  - [ ] 5 Plan sign-off
  - [ ] 6 Validation red
  - [ ] 7 Build green
  - [ ] 8 Documentation
  - [ ] 9 Review passed
  - [ ] 10 Smoke test
  - [ ] 11 User testing
  - [ ] 12 Committed
  - [ ] 13 Kit retrospective

  ## Close-out ledger
  <!-- Header: `Checkpoints: yes|no · base: <git rev-parse HEAD at phase 0>`,
       followed by `dirty-at-start:` — the `git status --short` paths that were
       already modified/untracked when the run began. That inventory is the
       durable form of the phase-0 dirty-tree check (which otherwise leaves no
       artifact): any later checkpoint whose `git diff --cached --stat` touches a
       path on it is a slip, and any file on it is someone else's uncommitted work
       — never overwrite one to fix a problem, ask first.
       Then an append-only event log, one line each, in order:
       - checkpoint: <SHA> — <what>
       - code-change: <which agent / what>  (any dispatch that edits
         code or docs — anything the reviewers must see; the design doc
         itself is exempt, they receive it alongside the diff)
       - close-out: <agents> — scope full|delta — deferred: <what>
         (scope names the pass's charter, never its diff size: phase-8/9
         and ship-gate passes are `full` — a phase-9 re-review included —
         phase-10/11 interim reviews are `delta`. No SHA is written on this
         line — it can only ever be a diff base or a target, and both have
         already been typed wrong in a past run. The tree a close-out covers
         is the `checkpoint:` line that immediately follows it in the ledger
         — checkpoint-after-close-out is already the run's own convention
         (SKILL.md's "Checkpoints"), so the position is mechanical
         (`git rev-parse` at actual commit time), never freehand-typed or
         copied from a diff-base string an agent was handed. A close-out
         with no following checkpoint line yet is not closed for gate
         purposes — don't infer one.)
       Phase 12 reads THIS, not your memory of dispatch order. Validate before
       reasoning: every SHA named anywhere in the ledger must appear in
       `git log <base>..HEAD` — one absent, or equal to `base` itself, is a
       gate failure for that line's agent, not an ordering input.
       With outside repos: `base: none (home unbranched, on <branch>)` when the
       home isn't branched, one `Repo …` header line each, events tagged with
       their repo, SHAs validated per repo — see "Building in an outside repo". -->
  ```

- **Fresh runs only:** record the run base (`git rev-parse HEAD`) in the
  ledger header (an unbranched home records `base: none …` instead, plus a
  `Repo …` line per outside repo), ask the checkpoint-consent question (see **Checkpoints** in `SKILL.md`), and record the answer there too; on consent, make the first
  `wip(<slug>): seed design doc` commit now (not when the home stays unbranched
  in outside-repo mode: the doc is then never committed during the run). A resumed run **reads** the
  recorded answer instead of re-asking — ask only if the header is absent,
  and on that resume-ask create the header then, with base := current HEAD.

- **Then (both branches), begin work at the first `[ ]` phase in the
  checklist.** This is the single control rule that routes every run — fresh,
  resumed, or skipped. Treat `[x]` (done) and `[-]` (skipped via `--from`)
  **identically: already handled — never execute or resume into them.** With
  no `--from`, the first `[ ]` is phase 1, so a normal run starts at Research.
  With `--from 4`, phases 1-3 are `[-]`, so you start at phase 4. Announce the
  starting phase to the user.

### Skipping the front phases (`--from`)

For a tight feature that needs little or no prior research, the user may pass
`--from <phase>` (a number `1-13` or a phase name like `plan`/`planner`) to
start partway in. **No new control path** — at seed time, mark every phase
*before* the target as `[-]` (skipped — never `[x]`, which would claim work
that never happened). The "begin at the first `[ ]` phase" rule above then
lands you on the target. Note the skip in the design doc so the record stays
truthful.

Guardrails:

- **Only the front phases (1-3) are freely skippable.** The validate → build →
  review spine (6+) is mandatory — skip ideation if you must, never skip review.
  Straight to 4 is the common case. This holds **whatever the deliverable is**:
  "there are no tests here" is never a reason to skip 6–9; the phase-4 contract
  defines what red / green / run mean for it.
- **No fake sections.** Don't fabricate a Requirements or Research section for a
  skipped phase; pass the planner the description directly and have it surface
  gaps as **Open unknowns**. The phase-5 gate is the safety net.
- If a later phase genuinely needs a skipped phase's output, say so and offer to
  run it rather than guessing.

### Stopping early (`--to`)

`--to <phase>` runs the pipeline through the target phase and then **stops**
instead of continuing to commit/retrospective — e.g. `--to 5` for a plan-only
run (architecture + sign-off, no code), or `--to plan`. Combine with `--from`
for a slice (`--from 4 --to 5`). On reaching the target, check its box, tell
the user where you stopped and how to resume (`/build <slug>` picks up
at the next unchecked phase), and stop — do not run later phases. `--to` may
land before the validate/build spine (a plan-only run is fine); it just defers the
spine to a later resume, it never skips it. A stopped run leaves a
consented checkpoint chain live — handle it per **Checkpoints** in `SKILL.md`.

### Building in an outside repo (`--repo`)

The repo the session runs in is the **home**: the knowledge store and the
preferred place for deliverables. It always holds the design doc, the close-out
ledger and the `docs/solutions/` lessons. The deliverable's code or files go into
another repo, an **outside repo**, only with express permission, given one of two
ways:

- **`--repo <absolute path>`** in the arguments, once per repo; or
- **a proposal the user accepts.** When the work plainly belongs elsewhere (the
  code lives in another repo, or it is a standalone project), propose it at
  whichever phase shows it (most often 0 or 4): a gate question naming the
  absolute path and your reason, against the alternatives (the home, or a repo
  already in the run). Only an explicit yes to that path counts; a path mentioned
  in a brief or suggested by an agent is context, not permission. For a project
  that doesn't exist yet, the proposal includes creating it (`git init -b main`,
  one real commit); starting a separate session there instead stays an option to
  offer.

A permission once recorded in the ledger holds for the whole run, resumes
included; `--repo` needn't be passed again.

**Setup per outside repo, before anything writes to it** (at phase 0, or the
moment a proposal is accepted):

1. It must be a git repo with a real commit. No git, or an unborn HEAD: ask to
   make a local baseline commit (nothing pushed), showing the `git status --short`
   it would take in, or stop. The baseline is the pre-run state, so it takes the
   files as they are, and it is never `--allow-empty` unless the directory is
   empty. Run `/commit`'s hygiene checks over that file list first (no secrets,
   no `.env`, no build output or large binaries); a repo without a `.gitignore`
   gets one proposed before the commit.
2. A dirty tree (after any baseline): stop and confirm, as for the home in a
   fresh run. Record its `git status --short` as that repo's `dirty-at-start`.
3. Create `feature/<slug>` there from its current HEAD and record that HEAD as
   the repo's base.
4. Make it a working directory of the session (`/add-dir <path>`, or
   `--add-dir` at launch), or every write there prompts. This lasts one session:
   redo it on every resume.
5. Note its conventions entry point: its `docs/INDEX.md` if it keeps one, else
   `AGENTS.md`, `CLAUDE.md` or `README.md`.

The ledger header gains one line per outside repo:
`Repo <name>: <abs path> · branch feature/<slug> · base <SHA> · granted: --repo | proposal, phase N · dirty-at-start: <paths>`.
The checkpoint-consent answer covers every repo of the run, including one added
later.

**The home in this mode.** If the deliverable changes nothing in the home beyond
the design doc and lessons, the home is **neither branched nor checkpointed**:
those files are written in place on whatever branch the home is on (often
another piece of work's). The ledger header keeps its usual first line, with
`base: none (home unbranched, on <branch>)`, and its `dirty-at-start:` as usual;
the fresh-run dirty-tree stop doesn't apply to it, since nothing is branched or
committed there. Two consequences to tell the user at phase 0: the design doc
is untracked on that branch (a `git clean` or `git stash -u` in that other work
takes it with it), and a lesson that would edit a file on the home's
`dirty-at-start` waits for their OK. Ask it with its cost: the edit lands in that
other work's uncommitted file and rides along in its next commit. A refusal is a
deferral recorded in the design doc, not a phase-8 blocker. If a later phase
finds the deliverable must change the home after all, branch the home then: ask
which ref to cut from (its default branch, or the current HEAD, which may carry
another run's wip commits), the dirty-tree stop applies at that moment, and the
header's `base:` gets that ref's SHA.

**On resume**, check out `feature/<slug>` in each outside repo; if the branch is
gone, recreate it from that repo's **last logged checkpoint** (its base only when
none was logged), never from the base when checkpoints exist, or the chain the
ledger names is lost. An outside repo that is dirty on resume most likely holds
this run's own half-done work: inspect it per the atomicity rule in `SKILL.md`
before continuing. **Never switch the home's branch** while it is unbranched; the
design doc is in its working tree.

**The translation rule: everything about a repo runs in that repo.** Every git
step this pipeline names (the checkpoint commits and the `git diff --cached
--stat` before each, recovery diffs, the pre-existing A/B against `base`, review
diff bases, ledger SHA validation, phase 12's chain check and squash) runs **per
repo, against that repo's own base and chain**, as `git -C "<abs path>" …`. So
does every other repo-relative command: the phase-7 STUB grep
(`grep -rn 'STUB(<slug>)' "<abs path>/<source dirs>"`), a docs lint, test runs,
the smoke run's processes (`cd "<abs path>" && …` in one Bash call). A grep or
lint run from the home over outside code matches nothing and reads as a pass,
which is the no-op-gate trap phase 7 warns about. In the ledger:

- `code-change: <repo> — <agent / what>`; a dispatch touching two repos logs a
  line per repo. The home's lessons count too: `code-change: home — <path>`.
- `checkpoint: <repo>@<SHA> — <what>`; a checkpoint moment commits in each
  outside repo that changed since the last one and logs a line each.
- A close-out is followed by one checkpoint line per outside repo changed since
  the previous checkpoint. Phase 12's gate reads them per repo: for every outside
  repo the run changed, each gate agent's last `full` pass must be followed by
  that repo's checkpoint, and that SHA must postdate the checkpoint after the
  repo's last `code-change`, by `git -C <path> log <base>..HEAD`. A repo untouched
  since the agent's pass is still covered by its earlier line. An unbranched home
  has no checkpoints: its files are covered when each reviewer's last `full`
  pass comes after the last `code-change: home` line, in ledger order. The
  librarian is exempt for the home (it leaves the home's docs alone, per *Docs*
  below), so lessons written after its pass don't reopen its gate.

**Briefs for outside-repo work.** Subagents start in the home and load the
home's `CLAUDE.md` and `ProjectCLAUDE.md`, never the outside repo's, so the brief
has to carry what they would miss. Every dispatch that touches an outside repo,
reviewers and the librarian included, names:

- the repo's absolute path and the absolute paths in scope (for an isolated
  spike, the worktree directory below as the only place it may edit);
- `git -C "<path>"` for any git, and how to run its checks there
  (`cd "<path>" && <command>` in one Bash call);
- for a reviewer, the per-repo diffs (`git -C "<path>" diff <base or last
  reviewed checkpoint>`) and the home's lesson files by path;
- the repo's conventions entry point, and that **for code in that repo it
  replaces the home's project rules**: the home's code conventions and its
  docs-first `docs/INDEX.md` traversal apply to the home's own files only. Where
  the repo's conventions are silent, follow the surrounding code.

**Isolation.** `isolation: worktree` only ever makes a worktree of the home, so
for outside-repo code it isolates nothing: an experimenter briefed with an
outside path edits the live tree, and "spike code never lands on the feature
branch" breaks silently. For an isolated spike or unit there, run
`git -C "<path>" worktree add --detach "<dir in your scratchpad>" <SHA>`
yourself, with the repo's last checkpoint as the SHA, or its base before the
first one or when checkpoints were declined (detached: `feature/<slug>` is
already checked out in the repo's main tree, so naming the branch fails), name that directory in the brief, and remove
it afterwards (`git -C "<path>" worktree remove "<dir>"`). Like any worktree it
sees committed state only. Fan-out inside an outside repo: disjoint file sets, or
sequential.

**Docs.** Code-derived docs follow the outside repo's own conventions, in that
repo. The librarian runs `/sync-docs` there only if the repo already keeps a kit
`docs/INDEX.md` tree, and never bootstraps one. While the home is unbranched, the
librarian leaves the home's `docs/` tree alone: no code there changed, and its
files may be another work stream's uncommitted edits. The design doc and
`docs/solutions/` lessons stay in the home; the home's docs lint covers the
home's files.

**Phase 12.** Reconcile each outside repo's chain as phase 12 describes
(squash-or-keep is asked once for the run, and the chain check runs in every
outside repo), then `/commit --repo "<abs path>"` per outside repo. The home's design doc
and lessons stay **uncommitted by default**, and you say so; commit them only on
a branch the user names. Nothing is pushed and no PR is opened in any repo: a
permission deny on `git push` doesn't match `git -C <path> push`, so this rule is
the guard.

## 1. Research (`researcher` agent)

Delegate: assess whether this should be built at all (libraries, OSS, prior
art), a light technical overview, and known pitfalls. Have the agent read
`docs/solutions/INDEX.md` first (if it exists) — earlier runs' captured lessons
may already answer a question or flag a dead-end. It returns findings with
sources, a build / buy / drop recommendation, and open questions split into
*decisions for the human* (feed the grill) and *empirical uncertainties* (which
must not get lost between phases). Require each uncertainty as a **directly
dispatchable one-question brief**: the question, the smallest spike that yields
a verdict, and enough context to run without this conversation — phase 3
dispatches the grill-independent ones verbatim, so a brief needing follow-up
wastes the slot. Spike **now** when the build/buy/drop call or the grill would
benefit; the rest carry to planning. Write it into `## Research`.

## 2. Go/no-go (orchestrator, gate)

Present the recommendation to the user: **build / use library X / drop**.
Don't carry a guess into this gate: if the recommendation hinges on an
unverified claim, run the experiment first. Record the decision in the
design doc. On "drop", stop. On "library",
redirect: the remaining phases apply to the integration, not a from-scratch
build.

## 3. Requirements (orchestrator, interactive)

**First, use the grill's dead time: dispatch the independent spikes now.** The
interview is the longest wall-clock stretch of the run and every agent is idle
through it. Partition phase 1's uncertainties: those **independent of grill
outcomes and self-contained** get dispatched before the first question — present
the list with a per-experiment tier recommendation ("while I grill you, these
spike in the background — OK?"), then one `experimenter` each, background,
`isolation: worktree` (mind the committed-state caveat above; a spike on an
outside repo's code is isolated per §0 *Isolation* instead). Write verdicts
into `## Experiments` as they land. Uncertainties the grill might reshape stay
undispatched — spiking against requirements that are about to move is the one
waste case, and the user confirming the list bounds it.

**Assemble the whole question set before asking anything, then ask in dependency
waves — `/grill-me`'s "one at a time" does not apply inside `/build`.** In a chat
interview a question costs a sentence; here it costs a *scheduling event*, and the
user may be hours or days away. Draft every question first, mark what each depends
on, and put all questions whose *option sets* don't change based on another
answer into one `AskUserQuestion` call (the tool takes four). Only a genuine
dependency breaks a wave — "concurrent or sequential?" must precede "what bounds
the concurrency?", but "what happens when a run raises", "does the dataset
re-fetch matter" and "warn on sampling?" are one wave. **Never emit a question
the moment you think of it**: interleaving questions with your own work turns a
15-minute grill into a three-day one at identical information yield. And **do not
start a grill you cannot finish** — if the set can't be completed in one sitting,
say so and pick up the whole remainder in one block, not question by question.

**Before asking, write the recommended option's description — then check whether
you have written a finding instead of a question.** If it reads *"X already does
this"* / *"mirrors Y"* / *"zero new code"* **and** nothing the user perceives
changes either way, it is a finding: record it, say what you decided, move on.
**Both prongs are required.** "Already true of the code" alone over-fires — a
degenerate path whose *visible output* changes is a real question even when the
status quo is perfectly determinable, and those are exactly the ones users
override. A question whose answer you have already written into your own option
text spends a scheduling event to buy nothing.

**A cost claim in an option description is a claim about code.** Any assertion of
scope, effort, line count, file count, or "larger/smaller than X" must cite the
files it rests on (`file.py:line`) or be labelled explicitly as an unverified
estimate — the same burden `SKILL.md` puts on dispatch briefs. An uncited "this
would mean touching A and B and a mechanism that doesn't exist" is how a gate
talks the user out of the option that was actually correct.

Invoke `/grill-me`, seeded with the research section and its *decisions for
the human* (the empirical uncertainties are not grill material — they wait
for the experimenter or are already spiking in the background).

**Every item on research's "decisions for the human" list gets an explicit
disposition before this phase closes** — asked, resolved by a code read (say
which file), or deferred with a reason. None may silently disappear; the same
rule the planner's unknowns get in phase 4. Record the dispositions in
`## Requirements` alongside the decisions, including the ones you answered
yourself. An item that says **"confirm against a concrete sample"** is not
discharged by a prose answer — it is the concretizing rule firing by name, and
skipping it is how a question resurfaces at phase 11 as a user-visible defect.

Distill the interview into `## Requirements`: scope,
acceptance criteria, edge cases, non-goals. **When the grill settles an
interface's shape**, settle it against a concrete instantiation per the
concretizing rule at the top; an `AskUserQuestion` `preview` is usually
the cheapest inline form.

## 4. Architecture ↔ experimentation loop

- **Plan** (`planner` agent): the delegation prompt spells out the
  architecture-doc format, *overriding the planner's default*, and that format
  follows the deliverable's medium — executable gets modules/methods with public
  vs internal marked, data flow, Mermaid where it helps; other media get what
  fits (a section outline with sources for a doc or deck, schema + provenance for
  data), since a planner fabricating modules for a PDF is the same over-heavy
  failure the contract below prevents. **If units may be built in parallel, the
  plan must name each one's file set** — that list is what makes disjointness
  checkable at phase 7. Every plan ends with the **validation contract** (below)
  and **Open unknowns** — claims it rests on that need empirical verification.
  Pass the research phase's *empirical uncertainties* **and the verdicts
  already landed in `## Experiments`** (the phase-3 background spikes) into
  this prompt and require a disposition for each: resolved with cited
  evidence, needs a user decision (→ plan gate), or open unknown
  (→ experiment). None may silently disappear. With the grill-time spikes
  in, the first plan often starts with its biggest unknowns already
  answered instead of opening the loop cold.
- **Skepticism check**: a first-cycle plan with zero open unknowns on a
  non-trivial feature is a smell, not a green light — especially when
  research flagged uncertainties. Challenge it once ("which of these claims
  have you actually verified?") before accepting. Bias toward
  experimenting: an hour of spiking is cheaper than a wrong architecture.
- **Experiment** (`experimenter` agent, one per unknown, parallel when
  independent, `isolation: worktree`, or per §0 *Isolation* for an outside
  repo's code): each agent gets ONE question and
  answers it with the smallest spike that yields a verdict. Spike code never
  lands on the feature branch; you write the returned verdicts + evidence
  into `## Experiments`.
- **Loop**: re-run the planner with the experiment results. Cycle
  plan ↔ experiment as often as needed; summarize each cycle to the user.
  Unknowns that need a *user decision* rather than an experiment go to the
  plan gate instead.
- Exit when the plan has no blocking unknowns. Write the final architecture
  into `## Architecture`.

### The validation contract (planner output — phase 5 gates it)

The plan states not only what gets built but how it will be **proven** —
TDD's discipline shed of its literal form: red (phase 6) → build to green
(phase 7) → review (phase 9), whatever the medium. The
contract is authored here, before the gate, because an over-heavy scheme
originates in the plan's mandated shape (a 25-test plan for a 20-page PDF
traced to a format clause demanding a test list; by phase 6, the gate that
could have struck it had already passed). Plain markdown bullets under
`## Deliverables` in the design doc — resist YAML and schemas. Four fields:

- **medium** — what the deliverable is in validation terms (executable,
  rendered pages, a live UI, a registered workflow, content, data), plus
  how it ships: long-lived vs run-to-completion. Phases 10–11 key the
  hand-over on that tag; a change inside an existing app tags the
  vehicle it ships in.
- **red** — the observable failure to see *before* building; concrete,
  never "tests fail". Two kinds, split by one question — *can the check
  run before the thing exists?* **Observable-first** (yes — typically
  executable: literal TDD) and **authored-first** (no — rendered or
  assembled media, content, data: the rubric is authored here, gated at
  5, and its first run against the first draft *is* the red).
- **checked by** — the check and who runs it; a tool plus its operating
  agent counts (`pytest — test-writer authors the red`). Tests are the
  deliverable's red and check, never a deliverable of their own.
- **review** — who reviews the result once green (phase 9 hosts it),
  named now so a check is never mistaken for the review.

**House shapes are the project's, not the run's.** If ProjectCLAUDE.md
has an `## Artifact shapes` section, a deliverable whose medium is
listed there inherits that shape: it constrains the plan and seeds the
red/rubric, so a shape violation fails a check instead of surfacing as
taste at review. No section, or no line for this medium — author freely.

```markdown
## Deliverables
- API rate-limiter — medium: executable (long-lived: ships in the running service)
  - red: pytest — 429 past the limit, pass under it — observed failing first
  - checked by: pytest — test-writer authors the red
  - review: code-reviewer (phase 9)
```

**One deliverable, one contract — but a contract may owe more than one
check.** When parts of the deliverable are validated differently (a PDF
read by an agent, built by a script exercised by tests), name **each** of
those checks here — extra `red` / `checked by` lines in the same contract,
never extra nodes, orderings or loops. They are **additive: a
whole-artifact check never discharges a part's.** In the run that forced
this rule, a rendered PDF's visual review displaced the code review, so
the build script was reviewed by nobody and shipped a bug a rendered page
cannot show by construction. One medium throughout — a couple of Python
modules — means one check and no fuss. (A large build whose independent
parts should run *concurrently* is a different problem, parked in the
experimental `/tree-build` and unvalidated; here siblings build
sequentially.)

## 5. Plan sign-off (orchestrator, gate)

The user reviews the architecture before any red is built. Catching a
wrong abstraction here is 10x cheaper than after red→green. **The validation
contract is a gate artifact in its own right**: present the contract
with its checks verbatim, not summarized — the user resizes or
strikes checks here, while a wrong-sized scheme still costs nothing. **If the plan
introduces or changes a stakeholder-facing interface**, the sign-off
artifact includes its concrete instantiation (per the concretizing rule
at the top), not just the module/data diagram. **Any invariant the plan calls
load-bearing must land as a test or a code guard, never as a note for the
reviewer** — a reviewer is a one-run guard. **And if the gate adds scope,
restate the size estimate in the same edit**: otherwise the overshoot gets
attributed at review time to whatever is most visible rather than measured.
Apply revisions
(re-entering the loop above if they're structural) until signed off. Record
the sign-off and the revisions applied in the design doc — one or two lines,
decision-grade, never a transcript.

## 6. Validation red (per the phase-4 contract)

The contract — authored at 4, signed at 5 — already says what red means
and which kind this deliverable's is (a check that "runs" pre-existence
but can only fail for the wrong reason — a grep over files that don't
exist yet — counts as authored-first):

- **Observable-first**: dispatch the *checked by* agent now and require
  actual observed output in the report — spot-check it; a red asserted
  rather than observed proves nothing. Tests fail **for the right reason**
  (missing implementation, not typos/import errors); a toolchain-validated
  artifact's pre-change run fails for real (schema rejection, unresolved
  reference, missing output key — the concrete toolchain is
  project-specific; it lives in ProjectCLAUDE.md, not here).
- **Authored-first**: nothing can run yet. Confirm the rubric stands
  frozen in the signed contract; its first run — at phase 7, against the
  first draft — is the red, and its findings are worked off before green.
  Not a deferral and not an exemption: fixed before building, run at the
  earliest possible moment, never saved for the end.

Check the box on the red observed (or the rubric confirmed — say which),
then with checkpoint consent commit `wip(<slug>): validation red` and log
the SHA in the ledger.

*(Applies wherever the contract has an executable check — a rendered
deliverable built by a tested script included; skip only when it has none.)*
When a planned public symbol doesn't exist yet, have the test-writer add a
**minimal stub** (signature or dataclass shape only, a body that raises or
returns nothing) marked `# STUB(<feature-slug>):`, so the red is an assertion
failure rather than an import error. Two guards: the stub must still leave the
test **failing** (one that accidentally satisfies it makes the red fake), and it
stays minimal — the moment a stub grows logic, the test-writer has started
implementing. These markers are what the phase-7 sweep clears.

## 7. Build green

Dispatch `implementer` for an executable deliverable, the roster
specialist that fits for other media (per the roster note in `SKILL.md`), and
`general-purpose` when none fits — a missing specialist changes the
builder, never skips the phase. The dispatch gets the design doc plus
which checks it must turn green and runs the check to green itself; you
log the `code-change` ledger event per dispatch (the phase-12 ship gate
reads these — agents never write the design doc, per `SKILL.md`). For
an authored-first contract, the rubric's first run happens here against
the first draft — its findings are the red, worked off until the check
passes. In the delegation prompt, tell the implementer to **remove each
`# STUB(<feature-slug>):` marker as it fills that symbol in**, and to
**delete — not leave defined — any planned symbol it diverges from and no
longer uses** (a dataclass/function the doc named but the implementation
routed around). A wrong check comes back to you as a finding — never
weakened silently. Architecture deviations
get written back to the design doc; it must end truthful. With checkpoint
consent, commit `wip(<slug>): <module> green` as each module or draft
lands and log
each SHA in the ledger — those SHAs are what the atomicity
recovery diffs against (delta reviews diff from batch-close lines, per
phases 9/11).

Implementers run at **hands (`sonnet`)** — safe here because the plan and the
observed reds already hold the judgment (CLAUDE.md → Model tiering). **Escalation:**
an implementer that returns blocked — can't get its checks green, flags the
design doc as ambiguous, or hits repeated tool failures — is re-dispatched for
*that unit* one rung up the ladder (ceiling-exempt, one attempt per rung —
see Model tiering). Step up, don't thrash; a unit still blocked after
`fable` is a plan problem — kick it back to the plan gate.

**Sequential by default, because implementers share one working tree** —
concurrent units race (half-written files, one agent's green invalidated by
another's edit, collisions on `__init__`/registry/conftest) and "independent"
units routinely still touch those files.

**Fanning out hands work (opt-in: `ultracode` on, or the user's explicit OK —
never unilaterally, a Workflow can spawn many agents).** With several genuinely
independent units you may author a Workflow script running one hands-tier agent
per unit. **You own the collisions, and you own them before dispatch:** the plan
names each unit's file set, you fan out only where those sets are provably
disjoint, and every shared seam — registry, `__init__`, lockfile, generated
index, the test harness's own fixtures — belongs to *your* assembly step, never
to a child. Where disjointness can't be established, either give each unit
`isolation: worktree` and merge at assembly (a worktree sees only *committed*
state, so checkpoint first; in an outside repo, the worktree you add per §0
*Isolation*) or keep those units sequential. As each unit closes,
re-run its check against the shared tree before its checkpoint — a sibling may
have landed meanwhile — and stage only its own paths. **Don't fan out one or two
units, or units that mostly touch the same files**: coordination then costs more
than the wall-clock it buys, and determinism, not speed, is the reason to script
it at all. Set `model: 'sonnet'` on every `agent()` call explicitly —
un-annotated calls inherit the session model and the hands saving evaporates.

**When work does fan out, mirror it in the task panel**: one task per unit,
`blockedBy` for real dependencies, flipped as each starts and closes, so the
user can see what is running concurrently. The design doc's phase checklist
stays the durable record — don't keep two trackers of the same thing; the panel
exists for live visibility of concurrent work, which the checklist can't show.

**Before you check this box, exercise the interface once per state its contract
declares** — every exit code including the "cannot determine" one, the error
envelope, the rejection message — and paste the observed output into the design
doc. Phase 5 signed off an *instantiation*; this is where you confirm the built
thing matches it in the states nobody previewed. A run that skipped this spent
both phase-9 fix rounds on comment hygiene while three behavioural defects sat
in its documented failure paths, unexecuted until phase 10 — and fixing them
then reopened the phase-12 ship gate. **Then re-read every failure message the
red left behind**: it must describe the violated expectation, not the
implementation that violated it, or it hands a future debugger a confident
wrong diagnosis.

**Two sweeps that cost a line each and otherwise become review findings.**
(1) **Red-phase language**: any docstring, comment or assertion message written
at phase 6 that describes the pre-implementation state ("today this prints X",
"`None` until that widget exists") is false now, and reads to the next person as
a live defect in code its own test is passing against. (2) **Orphaned helpers**:
for every helper whose call sites this phase edited, confirm it still has one —
the STUB grep finds scaffolding that was *added*, never a helper stranded when
its last caller was replaced. Both are patterns: sweep for the class, never
just the instances a reviewer happened to name, or the ones nobody spotted
survive by construction.

**Before checking this box, if the phase-6 STUB mechanism was used, sweep
for leftover scaffolding:**
`grep -rn 'STUB(<feature-slug>)' <source dirs, excluding docs/>`. Any hit
means a stub was implemented but not cleaned, or a planned symbol was
abandoned in place — resolve it (finish or delete) now. The reviewers
receive the diff in phase 9 and treat a dangling stub on shipped code as a
finding, so an unswept marker just becomes a review blocker. Use the exact
slug token from phase 6 — one-character drift makes the grep silently match
nothing, and a no-op gate reads as "covered" when it isn't. (In a run that
introduced no stubs, don't run a grep that can only ever match nothing and
mistake it for a passed gate — confirm the green from the contract's
checks instead.)

## 8. Documentation

Not optional, and not foldable into review. Split by *information source* —
code-derived docs go to the specialist; conversation-derived state stays with
you, because only you hold the context to write it:

1. **Code-derived docs (`librarian` agent).** Delegate: bring the `docs/`
   codebase map current (it invokes `/sync-docs`) and update the
   feature-level docs this project keeps. It reads the code directly, so it
   needs none of this conversation — and can't write what isn't in the code.
   For an outside repo, brief it per §0 *Docs*: that repo's conventions, no
   bootstrapped tree.
   **Route every code-derived reference table here** (exit codes, flag lists,
   output contracts, which stream a marker goes to) even when it sits in prose
   you were already editing — those are facts about the code, and yours drift.
   Write its report into the design doc, act on its flags, and log the pair:
   a `code-change` for its edits (docs are diff the reviewers must see) and
   `close-out: librarian — scope full — deferred: none`, followed by the
   checkpoint commit that captures its work (that checkpoint's SHA, not a
   field on the close-out line, is what phase 12 reads as the tree this pass
   covers). Scope `full` is load-bearing — the phase-12 gate discriminates on
   exactly that word.
2. **Finalize the design doc (orchestrator).** Decisions taken, deviations
   from the plan — this is conversation-derived rationale the librarian
   doesn't have, and the design doc is your resume state, so you own it. If
   the librarian flagged a stale design/rationale doc, fix it here. Three
   mechanical passes, each of which otherwise arrives as a review finding:
   - **Grep the doc for the vocabulary of every rejected alternative** (the
     widget you didn't use, the pre-revision call, the bound you replaced) and
     confirm no surviving line still asserts it as current. A gate revision
     edits the code but rarely every sentence written on the old design — this
     is how one doc ends up stating two different bounds.
   - **Cite symbols, not line numbers, in anything written from phase 7 on.**
     The plan legitimately cites lines (it described the pre-change tree); a
     record written after the change is read *after* the lines moved, and a
     citation that now lands on unrelated code is worse than none.
   - **Correct a claim in every place it lives, then grep to prove it.** The
     surfaces you're editing are prose, and a claim usually also sits in a
     comment or docstring — including, twice observed, one written by the very
     commit doing the correcting.
3. **Compound durable lessons → `docs/solutions/` (orchestrator writes).**
   A non-obvious lesson this run surfaced should make the *next* feature
   cheaper. It's conversation-derived — only you hold the failed-experiment and
   gotcha context — so by this phase's own source-split rule you write it, not
   the librarian. **Conditional, not automatic**: only a genuinely reusable
   lesson (a failed experiment worth not repeating, a gotcha, a non-obvious
   constraint). A routine build writes nothing — the store must stay
   signal-dense, not a per-feature log. When it qualifies:
   `docs/solutions/<category>/<slug>.md`, minimal frontmatter
   (`name`, `description`), light categories (`gotchas/`, `patterns/`,
   `decisions/`) — no deep taxonomy.

   **The store self-indexes — `/sync-docs` deliberately skips `docs/` itself,
   so don't expect the librarian to pick these up.** You maintain it: append a
   one-line pointer (`- [title](category/slug.md) — hook`) to
   `docs/solutions/INDEX.md` (create it the first time, MEMORY.md-style). Don't
   wire it into the root `docs/INDEX.md` — that file is sync-managed and would
   drop a non-source link on the next sync; cross-agent discovery rides on the
   CLAUDE.md docs-first note instead.

   **Retrieval:** the phase 1 `researcher` delegation reads
   `docs/solutions/INDEX.md` first (already instructed), so future runs find
   prior lessons without a grep. `/refresh-solutions` is the companion skill
   that keeps the store curated and the index honest over time.

4. **Verify the docs mechanically (orchestrator).** If the project has a docs
   lint (`tools/docs_lint.py` in this repo), run it and close what *this build*
   introduced — most often a design doc or lesson written above without its
   index line, which is exactly the failure the store cannot see on its own. Fix
   those before the box is checked; report pre-existing findings without acting
   on them, so the run doesn't silently inherit somebody else's backlog. No lint
   in the project → say so once and move on; don't build one here.

Do not enter phase 9 with this box unchecked — the reviewers receive the
docs as part of the diff and treat stale or missing documentation as
findings, so skipping this phase just converts it into review blockers.

## 9. Review loop (contract review + `code-reviewer` + `maintainability-reviewer`)

**Launch phase 10's smoke test now, alongside the reviewers.** The two are
independent — reviewers read the diff, smoke exercises the built thing — and
running them together is what keeps smoke's findings inside *this* phase's fix
round. Deferred until after this phase closes, they arrive as a `code-change`
that postdates the full close-out and reopens the phase-12 ship gate for all
three agents; that is the most expensive avoidable detour in this pipeline.
Phase 10 keeps its number and its box; only its start moves.

Two halves, both mandatory **whatever the medium**:

- **The contract's review**, run by its *review* agent,
  medium-appropriately: for an executable deliverable it coincides with
  the code review below; for rendered/assembled media it's the read of
  the whole — batched across agents for a multi-page artifact (~7 pages
  each; a single agent handed 20+ full-page images stalls without
  returning).
- **Both code reviewers on the accumulated diff, in parallel — always**,
  even when the deliverable renders: the code that produced it ships too.
  The diff's base is the last reviewed checkpoint (the ledger's run base on
  a first pass) — widen to the original scope only when the fix changed a
  *basis* other findings derived from, per the invalidation rule below, and
  say in the ledger's `checkpoint` field which of those two fired. Launch
  both as fresh subagents with only the diff and the design
  doc — no implementation context. That isolation is the point: they check
  the work, not the intentions. **One exception:** to confirm that findings
  *a reviewer itself authored* were applied as specified, resume that agent
  rather than dispatching a fresh one — it is checking its own list, so
  isolation isn't at risk, and it costs a turn against a fresh pass's dozens.
- **Show the user each review summary — the findings as written, not your
  narration.** Paraphrasing makes your rendering the only version in the room,
  and a claim you got wrong then survives a round longer than it should.
- Fix blockers and should-fixes per the fix protocol above — **the reviewers'
  and the smoke run's, in one round** — then re-review. **Max 2 fix rounds**; if
  the third review still has blockers, stop and hand the open findings to the
  user. Annotate the round on the checklist box (`- [ ] 9 Review passed (fix
  round 1/2)`) — the annotation, not the box state, carries the count (on a
  phase-11 re-entry the box is already `[x]`), it lives in the design doc, and it
  **resets per batch**. A fix round invalidates the smoke run too: re-exercise
  after the last fix, and don't close either box on a stale pass.
- **A fix that changes the basis of a prior measurement** (a re-crop, a
  re-render, a renumbering) invalidates verification of everything derived
  from that basis, not just the items edited — so the re-review covers the
  same scope as the review that found the defect; a spot-check is not a
  re-review.
- After each completed pass, append a close-out ledger event (field
  semantics per the phase-0 seed comment: **scope `full` or `delta`**, no
  SHA on this line) — then, with checkpoint consent, commit the batch-close
  checkpoint and log its SHA on its own following `checkpoint:` line — that
  line, not the close-out line, is what later delta reviews diff from and
  what phase 12 reads as this pass's coverage.
  <!-- Three callers use these close-out mechanics: this full pass, the
       scoped deltas of phases 10–11, and phase 12's ship-gate runs — keep
       their scopes distinct; phase 12 discriminates on that field. -->
- Prompt/instruction improvement ideas from reviewers (e.g. "this LLM
  artifact keeps appearing — instruction X would prevent it") are collected
  under `## Kit suggestions` in your report to the user. Suggestions only —
  see the hard rule in `SKILL.md` (never modify `.claude/` or the kit-managed `CLAUDE.md`).

## 10. Smoke test (starts with phase 9, closes after it)

Exercise the deliverable end to end — the contract's medium tag says what that
means (start the app and poke it, a full toolchain run, render and read).
**Breadth** is what makes this a smoke rather than a repeat of phase 7's green:
broader input, more cases, the adjacent path, and **real-world state rather than
the fixtures the tests use** — copy an actual target, never write to one. A
long-lived app's *process* runs from the orchestrator (background Bash) so it
survives into phase 11; the poking is a general-purpose agent's job. Anything
rendered gets *looked at* — a "checks pass" run is blind to layout and styling;
delegate per the *checked by* rule in `SKILL.md`, never silently skipping the look.
Land a condensed result in the design doc (a few lines, never logs) and keep the
run's actual outputs on disk, saying where — phase 11 hands them over.

## 11. User testing (orchestrator, gate)

First, audit your own checklist: re-read every `[x]` and name, one line
each, the observed evidence behind it — a phase ticked on inference rather
than execution goes back to `[ ]` (a run has ticked the smoke test PASSED
before the ship path was ever executed) — and you **execute it now, before
the hand-over**: an unticked box is work owed, not an annotation. Then hand
the deliverable to the user and wait. For a long-lived app that's the running instance; for a
run-to-completion artifact (per the contract's medium tag) it's
the run command + representative input so the user can exercise it themselves,
plus the last run's outputs to inspect — there's no persistent instance to hand
over. Every issue the user finds gets fixed **immediately** (per the fix
protocol at the top) so testing isn't blocked on documentation/review. The close-out is **two-speed,
deliberately** — every fix still gets reviewed, but only the ship gate pays
for the full pass:

- **Interim hand-backs get a scoped delta review**: one `code-reviewer` at
  **brain-top** (most interim batches' only review — never a tier to economize
  on), on the diff since the last reviewed checkpoint, its prompt carrying the
  prior round's findings to check against, and told explicitly that **doc
  staleness is known-deferred and not a finding this round** — without that line
  it re-reports the same blocker every batch, by charter. No `librarian`, no
  `maintainability-reviewer` yet.
- **The full close-out — `librarian` + both reviewers — runs once, before phase
  12** (the ship gate enforces it). Force it early when the accumulated delta
  stops being local: a new public symbol, more than one module, or three or more
  hand-backs.

Track the loop in the design doc, not your head: a short `## User testing` list
(found / fixed / last batch closed), a `code-change` event per fix dispatch, a
`close-out` (scope `delta`) per delta review, and the batch-close checkpoint
with its SHA on its own line. What must never happen is reaching phase 12 with
code no reviewer saw, or with the full pass older than the last code change.

The user decides through their own testing when the loop is
done; don't nudge. Once they're satisfied, phase 12's precondition is what
actually guarantees docs and review are current against the final code —
not a promise made here.

## 12. Commit (orchestrator)

**Precondition — the ship gate:** before committing, each of `librarian`,
`code-reviewer`, and `maintainability-reviewer` must **individually** have
seen the tree exactly as it now stands — conjunctive, per agent, never "some
reviewer ran recently". For a non-executable deliverable the contract's
*review* agent is a fourth member: its last whole-artifact read must
postdate the last change to the artifact — a re-render after the read
reopens it. Read the **close-out ledger**, not your memory of
dispatch order: for each of the three, take its last **`full`-scope**
close-out event, then the `checkpoint:` line immediately following it — that
SHA is the tree that pass covers (never a SHA written on the close-out line
itself; there is none). That SHA must postdate the last `code-change`
event's own following-checkpoint SHA, per `git log <base>..HEAD` order.
A `delta` entry never satisfies this gate — it saw a slice and was told to
ignore doc staleness. Run
whatever is missing now, in this order: **`librarian` first, then both reviewers
on the post-librarian tree**, each at its own phase tier (never the place to
economize), each on the diff since its last full pass — and close each run out
like phase 9: append its `close-out` (scope `full`) and, with consent, commit the
pre-12 checkpoint, logging its SHA. A gate-filling librarian that edits docs logs
a `code-change` like any dispatch; the reviewer runs that follow it are what
close that edit. The phase-11 delta
reviews deferred these passes; this is where the deferral is collected — and a
`code-change` logged *after* an agent's last full pass legitimately re-opens
that agent's gate: the gate working, not a ledger error.

**When a gate agent dies** (stall, API error, watchdog) — expect it here, since
these are the run's biggest dispatches. Apply `SKILL.md`'s run-wide stall
protocol (retry same tier, inspect the tree first, narrow scope, orchestrator
may finish verification itself with a logged `code-change`) — this is a
dispatch of that kind, not a special case. **Never log a close-out for an
agent that didn't finish**: that forges the gate's only evidence and is
precisely how an un-run agent passes silently. Retry sequentially rather than
in parallel. If you must substitute a different agent type, log it under the
agent that actually ran and say the named specialist didn't — never relabel,
or the ledger stops recording who saw what.

**If the ledger is missing or its ordering can't be established (compaction,
resumed session): don't guess — re-run all three on the current tree**, recorded
and checkpointed like the runs above, recreating the ledger section first (fresh
header, base := current HEAD) if it's gone. One redundant pass is the cost of a
crash; a
silently skipped ship gate is not. This is the one hard gate that catches a
phase-11 loop that batched fixes without ever looping back — skipping it is
how stale docs or an unreviewed change ships.

On user approval, close out the git state, then commit. Either path may carry
late uncommitted edits, so reconciliation is yours, not `/commit`'s: ask
squash-or-keep, and say what each costs — **squash orphans every SHA the ledger
names**, so it also means rewriting those lines into milestone descriptions.
**Before the reset, verify the chain is yours.** Run
`git log --oneline <base>..HEAD` and read every subject: each must be a
`wip(<slug>)` checkpoint this run made. A run holds a branch for days, and a
parallel session can commit onto it — a squash folds that commit's *content and
message* into this feature's commit, silently. Any non-`wip(<slug>)` commit is
somebody's stopped work: unstage its files after the reset, squash the rest, and
replay it as its own commit with its original message and authorship
(`git cherry-pick` after committing yours preserves both). Staged-file discipline
cannot catch this — the foreign work is already committed, so it never appears in
`git diff --cached --stat`.

On **squash**, `git reset --soft <run base>` (the ledger header records it) turns
the feature into staged changes, then invoke `/commit`. On **keep**, the wip
chain stands and `/commit` takes the remainder. Without checkpoints, `/commit`
on the dirty tree. With outside repos, all of this runs per repo and the home's
files follow §0 *Phase 12*. Merging/PR is the user's call — say so and stop.

## 13. Kit retrospective (`kit-retrospective` agent)

The run is locked in — now reflect on the *pipeline that produced it*, not
the code (the phase-9 reviewers already owned the diff). Dispatch the
`kit-retrospective` agent to mine the raw run for kit-improvement ideas.

Hand over paths, never a summary — a summary frames the run before the agent
sees it, and it reads the unfiltered transcript precisely so it isn't
influenced. Resolve the transcript deterministically (session ids are unique,
so this is concurrency-safe):

```bash
find ~/.claude/projects -maxdepth 2 -name "$CLAUDE_CODE_SESSION_ID.jsonl"
```

Pass: that path, its `<session-id>/subagents/` dir (same path with `.jsonl` →
`/subagents/`), the design doc, and the kit instruction locations
(`.claude/skills/build/SKILL.md`, `.claude/agents/*.md`). It digests
transcripts in its own context, so the run's bulk never enters yours. It
resolves its own evidence — re-running that `find` itself rather than trusting
your path — and says so if it can't find the record. **On a long run, tell it
to sample rather than read linearly, and to skip the suggestions already
captured**: a linear read of a 25-dispatch transcript is how this agent
stalls, and its value is what nobody noticed from inside.

**One thing it must always read in full, never sample: every `AskUserQuestion`
call paired with its `tool_result`.** These are the densest signal in the record
and the cheapest to extract — a dozen or so exchanges against thousands of tool
calls. Require the pairing to be done *mechanically* (walk the JSONL, match
`tool_use_id`, dump question text, **every option's `description` and `preview`**,
and the **full result payload** to a scratch file, then read that) — an agent that
reads option *labels* only will silently reconstruct the answers from outcomes and
report inference as observation. What lives in there and nowhere else: which
questions the user answered **against** the recommendation, which they refused or
dissolved with free text, when they first signalled that something was being
over-escalated or under-verified, and whether an option's own description already
contained the fact that made the question unnecessary. Sampling loses all of it.

**Present the returned suggestions to the user verbatim** under
`## Kit suggestions` in the design doc (folding in any the phase-9 reviewers
already left there). Suggestions only — the hard rule at the top applies
even here. The user decides what to apply.
