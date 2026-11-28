# Decisions

Numbered entries, cited as `#N`. Each entry says what it constrains and why, with the alternatives rejected; the how lives in `ARCHITECTURE.md` and in the code, the chronicle in `CYCLES.md`. Status: `proposed`, `active`, `partly superseded by #M` (the entry already states the rule in force), `superseded by #M` (moved to `decisions-archive.md`).

## #1 The LLM builds the machine, the network learns chess

Status: active. Date: 2026-11-24.

Haiku knows engine techniques by heart (alpha-beta, transposition tables, NNUE), so an engine written by it alone measures the ability to apply known knowledge, not to discover. The evaluation is instead learned by a network from the engine's self-play, starting from zero: what it knows comes from the data. The agent is free to choose the architecture, under a CPU budget per generation: in practice this leads to the Stockfish style (alpha-beta + NNUE on CPU).

## #2 Immutable referee, engines in ephemeral containers

Status: active. Date: 2026-11-24.

The agent has full control of the genome but no access to the referee. Every engine process runs in its own container (`--network none`, 1 CPU, read-only binary): in a shared container a candidate could kill its opponent's process. Perft is checked on random positions because the counts for the standard positions are known and can be hardcoded.

## #3 SQLite instead of PostgreSQL

Status: active. Date: 2026-11-24.

A single writer on a single machine, no concurrent access from other services: Postgres would add a service with no benefit. SQLAlchemy and Alembic stay, so a migration would be mechanical.

## #4 Append-only ledger, no soft delete

Status: active. Date: 2026-11-24.

The ledger is the history of the experiment: no row is ever deleted, so `deleted_at` would have no use.

## #5 Haiku 5.5 through OpenRouter, interchangeable provider

Status: partly superseded by #11 and #17. Date: 2026-11-24.

