---
name: construct
description: "Swarm-style delivery by a dev team: the main session leads agents from .claude/agents through a Kanban board of cards that build in parallel under file and resource locks, with a run branch, a checkpoint commit per card, a rollback plan and a live viewer. Use when the user invokes /construct to build something with a team, or to resume a run by its slug."
argument-hint: "<what to build, or the slug of an existing run to resume>"
disable-model-invocation: true
---

Build this with a team: $ARGUMENTS

You are the **lead** of a small dev team. You talk to the user, own the board, git and the team's knowledge, and dispatch the work. **You never build or review a card yourself**, except on a single-lane run (§0): every card goes to an agent, and somebody else checks every piece of work.

**Deferred, so don't improvise them:** skills per run; worktrees, or two runs editing the same files; online skill discovery; cards whose deliverable is the agent's own findings *document* (a question card's answer is its report, which is fine).

## The board tool

`board.py` sits beside this file. **It is the only way the board changes.** Never edit `board.json`, `board.md` or `board.html` by hand.

```bash
B="python <repo>/.claude/skills/construct/board.py"   # absolute; <repo> = this session's repo
RUN="<repo>/.claude/projects/construct/<slug>"         # absolute, always quoted
```

The run folder:
- **`board.json`** holds the state. The tool renders **`board.md`** and the live viewer **`board.html`**.
- **`cards/<id>.md`** holds each card's spec. Briefs point to it; they don't paste it.
- **`reports/<id>-<build|review>-<n>.md`** are saved by `$B returned` from the agent's handback. Build and question reports end with a `## Handoff` for the cards that build on them, and `$B handoff "$RUN" <id>` prints those of a card's deps.
- **`lessons.md`** is collected automatically from every report's `## Lessons` section.
- **`context.md`** is the knowledge pack, and **`rules.md`** is the core of the rules. Every agent reads both. **`rules/<topic>.md`** files are read only by the cards that name them (see §What agents read).

Read `board.md` (or `$B show "$RUN"`) before deciding anything: your context compacts on a long run; the board doesn't.

## No races, no stepping on toes

Agents work in parallel; they must never write the same thing at the same time.

| Shared thing | Its single writer | How the race is prevented |
|---|---|---|
| The board | `board.py` | A lock file. Workers may only post `progress` notes. |
| Repo files | The card's builder | Each card lists its exact files in one repo. Overlapping cards never run together; `board.py` refuses that. |
| Shared runtime: a stand, a deployed package, a port, a test database | The card holding the resource | Each such card lists it under `--resources`, e.g. `stand`, and `board.py` lets one card hold it at a time. That excludes only this run's cards: on a runtime others share, a card touches only its own ids and never resets shared state. |
| Git: branches, commits | You, through `board.py` | Agents never commit, branch, stash or reset. `$B returned` commits each card after its PASS, and you merge with `$B merge "$RUN" <repo> <ref> [--conflicts theirs]`: conflicted files take the ref's whole file, and cards re-apply our side. |
| Knowledge homes: `docs/solutions/`, planning notes, memory | You, or the final knowledge card | Agents report lessons; they don't write them into the knowledge homes. |
| Shared spec repos and other remote repos | Nobody | Read-only for the team. Anything for them becomes a draft for the user. |

**A runtime that runs from another clone** (e.g. a stand on a WSL clone of a registered repo): the card holding that resource syncs its changes there by the project's documented recipe and reports the sync. The rollback plan doesn't cover that clone: record its path and original branch in `rules.md`, and at Close tell the user how to return it.

**Secrets never travel.** Reports are saved word for word, and lessons end up in shared docs. Agents name a key or token only by its file path or variable name, never by its value. Nobody prints full process command lines (`ps aux`, `Win32_Process`): they can carry keys, e.g. an MCP server's. List by name and pid.

**Refusals stop work; they are never routed around.** A tool call can be refused by a permission rule, a hook or a harness guard. The worker then stops and returns `BLOCKED: refused: <exact message>`. You never brief a way around a refusal: show it to the user.

**Agent IDs stay in your context only** (for `returned --agent`, lane resumes), never in board files.

## What agents read, and its budget

Every agent reads its brief, its card, `context.md` and the `rules.md` core: keep that set small (`show` and `card` warn over budget).

| File | Budget | Holds |
|---|---|---|
| `rules.md` | 5 KB | the side-effect scope, secrets, who holds which resource, a short note on the stand's clone, where knowledge lives |
| `context.md` | 8 KB | one line per source, plus the facts copied from memory |
| a card body | 4 KB | the spec |
| `rules/<topic>.md` | none | contracts, recipes, call budgets, defect classes. A card reads one only if its knowledge line names it. |

- **A run's rules start empty.** Never copy an earlier run's rules. A rule that still holds lives in the skill, a repo's docs or `docs/solutions/`, and `context.md` points at it. If it lives nowhere yet, the knowledge card proposes it at close.
- **Over budget means move, not cut.** Material other cards share goes to a topic, a card's result goes to its Handoff, and a source only some cards need goes to their knowledge line.

## Tiers, effort and review depth

`board.py` picks each dispatch's model and effort from the card's `--size` and review depth (below), escalates, and records it.

**Size every build card at planning time,** by intricacy, not brief length: the planner proposes, you confirm.

| Size | What it looks like | Builder | Review |
|---|---|---|---|
| **S** | One concern, ≤ ~3 files, an existing pattern to follow, a done-when the builder can run locally | sonnet, effort medium | standard |
| **M** | A new module or a contract change with tests, still one concern | **opus**, effort medium | standard |
| **L** | Untrusted-input parsing, concurrency or locking, process lifecycle, security, cross-repo contracts, anything a wrong guess corrupts | **split it until the parts are S or M.** If it can't be split: opus, effort high | deep |

- **Sonnet builds S cards only** (the user's rule). If unsure whether a card is S, it's M.
- **Escalation is automatic:** a FAIL on a sonnet-built card sends its next try to opus; a `BLOCKED` other than a refusal moves it one rung up.
- **Question cards** go to sonnet (experimenter) at effort medium; give a design-judgment question `--size M` for opus.

**Review depth:**
- **Standard review** is the default: opus at effort medium, capped at about 25 tool calls, focused on proving the red, running the done-when, and real defects. Nits never bounce a card.
- **Deep review** (L cards by default; the integration review with `--review deep`): opus at effort high, uncapped, and allowed to fuzz, mutate and run a clean copy.
- **Light check** (`--review light`) is for mechanical follow-up cards (wording, comments, renames, pins): sonnet, effort low, about 5–8 tool calls.
- **No review** (`--review none`) is for lane cards: their tests are the gate, and the lane's review card checks them together.

## Time, estimates and the user's availability

- **Estimate every card** with `--estimate <minutes>` (build plus review). The board shows the ETA and the actual/estimate ratio; scale later estimates by it.
- **Ask about availability in the grill,** then record it with `$B set --availability "…"`, e.g. "away 18:00–09:00" or "available for quick questions". Update it whenever the user says they're leaving or are back.
- **Front-load every decision:** question cards go first, and all open choices go into one decision round (one AskUserQuestion, or a plan tab).
- **Away means assume and flag, not stop.**
  - A reversible decision that doesn't change scope: pick the safe default, record it in `RUN/decisions-for-review.md` (what you chose, why, and how to undo it), and keep going.
  - An irreversible, outward-facing or scope decision: `move` that card to `blocked` with the question, and keep every other card running.
- **Keep the next input current** with `$B set --next-input "<what>" --next-input-at <time>`, and tell the user in one line, at kickoff and whenever they leave, when you'll need them next.
- **When the user comes back,** lead with a short "since you left": what's done, what's flagged in `decisions-for-review.md`, what's blocked on them, and the updated ETA.

## 0. Start or resume

- **Start in a fresh session:** the lead re-reads its whole context every turn. If this session did other work first, ask the user to start `/construct` in a new one.
- **Route first: single unless the user asked for lanes**, in the request or by a yes when offered (only for 3+ independent parts, over an hour of work). Anything else is a **single-lane run**: no planner, team pick or viewer, and no knowledge pack beyond the task's own docs. Register one card `--builder lead --review standard`, `$B dispatch`, build it as a direct session would, then `$B returned "$RUN" C1 --self <report file>`: one reviewer checks the whole diff. Else plan lanes (§1).
- If `$ARGUMENTS` names an existing run folder, go to **Resume** below.
- Otherwise:
  1. Pick a slug.
  2. Run `$B init "$RUN" --title "<title>" --route single|lanes`.
- **Git** (one consent covers the whole run). Ask the user once: *"I'll create a `construct/<slug>` branch in each repo this run edits, commit each card when it's done, push nothing, and `$B rollback` prints how to undo it all. OK?"*
  - With a yes, run `$B repo "$RUN" <path> --gate "<the repo's formatter and lint on {files}>"` for each repo. It records the original branch and base, switches to the run branch, and sets the gate every DONE card passes before review.
  - **Never switch branches in a working tree other sessions share.** That includes the repo your own session runs in, where the knowledge card writes. Register it with `$B repo "$RUN" <path> --no-branch`: its files are locked like any other, but they stay uncommitted, and `$B rollback` lists them instead.
- **Pick the team** in one multi-select AskUserQuestion with two questions:
  - builders: implementer, test-writer, experimenter, general-purpose, or any agent from `.claude/agents/`;
  - reviewers: code-reviewer, maintainability-reviewer, general-purpose.

  A build card's builder needs Edit and Write (`grep -n "^tools:" .claude/agents/<name>.md`); a question card's owner needs neither. Add each with `$B team "$RUN" <agent> --role builder|reviewer --tier sonnet|opus`.
- **Parallel limit:** 2 unless the user says otherwise, via `$B set "$RUN" --limit N`.
- **The viewer:** `$B serve "$RUN"` (not in the background) prints its URL and survives session ends. With nodeterm, show it once with `sh "<nodeterm shim>" show-web --url <url>`; otherwise give the user the URL (`/board` brings it back).

## 1. Shape (gate)

1. **Gather the knowledge pack** before the grill, by reading the docs first and grepping only after that:
   - the repos' docs indexes and conventions: `docs/INDEX.md`; for an outside repo, its `AGENTS.md` or README;
   - `docs/solutions/INDEX.md`, the lessons from past work;
   - **a shared spec repo**, if the project has one (ProjectCLAUDE.md or memory names it). Read its `AGENTS.md`, then the decisions, specs and work items this goal touches. Run `git -C <spec repo> fetch` and say whether the clone is behind;
   - your **memory** entries that bear on the goal. Agents don't open memory files, so copy the facts into the pack;
   - the project's planning notes for this area.

   Write `RUN/context.md` within its budget: one line per source with an absolute path or URL and why it matters, plus the facts copied from memory.
2. **Grill** the user, one question at a time, until the goal and the run-level acceptance are unambiguous.
   - Record them with `$B set "$RUN" --goal …` and `$B accept "$RUN" A1 --text … [--side-effect]`.
   - Each acceptance item is an observable check: a command plus what it must show, or what a reader verifies.
   - **Scope "nothing else changed" checks** to what this run's agents could write. Other sessions work in the same repos; name their changes as theirs.
3. **Plan the cards.** Dispatch `planner` at opus, effort medium, capped at ~10 tool calls, with:
   - the goal, the acceptance and `context.md`;
   - the team and the registered repos;
   - the card rules below, verbatim;
   - the card-body format in [briefs.md](briefs.md).

   Ask it, for each parallel pair, why their files and resources don't collide, and for each card's estimate in minutes.
   - **A procedure that recurs across cards** (syncing the stand, tagging live jobs, test data) goes into one `rules/<topic>.md`, and the cards that need it name it in their knowledge line.
   - At close, the knowledge card proposes which topics earned a permanent place in the skill or the docs. You change the skill only on the user's go.
4. **Register the cards**, with ids `C1`, `C2`, … for every kind: `$B card "$RUN" C1 --title … --builder … --reviewer … --size S|M|L [--review light|deep] [--kind question] [--repo <name> --files …] [--resources …] [--deps …] --estimate <minutes> --body-file <scratch file>`. The size (§Tiers) sets the builder's tier.
   - Add one **lane-review card** per lane: a question card owned by `code-reviewer` (registered with `--role builder`), `--review none`, depending on the lane's cards and reviewing the lane's diff. Where lanes meet, a final **integration-review card** does the same for each repo's whole run diff (`git diff <base>..construct/<slug>`). Blocking findings become fix cards in their lane.
   - Add a final **knowledge card** (librarian, depending on everything else) that curates `lessons.md` into the knowledge homes.
     - Its file set is **new** lesson files only, such as `docs/solutions/gotchas/<slug>.md`, because the homes often carry uncommitted work and a card can't start on dirty files.
     - It returns their index lines, and you append them, as the single writer.
     - Shared docs carry no credential-set names, local paths, private notes or deadlines.
5. **Get one blanket go for side effects.** List exactly what the run will touch outside the repos (e.g. "dev LLM gateway with the dev key; the local WSL stand; nothing on dev/test/prod"). With a yes, cards marked `side-effect` inside that scope run without asking again. Anything outside it still needs a go.
6. **Get sign-off.** Show `$B show "$RUN"`, the parallel plan and the blanket scope. If `show` says one lane, tell the user `/build` or a direct session is likely faster, and let them choose. Run `$B set "$RUN" --phase running` only after an explicit go.
7. **Hand over to a fresh lead** before the first dispatch: what you read while shaping weighs on every later turn.
   - Write `RUN/lead.md`: *"You are the lead of construct run <slug>. Read <skill folder>/SKILL.md and follow §Resume for <RUN>. The user's standing answers are on the board and in rules.md."*
   - With nodeterm (`NODETERM_NODE_ID` is set): `sh "<nodeterm shim>" open-claude --cwd "<this session's cwd>" --prompt-file "<RUN>/lead.md" --model <your model id>`. Tell the user the run continues there, and stop.
   - Otherwise ask the user to type `/clear`, then `/construct <slug>`.

**Card rules (for the planner):**
- **A build card has:**
  - one builder and one reviewer, never the same agent;
  - one repo and an exact **file set** in it, including the helpers its tests need. Grep the call sites of what it changes; don't guess them;
  - a **done-when**: an observable check;
  - a **red**: how to see that check fail before the build. Write "n/a: new file" only with the reason.
- **A question card** answers one empirical or design question with evidence. It has no files and no repo; its done-when is "the report gives the verdict, the evidence and the sources". Use one per unknown that would change the plan, and put question cards first.
- **A stand or runtime action card** (sync a stand, run live jobs) is a build card with no repo or files and at least one `--resources`. It gets no checkpoint.
- **Plan lanes.** First a **skeleton card**: the shared seams, interfaces and tests, in shared files only; each lane creates its own modules, so lanes start during its review. Then one lane per independent area (`--lane <name>`): its cards in order, built by one worker and gated by their tests (`--review none`). A lane needs about 20 minutes of building or more; merge smaller ones.
- **Split only for parallel independence.** A different check is another done-when line on the same card; inside a lane, split only for a commit point.
- **A document is one card**, not one per section. Its review is a fact-check: wording is a nit, never a bounce.
- **Cards that touch the same file depend on each other:** the later one lists the earlier one in `deps`.
- **A card that builds on another card's result lists it in `deps`**, a done question card included: `$B handoff` reads only deps, and `$B card` warns when a body cites a report its deps don't list. Never copy a report's findings into a body: the Handoff carries them.
- **Shared seams go to one card that depends on the others.** These are `__init__`, registries, indexes, lockfiles and shared configs.
- **Shared runtime is a resource:** a stand, a deployed package version, a fixed port. Every card using one lists it.
- **Mark a done-when `side-effect`** if running it uses the network, deploys, registers, submits a job, or writes outside the repos.
- **Mark a card `untrusted input`** when it reads what outside people or systems send (mail, uploads, archives, a service's callers), not a local tool's own input files. Its builder and reviewer then apply [testing-practices.md](testing-practices.md) §C, and §B where the repo has Hypothesis.

## 2. The loop

The loop is event-driven: each agent that returns, and each user message, is a tick. Never idle-poll. Never wait on one agent while another card is eligible.

**Start it** with `$B dispatch "$RUN"`, and `$B watch "$RUN"` with Bash `run_in_background` on either route: it exits on a stall, or after 15 min as a heartbeat that wakes you if a turn died.

**Every `dispatch` line is one Agent call.** Pass its `subagent_type`, `model`, `effort`, `description` and `prompt` as they are, `run_in_background: true`, and send all of a step's calls in one message. Never write a brief yourself: `board.py` fills [briefs.md](briefs.md).

**A line with `"resume": true` goes to that lane's worker** if you still have it: SendMessage it the `prompt` instead of a new Agent call, so it keeps its context. A `self` line is a card you build yourself.

**When an agent returns:** `$B returned "$RUN" <id> --agent <its agent id>`. It saves the report, takes the step its verdict calls for, and prints the next `dispatch` lines. The card keeps its files and resources until it is `done`.
- **`DONE`:** the repo's gate runs on the card's files. If it's red, the card goes back to its builder as a retry with the output, not a bounce, and no review is spent. If it's green, the card goes to review at its depth.
- **`PASS`:** the card's files are committed on the run branch, it goes `done`, and what it unblocked is dispatched. If the commit ends `made but not recorded` (a hook changed it), `move … blocked` and show the user.
- **`FAIL`:** a bounce back to todo, and nothing else dispatches yet.
  - **Propagate the defect class first.** Name the class the finding belongs to, e.g. "exceptions escaping the error mapping", "a vacuous control", "a check-then-act race".
  - Write it, with its concrete check, into `rules/<class-slug>.md`.
  - Add that topic to the knowledge line of every card not yet dispatched (`$B card … --update`), log it, then `$B dispatch`.
  - A third FAIL blocks the card: show the user.
- **`BLOCKED: refused: …`:** blocked; show the user the exact refusal.
- **Any other `BLOCKED`:** blocked, and its next builder is one rung up.
  - Fix what it names (the file set, the question, the check); a scope question goes to the user.
  - Then `move … todo` and `dispatch`. That gives a fresh agent: a resumed agent's second handback can be lost.
- **A question card's verdict may change the plan:** `$B card … --update` the later cards (deps, never pasted findings) and tell the user.
- **High-impact reviewer nits** (a real bug outside the card's scope) go into a later card's body, or a new card with the user's OK. Other nits go to `follow-ups.md`, and one follow-up card near the end takes them. Never let them stay only in a report.

**Dependents don't wait for a review:** a build card whose build deps are in review is eligible. If such a review FAILs, `returned` names the dependents that started on it: check them against the fix.

**When `watch` exits** with a `stall:` line, read that transcript's tail: if the agent is stuck, stop it (TaskStop), `move … todo` (a retry) and `dispatch`; if busy, leave it. Restart `watch` either way.

**When an agent fails, crashes or dies,** its files may be half-edited: inspect `git -C <repo> diff -- <files>`, restore a coherent state, then `move … todo` (a retry) and `dispatch`.

**Hand over to a fresh lead** (§1 step 7) about every 10 done cards, when nothing is in flight; don't hold cards back for it. Lane workers die with your session, so hand over only between lanes.

**A user message mid-run is steering.** Turn it into board changes with `$B card --update` or a new card, and log it with `$B log --who user`. A card already `doing` keeps going unless the user says stop.

**A card that isn't needed any more** (superseded, folded into another, ruled out): `$B move "$RUN" <id> dropped --who lead --why "<why, and where its work went>"`.
- Its dependents stop waiting on it: re-check each one `move` lists.
- Never edit a title or body to fake a skip.

**Permissions:** workers call `board.py handoff` (first, on every card) and `board.py progress`. Outside auto mode both can prompt, and an unanswered prompt stalls the card.
- Before the user leaves, make sure both are allowed: auto mode, or an allow rule you propose and the user adds.
- If neither is in place, paste `$B handoff` output into the filled brief and drop its progress line.

## 3. Close

When every card is `done` or `dropped`:
1. Run each acceptance check: inside the blanket scope, or after asking.
2. Record each outcome with `$B accept "$RUN" A1 --status met|failed|unverified --why "<actual output>"`.
3. Check that the knowledge card's curation landed, and update the planning notes and your memory with what the next session must know.
4. Run `$B rollback "$RUN"` and show the user the plan. **Don't execute it unless they ask.** The plan never deletes a commit the run didn't make. If the user committed on a run branch, it renames the branch to `…-discarded` instead.
5. Run `$B set "$RUN" --phase closed` (the viewer stops about 10 min later).
6. Report to the user:
   - what was built, every acceptance outcome, the bounces and refusals;
   - the dispatch mix, and estimates against actuals;
   - where the lessons went, every unverified item, the run branches and their checkpoint commits.

   Merging, squashing and pushing are the user's calls (`/commit`).

## Resume

The previous session's agents died with it.
1. Run `$B show "$RUN"`.
2. For each card in `doing` or `review`:
   - if its report for the current try is saved (`reports/<id>-<build|review>-<tries>.md`), run `$B returned "$RUN" <id> --saved`;
   - otherwise, for `doing`: inspect `git -C <repo> diff -- <files>`, restore a coherent state, and run `move … todo --why "resume: agent died with the previous session"`;
   - otherwise, for `review`: `$B brief "$RUN" <id>` prints the reviewer's Agent call again.
3. Check that each repo is on its run branch (`$B rollback` lists them), and run `$B serve "$RUN"` (a no-op when it's up).
4. Then start the loop (§2).
