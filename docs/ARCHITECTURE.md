# Architecture

## Overview

A cheap LLM agent starts from an empty Rust crate and builds a chess engine, improving it generation after generation with no human in the loop. The experiment measures how far an autonomous agent gets when every change it makes has to win real games to survive. The chess knowledge in the evaluation is learned by a network from the engine's self-play, not recalled by the LLM.

## The three worlds

| World | Where | Trust | Who changes it |
|---|---|---|---|
| Genome | `genome/` (separate git repository, ignored) | none | the agent only |
| Referee | `backend/src/darwin/referee/` | full | us only |
| Orchestrator | `backend/src/darwin/orchestrator/` | full | us only |

The trust boundary is the heart of the project. An LLM asked to make a number go up finds the easiest shortcut: hardcode the perft counts, give itself more time, kill the opponent's process. That is why the referee lives outside the sandbox and every engine runs isolated.

## Components

- **Sandbox** (`lab/`): Docker image with the Rust toolchain, a set of vendored crates (rand, rayon, bytemuck, pinned versions, resolved offline through `/.cargo/config.toml`) and Python with PyTorch CPU and numpy for training. No GPU: Docker on a Mac cannot see it. Jobs use the same image with 2 CPUs, 4 GB, at most 12 hours and a disk quota (10 GB per job, 40 GB in all, on the internal disk). The agent's commands run here, with no network, with `genome/` and `/memory` writable, the mirror and `/jobs` read-only, and the system filesystem read-only. A new container for every session.
- **Mirror** (`data/mirror.git`): trusted bare repository with every commit that matters (`refs/darwin/gen-N`, `refs/darwin/exp-N`, and `refs/darwin/wip-N` for the changes of a session that ended without a submission: kept, never judged). Only the orchestrator writes it; the referee's builds and the genome reset start from here, so the agent cannot alter or delete the champions' history.
- **Memory** (`data/agent/memory`): the agent's `NOTES.md` and `STRATEGY.md`, outside the genome, so they survive rejected experiments. The agent overwrites them in place, so after every session (and at startup) the orchestrator commits the whole folder to `data/agent/memory.git`, a bare repository only it writes, from a one-shot container that mounts the folder read-only: git never runs on the agent's files from the host. Python bytecode caches are left out; an agent's `.gitignore` hides nothing. The history before 27 November was rebuilt from the agent's tool calls (`scripts/rebuild-memory-history.py`).
- **Transcripts** (`data/agent/sessions/exp-<id>`): pi saves every session as a JSONL file (system prompt, session prompt, full reasoning, every tool call and result, in order). The ledger's events are cut for the site; the transcript is the complete record. Sessions before 27 November have none.
- **Ledger copy** (`data/backup/ledger.sqlite`): `core` copies the ledger every day with SQLite's online backup, because in Compose it lives in a Docker volume a host backup cannot read.
- **Referee** (`darwin.referee`): perft oracle on random positions (python-chess), clean build of the candidate, games and SPRT. fastchess plays the games in the `arena` container; the referee prepares the openings, re-reads every PGN with python-chess to check legality and result, and computes the SPRT itself in batches; after each batch it writes the match progress on the experiment (`progress`), which the Live page shows. Every engine process runs in its own ephemeral container (`--network none`, read-only binary, 1 CPU): a candidate cannot see or touch its opponent. The anchors are the random player and Stockfish 17 at limited strength (`UCI_Elo` 1320, 1600, 2000, 2400, 2800): every new champion plays the rungs just below and just above its expected Elo (its parent's joint estimate plus the gain that promoted it; the weakest rung when there is none), 20 pairs each, then climbs while the highest rung played is still a whitewash (0.9 or more) and steps down while the lowest is a rout (0.1 or less), and the estimates of the informative anchors are combined, weighted by precision, into the rating snapshot the ledger records. Below 1320 the champion stays "below the ladder". The dashboard always shows the absolute Elo with its 95% margin (DECISIONS #21), and that Elo is a joint estimate (`darwin.ledger.strength`, DECISIONS #29): one maximum-likelihood fit of the logistic Elo model, a draw as half a point, over every rung of every snapshot (anchors fixed at their nominal Elo) and the SPRT match that promoted each champion over its parent, with margins from the inverse Hessian. Generations the anchors cannot reach through that evidence get no estimate. It is derived, never recorded: the API computes it when it reads, and keeps it in the process until a new snapshot or a new generation appears.
- **Orchestrator** (`darwin.orchestrator`): the generation loop, the rhythms described below, the spending cap. The agent runs inside pi, driven in RPC mode.
- **Ledger** (`darwin.ledger`): append-only SQLite with experiments, verdicts, games, generations, LLM calls and agent events. Schema in `DATABASE_SCHEMA.md`.
- **Commentary** (`darwin.commentary`, inside `core`): Haiku writes for visitors, in Italian and English with a single call, a commentary on every Lichess game (based on Stockfish's evaluation of every ply) and one on every referee match (based on the results and statistics of its games), translates the agent's hypotheses and lessons into Italian and gives every hypothesis a short title in both languages (title and translation start at submission). It also translates every agent thought as soon as it is written and, at most once an hour, the current version of the strategy, notes and instructions (up to 16,000 characters). Only the code stays in English. A queue with a single consumer, its own cap of 0.20 $ a day, and a catch-up of anything missing at startup. Anthropic provider only. The agent never sees any of it.
- **API** (`darwin.api`): read-only, public FastAPI. `/api/overview` (phase, generations, experiment in progress, on trial and last verdict, spend, latest events), `/api/live` (one referee game followed to its end, read from fastchess's event stream under `data/matches`, with the match wins so far), `/api/lichess` (game in progress and the bot's latest games with their commentary), `/api/stream` (SSE: agent events and the game, checked every second). For the secondary pages `/api/generations/detail`, `/api/experiments`, `/api/sessions/{id}` (one session with its events in order, its outcome and the sessions on either side, at most 600 events), `/api/matches`, `/api/code/*` (tree, files and diffs of the genome, read from the mirror), `/api/mind` (the agent's memory and instructions) and `/api/lab` (totals, cost per generation, changelog).
- **Dashboard** (`frontend/`): bilingual (Italian and English, typed dictionaries in `src/i18n`), with the Live, Evolution, Code, Mind and Lab tabs. The Live page (DECISIONS #7, revised by #21) has three columns of the same height and nothing that grows with the history: on the left the latest generations with the Elo curve, in the middle one game at a time, with our engine always at the bottom, and the agent's thought, on the right the trial in progress, the latest results and the spend. One colour per subject, and loading, error and empty states animated in ASCII (DECISIONS #24). Light and dark theme from the system. Every session has its own page outside the tabs, `#/sessione?id=N` (DECISIONS #28): a log with one line per tool call, phrased for a visitor by fixed rules on the payload (`features/session/describe*.ts`, no model), the raw call and its answer a click away, thoughts and reasoning in between, the outcome at the end; a running session grows from the same event stream. The Live page shows the tail of that log in the middle when no referee game is on, one line under the board when one is, and a link in the top bar; Evolution, Mind and the diffs of the Code page link to it.
- **Lichess bot** (`darwin.lichess`, inside `core`): plays the reigning champion around the clock, accepts compatible challenges and sends its own to other bots, aiming at 1200 while its rating is provisional. It stays under Lichess's daily caps (200 challenges sent, refused ones included, and 100 games against other bots per account): it counts both over the last 24 hours in the ledger and stops at 150 challenges and 90 bot games. Both budgets are spread over the day in hourly shares with at most an hour's share in reserve: sent as fast as possible, the day's challenges ran out in five hours and the bot sat idle for the other nineteen. Incoming challenges are accepted from 1 to 10 minutes of base time, so some games are rapid; an opponent that already played 10 games in 24 hours is declined, so one account cannot keep the bot for itself. After a 429 it waits as long as Lichess says; if Lichess does not say, it stops sending challenges for a pause that doubles up to 4 hours. The engine runs in its own container with no network; the token stays in `core`. Written by us instead of the official `lichess-bot`, which would have had to start the engine containers and so hold Docker access next to the token. Two uses: the measure in the real world (performance computed per generation from rated games only, because the account mixes versions and a casual opponent can lose dozens of games in a row) and a source of lessons. Every loss is analysed by Stockfish on the referee's side, which marks where the evaluation collapses, and reaches the agent as a summary. Lichess does not judge candidates: too slow and noisy for that.

## The agent: pi and its tools

The orchestrator starts pi (`agent/`, pinned version) as a child process and drives it with JSON over stdin and stdout (RPC mode). pi runs in an empty folder with all automatic loading off (project configuration, extensions, skills, templates, context files, MCP): nothing the agent writes can be loaded by pi, only our extension. pi reasons at effort `high` (`DARWIN_LLM_THINKING`, DECISIONS #25). Every pi event (agent text, the model's summarized reasoning, tool calls with their arguments and results, token usage) passes through the orchestrator, which writes it to `agent_events` and `llm_calls`: the dashboard's captions and the spend tally come from there. pi also saves its own transcript of the session (`--session-dir`, a new folder per experiment, never resumed). pi does not enter the sandbox: only its commands do, while the API key stays with the orchestrator. pi's version is pinned because the project is young.

Standard tools, run in the sandbox: `read`, `write`, `edit`, `bash`. With bash the agent builds, tests, uses the genome's git and plays its engine against the champion rebuilt from its tag.

Our tools, added through a thin TypeScript extension that forwards every call to the orchestrator's local API (the logic stays in Python):

| Tool | What it does | Since |
|---|---|---|
| `perft_check` | the referee's perft on random positions; returns the first move with a wrong count | M3 |
| `submit` | submits the candidate with its mandatory hypothesis and ends the iteration | M3 |
| `experiments` | searches past experiments (hypothesis, outcome, margin) | M3 |
| `run_job` | starts a long CPU-only job (self-play, training) under a CPU cap, and reads its status | M3 |
| `lichess_losses` | reads the queue of losses with Stockfish's analysis | M5 |

Rule: only what the sandbox cannot do on its own becomes a tool. The agent has no network, no Stockfish, no access to the referee, to the `gen-N` tag (the orchestrator sets it) or to the time control.

## The life of a generation

1. **Observe**: the orchestrator resets the genome to the base (the last accepted commit) and builds the context: phase, champion, last verdict with the gate details, latest experiments, jobs, `STRATEGY.md` and the tail of `NOTES.md` (read through the sandbox: they are the agent's files).
2. **Implement**: the agent works with its tools within the session's limits (40 minutes, 80 tool calls, 0.25 $), which the session prompt states with the start time (DECISIONS #27); the orchestrator counts them from pi's events and stops the session when one runs out. A session that ends without a submission leaves its changes as `refs/darwin/wip-<id>` in the mirror.
3. **Submit**: `submit` commits the working tree in the sandbox, copies the commit into the mirror and queues it for the referee, which runs it through the gates in order of cost: build, perft, smoke (blitz games with no illegal moves, crashes or timeouts), the phase's match. If a new champion was born in the meantime, the candidate is first reapplied on top of it; if that conflicts, the experiment is `stale`.
4. **Learn**: the outcome goes into the ledger. If it wins it becomes `refs/darwin/gen-N` in the mirror. The next session receives the verdict and records the lesson with `lesson_for_previous`.

Every iteration starts with a fresh context: state lives in the genome's git and in the ledger, not in a growing conversation.

## Rhythms

What makes the system look alive must not cost money: the CPU works all the time, the LLM in bursts.

1. **Always on, zero cost**: evaluation games, self-play for training, the Lichess bot. There is always a game in progress on the dashboard.
2. **Event-driven wake-ups**: the agent starts when a verdict arrives, a `run_job` ends or a batch of Lichess losses comes in, not on a timer. In evolution, while the referee judges candidate N, the agent prepares N+1, with at most one candidate queued; in genesis and first steps it waits for the verdict, because there a candidate usually passes and moves the base, and work started on the old base would be lost.
3. **Periodic reflection**: every 10 iterations, counted from the ledger so that a restart does not reset the count, the agent rereads the whole history (experiments, code of past attempts, Lichess losses) and rewrites `STRATEGY.md`, choosing its next direction on its own.

The daily spend is spread over the hours (2 $ a day, about 8 cents an hour): when the hour's share is used up the agent sleeps and the machine keeps playing. Measured in operation: with Haiku 5.5 and caching a session costs 0.2 cents at effort `low`; at `high` an iteration costs 1-3 cents and a reflection about 3. The bottleneck is the referee's CPU, not the budget.

## Phases

The referee unlocks them, not the agent:

1. **Genesis**: build and perft only; there is no champion yet.
2. **First steps**: beat the random player; whoever does becomes `gen-1`.
3. **Evolution**: SPRT against the reigning champion.
4. **World**: every new champion goes to the Lichess bot.

## The genome contract

It lives in `seed/CONTRACT.md`, copied into the genome when it is created: binary `target/release/genome`, UCI protocol, a `perft <depth>` command with the per-move breakdown. The agent-facing files (`CONTRACT.md`, `STRATEGY.md`, `NOTES.md`) are in English because they end up in the prompt.

## Deploy

Development on a laptop, 24/7 operation on the server, reached over ssh. The server is a MacBook Air M4 at home (10 cores, 4 performance and 6 efficiency, 16 GB, no fan) with Docker Desktop, shared with other services.

```
server (Docker Compose, automatic restart)
├─ core          orchestrator + referee, a single Python process, with pi (Node)
│                and the Lichess bot; network: model provider and Lichess; the only service with Docker access
├─ api           FastAPI + built dashboard, reads the ledger
└─ ephemeral containers created by core:
   ├─ sandbox    one per iteration, pi's commands run here
   ├─ build      clean build of the candidate from a commit
   ├─ arena      fastchess, creates the engine containers
   ├─ engine     one per engine: no network, 1 CPU, read-only binary
   └─ job        the run_job jobs, under a CPU cap
```

- Startup: `.env` with `DARWIN_HOME` (absolute path of the repository) and the key, then `make genome-init` and `make up`. On the server `make up-public` also starts `tunnel`: `cloudflared` (pinned version) publishes the API, and the dashboard with it, at https://darwin.esse.dev without opening ports. The credentials of the `darwin` tunnel live in `~/.cloudflared` on the server, created once with `cloudflared tunnel login` and `tunnel create`; `tunnel route dns` created the DNS record. `core` applies the migrations at startup; `api` also serves the built dashboard.
- Update: `make deploy` on the laptop reads `DEPLOY_HOST` (an ssh host) and `DEPLOY_DIR` (the repository there, relative to its home, `darwin-chess` by default) from the untracked `Makefile.local` or the command line. It copies the code to the server, builds the images and asks `core` to drain (the file `data/control/drain`): no new sessions or Lichess games, the ones in progress finish. When `core` answers with `data/control/drained`, `core` and `api` are recreated on the new images. `make deploy only=api` recreates only `api`, for changes to the site, and leaves `core` working. The trial in progress is not waited for: after the restart the referee runs it again from the start, which costs only CPU. When stopped, `core` shuts down in order within 30 seconds (SIGTERM) and removes its instance's containers.
- Orchestrator and referee share a process: both are trusted, and the SQLite ledger keeps a single writer. The import rule guarantees the separation.
- The data (`DARWIN_DATA_DIR`: binaries, games, ledger, artifacts) is mounted into the containers at the same path it has on the host, so the bind mounts of the containers created by `core` and by `arena` resolve the same way in development and production.
- CPU, to be tuned with a one-hour load test: 8 of the 10 cores to the Docker VM; inside it, 2 for the agent's builds and 6 for games (3 in parallel). A training job takes cores from the games, it does not add to them. Without a fan the Air slows down under sustained load, and the mixed cores add noise to the games: a verdict needs more games, there is no systematic bias.

## Boundaries

- The referee imports nothing from the orchestrator: it receives a commit or a binary and returns a verdict.
- The agent never receives referee code or internal output, only the verdict and the public details (for example the move with a wrong perft).
- Only `core` and `arena` command Docker; `arena` runs fastchess (trusted code, not the agent's). Sandbox, engines, jobs and the Lichess bot never see the socket.
- No git command runs on the host inside the genome: the repository's hooks and configuration belong to the agent. Every git operation goes through a container.
- The agent's files are read from the host only through the sandbox or after checking that the resolved path stays inside the genome: a symbolic link could point anywhere.
- Only the referee uses Stockfish; it is never reachable from the sandbox.
- The API reads the ledger, it does not write.