An iteration estimated at 2 to 5 cents, to be measured (from #11), cap of 2 $/day. Provider and model are pi configuration, so a local model (llama-server, LM Studio) or another provider is an environment variable (from #11). Comparing cheap models is postponed: it happens if Haiku underperforms.

## #6 Lichess as an external measure, not as a filter

Status: active. Date: 2026-11-24.

Games on Lichess are too slow to decide generations (hundreds a day against the thousands needed), but they give a rating the agent cannot fake. Chess.com is ruled out: it does not allow bots. The performance per generation counts rated games only (from cycle 6): the account mixes generations and a casual opponent can lose dozens of games in a row, as one did 43 of 45 against gen-17, lifting it by about 50 points.

## #7 Dashboard in the minimal live style (concept D)

Status: active. Date: 2026-11-24.

Out of four directions (dense lab, editorial genealogy, second-screen live, minimal live) the choice is D: the board in the middle with both players and the move list, the agent's captions, the current generation highlighted at the top, the history of generations on the left, and on the right only two cards (SPRT in plain words, spend). Rejected: A (too many elements for a screen meant to be watched), B (history alone does not say what is happening now: it stays as an idea for a secondary page) and C (same spirit as D, but noisier). The concept is in `docs/concepts/concept-a-dashboard.html`.

## #8 cburnett pieces and Lucide icons

Status: active. Date: 2026-11-24.

The cburnett pieces, the classic set of Lichess and Wikipedia, chosen by eye among seven sets whose license was checked in lila's COPYING.md. It is GPLv2+: fine for a personal project, but if the repository went public under another license the SVGs would stay GPL and have to be declared separately. The repository is now public under MIT, and LICENSE excludes them. Lucide icons because they are already the set of the shadcn components: a second set would be inconsistent.

## #9 Lichess losses become lessons for the agent

Status: active. Date: 2026-11-25.

The Lichess bot always plays the reigning champion and every loss joins a queue the agent reads, summarized, before every iteration: real opponents find weaknesses that self-play does not show. Stockfish analyses the lost games on the referee's side and points to the move where the evaluation collapses, but not to the fix. It is declared outside help: the network keeps learning only from the engine's own games. The rejected alternative, giving the agent only the game and the result, would make the feedback much poorer. Judging candidates stays with the local referee.

## #10 fastchess plays, the referee judges

Status: active. Date: 2026-11-25.

fastchess plays the games (pinned version, built into the `arena` image): time control, concurrency, crashes and PGN are solved problems, and rewriting them would give nothing. The judgement stays ours: the referee re-reads every PGN with python-chess and computes the pentanomial SPRT in batches, stopping when the likelihood ratio crosses a bound. fastchess's own SPRT is not used, so the verdict has a single source. The opening book is generated by the referee (random moves at equal material) until a book filtered by Stockfish replaces it.

## #11 pi as the agent harness, in RPC mode

Status: active. Date: 2026-11-25.

The agent runs inside pi, driven by the orchestrator with JSON over stdin and stdout. Compared with a loop of our own it brings well-tested file editing tools, which matter a lot for a small model, and OpenRouter support. pi's commands run in the sandbox, and the API key stays outside. Accepted costs: Node in the stack and a young project, hence a pinned version. Rejected: the Claude Agent SDK, with a heavy system prompt paid on every call and a tie to a single vendor. It replaces the OpenAI-compatible client planned in #5; the spend estimate rises to 2-5 cents per iteration, to be measured.

## #12 Standard tools plus four of our own

Status: active. Date: 2026-11-25.

The agent has `read`, `write`, `edit`, `bash` in the sandbox and four tools of our own (`perft_check`, `submit`, `experiments`, `run_job`, later `lichess_losses`) in a TypeScript extension that forwards to the orchestrator's local API. Only what the sandbox cannot do becomes a tool: querying the referee, reading the ledger, acting outside the sandbox. Few tools because their descriptions travel with every call and a small model chooses better among a few clear options.

## #13 Event-driven rhythms and spend spread over the hours

Status: active. Date: 2026-11-25.

The CPU works all the time (games, self-play), the LLM wakes up on events (a verdict, the end of a job, Lichess losses) and every so often rewrites its own strategy. The budget of 2 $ a day is spent in hourly shares: a wake-up with no share left waits, the machine does not. Rejected: waking on a fixed schedule, which either wastes calls when nothing has changed or leaves the CPU idle.

## #14 Deploy in Compose with ephemeral containers, data at the same path

Status: active. Date: 2026-11-25.

The server runs two fixed services, `core` (orchestrator and referee in the same process, so the ledger has a single writer) and `api`; sandbox, builds, arena, engines and jobs are ephemeral containers created by `core`. A single container would not do: every engine must be isolated from its opponent. The data is mounted at the same path as on the host, so the bind mounts of the child containers work the same way in development and production. The server is a fanless MacBook Air M4, not a Mac mini: game concurrency is tuned with a load test before trusting the estimates.

## #15 Trusted mirror and memory outside the genome

Status: active. Date: 2026-11-25.

The genome repository belongs to the agent: it can rewrite tags, delete objects, add hooks or a `core.fsmonitor` that git would run on the host. That is why git never runs on the host against the genome, and the history that matters lives in a bare mirror written only by the orchestrator: the referee builds from there and every session restarts from there. `NOTES.md` and `STRATEGY.md` move out of the genome into `/memory`: inside the genome a lesson learned from a rejected experiment would vanish with the reset. The agent overwrites them in place, so their history is kept the same way (from cycle 6): a bare repository only the orchestrator writes, committed from a container that mounts the memory read-only, never by git on the host against the agent's files.

## #16 Testing the full session with a fake model

Status: active. Date: 2026-11-25.

The chain of pi, extension, sandbox, tools, mirror, referee and ledger is tested without spending: a local OpenAI-compatible endpoint answers with a script of tool calls, configured in pi as a provider. The cost per call comes from pi itself, which computes it from the model's prices: the same field used with OpenRouter.

## #17 Anthropic or OpenRouter provider, Anthropic by default

Status: active. Date: 2026-11-25.

The key available is an Anthropic one, so the default becomes Anthropic directly; OpenRouter stays selectable with `DARWIN_LLM_PROVIDER`. The switch touches no other code: pi knows both providers, each with its own model ID (`claude-haiku-5-5`, `anthropic/claude-haiku-5.5`) and its own key variable, and computes the cost from the same prices (0.10 $ and 0.50 $ per million tokens, cache reads 0.01 $). It supersedes the choice of OpenRouter in #5.

## #18 Libraries for the agent, no GPU, disk quota on the internal disk

Status: active. Date: 2026-11-25.

The agent gets a few vendored Rust crates (rand, rayon, bytemuck) and Python with PyTorch CPU and numpy, all inside the image and so offline. Without libraries, training a network would have to be written from scratch in Rust, the point where a cheap model risks getting stuck; with PyTorch it is the standard path, the same as Stockfish, which trains in PyTorch and embeds the network in the engine. What the network knows still comes from the games. The engine stays in Rust and the weights have to be embedded in the binary, because the referee runs it on its own.

No GPU: Docker on a Mac does not see the Apple GPU, and using it would mean running the agent's code on macOS outside the sandbox. Also rejected: a trainer of our own to which the agent only passes data, which would make the agent configure instead of build. For small NNUE-style networks the CPU is enough; this reopens if training becomes the bottleneck.

Jobs write to the server's internal disk (120 GB free) with a quota of 10 GB per job and 40 GB in all: a job over its quota is stopped, a new one is refused when the quota is full, and the agent deletes old outputs itself. The external disk was rejected: it is shared with a media library, nearly full and connected by cable, so it can disappear from under `core`.


## #19 In Compose the ledger lives in a Docker volume; every container carries its instance

Status: active. Date: 2026-11-25.

The first start on the server showed SQLite connections that did not see rows just written by another connection of the same process, with foreign key errors and `core` restarting. The cause is Docker Desktop's shared folder: the WAL shared memory does not stay coherent there, the network filesystem case SQLite advises against. The ledger moves to a Docker volume, inside the virtual machine; the rest of `data/` stays in a folder because it has to be mounted into the engine containers at the same path. Rejected: the classic journal without WAL, which relies on file locks that give no more guarantees on the same share.

Stopping `core` left arena, engines and sandbox running. Every container now carries the instance label (`prod` in Compose, `dev` in development, one of their own for tests) and at startup `core` removes those of its instance without touching the others.

## #20 Public, bilingual site, commentary for visitors kept apart from the agent

Status: partly superseded by #23. Date: 2026-11-25.

The dashboard goes public (Cloudflare Tunnel on `darwin.esse.dev`) and bilingual, Italian and English. Code, prompts and the agent's texts stay in English: every text of the agent is translated into Italian and kept, hypotheses, lessons, live thoughts, strategy, notes and instructions; only the code stays as it is (from #23).

The readable commentary on games and verdicts is written by Haiku from verified data (Stockfish evaluations, match statistics), never by reading the game by eye. It has a budget of its own, 0.20 $ a day, and the agent does not read it: a second model explaining the games to it would change the nature of the experiment. The referee's commentary comes when the match is over and not every few games, because halfway through a match the numbers swing and the text would say things the verdict later contradicts.

## #21 Live page with balanced columns, and Elo with its margin

Status: active. Date: 2026-11-25.

The redesign of the Live and Evolution pages follows concept B (`docs/concepts/concept-b-revisione.html`): variant a1 ("Rifinita") for the Live page, A for Evolution. Rejected: B (the Live page as a game plus a panel, history grouped by generation) and C (a single column like a newsfeed), which changed the structure to solve a problem of quantity and writing; also rejected the aesthetic versions a2 (no panels) and a3 (instrument grid).

The Live page holds nothing that grows with the history: three columns ending at the same height, the last five generations, the last three results, fixed, with a link to Evolution or to the bot's Lichess profile. An in-place "Show more" was tried and removed: it lengthened one column and unbalanced the page again.

The headline strength number is the absolute Elo against Stockfish with its 95% margin, and the chart shows error bars and the band where generations overlap. The real margins (± 120-140 Elo with today's games) showed that the drop from 1,193 to 1,129 was noise, while the site presented it as a decline next to gains of +24 and +42. The gain over the previous champion stays, secondary and explained; the Lichess performance is shown from five games up.

The short titles of the experiments are written by the commentary worker at submission, like the translation, not by the agent: the agent's work does not change and the titles stay out of what it reads.

## #22 Updating the server by draining core before the restart

Status: active. Date: 2026-11-25.

Restarting `core` interrupted everything: the Lichess game in progress lost on time (and rated), the agent's session marked as an error, the trial run again from the start. `make deploy` asks `core` to drain with a file in the data folder, because the host already mounts it and no port has to be opened: `core` starts no new sessions or games, waits for the ones in progress to finish (a session lasts at most 40 minutes, a 3+2 game about ten) and answers with another file; only then are `core` and `api` recreated.

The trial in progress is neither waited for nor resumed: a match can last an hour, and resuming it from the last batch would mean saving the games played and restarting from the right openings, only to save compute time. This reopens if restarts become frequent. `core` also handles SIGTERM: before, it died at once without closing anything.

## #23 Everything translated into Italian except the code

Status: active. Date: 2026-11-25. Partly supersedes #20.

At the author's request the agent's live thought, strategy, notes and instructions are translated too; only the code stays in English, because two versions of the code would make no sense. The measured cost is low: a translation costs about 0.0001 $, there are about 200 thoughts a day, the notes change every session but are translated at most once an hour, the latest version. About 3 cents a day in all, within the unchanged commentary cap of 0.20 $.

The Italian thought arrives a few seconds after the original: in the meantime the site shows the English with its label. Every version of a memory file has its own translation, tied to the CRC32 of the text, so the site never shows the translation of an old version next to a new original. Above 16,000 characters a file stays in English: translating it at every change would become a long and expensive call.

## #24 Visual identity: one colour for each thing, animated ASCII states

Status: active. Date: 2026-11-25.

The choice is variant E of concept C (`docs/concepts/concept-c-identita.html`), palette "e": neutral background, minimal finishes (one-pixel rules instead of shadows, labels in monospaced small caps, dashed separators), and one colour per subject, the same across the site: the champion's strength in blue, generations in violet, the verdict in green, the spend in amber, whatever is live in coral. Panels are lightly tinted with the colour of their subject. Fonts unchanged, Geist and Geist Mono.

Loading, error and empty states are multicolour ASCII animations: a knight jumping in an L, the king trembling, the pieces dropping into the starting position. With reduced motion on they stay on a still frame; they are hidden from screen readers, and the sentence next to them states the state.

Rejected after five rounds: A "Terminale", B "Taccuino", C "Arcade" (too colourful and overdone), D and its versions (too monochrome: every version was a single colour in many shades), e2 "Pop" and e3 "Terra".

## #25 The agent reasons at high effort; no subagents for now

Status: active. Date: 2026-11-25.

The agent ran at effort `low` (below Haiku 5.5's default `medium`) and for four generations had made only small evaluation tweaks; the changes worth hundreds of Elo (quiescence, time management) it had tried once and abandoned. It moves to `high`. The cost stays minimal: at `low` a session cost about 0.003 $, and the limit on the number of sessions is the referee, not the budget, of which we used less than 4%. To be measured after the first sessions; back to `medium` if the cost rises a lot with no visible benefit.

Rejected: lower-effort subagents for the mechanical work. Today sessions are short (6-7 model calls, one 500-line file), so there is no context to protect and no cost to save, and they would have added concurrent processes on the same genome, spend accounting and per-session limits. This reopens when sessions get long (network training, large rewrites) or hit the limits of 40 minutes, 80 actions or 0.25 $.

## #26 The agent is invited to be curious, with no hints about where

Status: active. Date: 2026-11-25.

After 29 sessions the agent had launched no job, written no tool and kept the engine in one file: the system prompt asked for "one focused change" and a submission every session, and it had learned that ending without one was a failure. The prompt now asks it to work on what it thinks matters most, says nothing ties it to small edits, one file or its past way of working, and that a session may end without a submission when what it learned is written down; `/memory` is where tools it wants to keep live, since unsubmitted work in the genome is lost. The reflection also asks what it has never tried. Nothing names a technique: where it goes is its own choice. To be judged on jobs, tools and the variety of changes over the next reflections.

Rejected: dedicated exploration sessions chosen by the orchestrator, which decide for the agent when to be curious; showing it statistics about itself, a nudge in a direction it did not choose.

## #27 The agent knows its limits, and unsubmitted work is kept

Status: active. Date: 2026-11-26.

Session 30 slept 15 minutes inside the session waiting for its own test match: it did not know the session closes after 40 minutes (it knew only the tool-call limit), nor that a job starts from a copy of its working tree and wakes a new session when it ends, nor that its unsubmitted changes would be thrown away. The session prompt now states the start time and the three limits (40 minutes, 80 tool calls, 0.25 $) and that the referee waits while the session is open; the system prompt says what a job sees and that its end wakes a session. A session that ends without a submission (abandoned, stopped by a limit, failed) leaves its changes as `refs/darwin/wip-<id>`, never judged. The 40 minutes stay: waiting belongs in jobs, and the limit is reviewed once sessions cut short while doing useful work show up.

Rejected: raising the limit to 90 minutes, which would only lengthen the waits inside sessions while the referee sits idle; reopening a session when its job ends, which would bring back a context the design keeps fresh on purpose.

## #28 A page for every session, as a log

Status: active. Date: 2026-11-26.

At high effort the agent writes almost no text between calls: session 30 had no thought and 21 tool calls, so the Live page showed a thought from four hours earlier while the agent built, wrote itself a match tool and played 60 test games. Everything was already in `agent_events` and on the stream; the site threw it away. The choice is variant A of concept D (`docs/concepts/concept-d-lavoro.html`), "Registro": every session has a page, `#/sessione?id=N`, with one line per tool call in order, phrased for a person ("legge main.rs, righe 360-520", "compila", "aspetta 15 minuti"), the exact command and answer one click away, and the thoughts and the reasoning inline. The sentences come from fixed rules on the payload, not from a model: they cost nothing, and when a rule does not know a command it says "esegue X" with the first line of the answer, never a wrong sentence. The rules that read the output of `/memory/match.py` depend on a tool the agent wrote: if it renames it or changes its format they fall back to the plain line.

Entry points: on the Live page the middle column shows the tail of the log when no referee game is on (the action in progress, the countdown of a wait, the last lines), one line under the board when a game is on, and "session #N in progress" in the top bar; every experiment in Evolution, the diff of an experiment in Code and a line at the top of Mind ("at work right now") link to it. The page lives outside the five tabs and outside Mind: Mind is what the agent knows, slow and versioned; a session is what it does, minute by minute, tied to one experiment.

The ledger changes that went with it: tool arguments are stored as a JSON object with each string cut on its own (a repr cut at 2,000 characters lost the end of long edits), every call and result carries pi's `toolCallId`, and the model's reasoning is stored as `reasoning`. pi asks Anthropic for adaptive thinking with `display: "summarized"` (its default, no option changes it), so every reply carries the summarized thinking; it is shown in English with its caption and not translated, because it comes with every reply and would multiply the commentary spend. Old rows keep their format and the page reads both.

Rejected: B "Racconto" (the session cut into five steps, the calls closed inside them), which hides the order of what happened behind a grouping that the rules would get wrong on unusual sessions; C "Due colonne" (timeline and detail side by side, like a debugger), which needs a wide screen and a selection to read anything, and on a phone collapses into A with an extra click. Not done: the full output of a command, which is not stored anywhere beyond its first 2,000 characters.

## #29 One joint Elo estimate for every generation, and a ladder that starts where the champion should be

Status: active. Date: 2026-11-26.

gen-14 scored 0.95 against Stockfish 1600, so the ladder climbed to 2000 (0.65) and rated it 2,108 ± 130. gen-15 scored 0.863 against 1600, the ladder stopped there because it climbs only from 0.9, and rated it 1,919 ± 166, although gen-15 had beaten gen-14 by +84 ± 34 in the match that promoted it. With 40 games per rung, which rung decides a rating was left to noise around 0.9, every generation was measured alone, and the chart showed a drop of almost 200 Elo that the games do not support.

The Elo the site shows is now one maximum-likelihood fit over all the evidence: every rung of every rating snapshot, with the anchors fixed at their nominal Elo, and the SPRT match that promoted each champion over its parent. Logistic model, a draw as half a point, 95% margins from the inverse Hessian. On the production ledger it puts gen-15 at 2,079 ± 75 above gen-14 at 2,006 ± 57, and every margin from gen-3 on falls to ± 50-80, because each generation borrows the games of its neighbours through matches of hundreds of games. It is derived, not history: computed when the API reads it and kept in the process until a new snapshot or generation appears. `rating_snapshots` keep each measure as it was taken, and the site shows it next to the estimate as "against Stockfish alone".

The ladder starts where the champion is expected to be: its parent's joint Elo plus the gain of the match that promoted it. It plays the rung just below and the rung just above that, then climbs while the highest rung played still scores 0.9 or more and steps down while the lowest scores 0.1 or less; without an expectation (the first ratings) it starts at 1320 and climbs as before. gen-15 would have been expected at about 2,105 (gen-14 then at 2,020 ± 60, plus 84) and played 2000 and 2400 instead of stopping at a near-whitewash of 1600. Rungs and their combination into the snapshot are unchanged; from now on each rung records its number of games.

The data that enters:
- a match counts as points out of games, not as its pentanomial: the rungs kept only their score, and one model for all the evidence keeps the fit consistent. The cost is margins about a sixth wider on drawish matches;
- gen-1's match was against the random player, which has no Elo, and a rejected candidate would add an unknown with nothing to say about the generations: both stay out;
- gen-1 and gen-2 were promoted before the ladder existed and never met an anchor. Their only link is a chain of near-whitewash matches (22-2-0 and 23-1-0) that gives them -97 ± 601 and 448 ± 490 and adds nothing to the others, so the matches older than the first rated generation stay out and the two remain "not rated";
- a generation that only ever won, or only ever lost, against everything it met has no finite estimate, like one with no path to an anchor: neither gets one.

The limit: the fit takes a gain over the parent to be worth the same against Stockfish. Self-play gains often shrink against other opponents, and an SPRT stopped early at H1 overstates the gain it measured; the margins do not include that. On today's ledger the evidence fits the model roughly, with more spread than it assumes (chi-square 33 over 19 degrees of freedom): the largest misfits are gen-14 losing 3.5 points to the 1320 rung where the fit expects 0.8, and gen-15 scoring 34.5 against 1600 where it expects 37.6. To be checked as the chain grows.

Rejected: more games per rung only, which narrows each measure at the cost of hours of CPU per champion but still lets noise around 0.9 choose the rung and still measures every generation alone; leaving the climb rule as it was, which keeps spending the rating's games on the rungs a strong champion crushes (gen-15 won 40 of 40 against 1320) and lets the rung that decides be chosen by a few games either side of 0.9; weighing each match by its pentanomial variance, a second model for a sixth of margin.

## #30 The bot's games are reviewed on the site, derived from the stored evaluations

Status: active. Date: 2026-11-27.

The site showed the bot's last three games and sent visitors to Lichess, where its games have no analysis. Every finished game now has its own page on the site, with a paged list to reach it. Moves are judged the way Lichess judges them, on the winning chances they gave away with Lichess's thresholds, so the marks read the same as on Lichess. The judgements, the totals and the turning point are derived when the API reads the game, from the Stockfish evaluations already stored for the commentary: nothing new is computed on the server or written to the ledger, and a change to the rule applies to every past game at once.

Rejected: linking to Lichess only, which gives the visitor the moves without the analysis; storing the judgements, which duplicates what the evaluations already determine and would need a migration whenever the rule changes.
