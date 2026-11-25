# darwin-chess

**English** · [Italiano](README.it.md) · [Live site](https://darwin.esse.dev)

An LLM agent writes a chess engine in Rust from an empty crate and keeps evolving it on its own. A change survives only if it wins real games against the previous version, judged by a referee the agent cannot see or touch.

Status: running 24/7 since 2026-11-25, with the games, the agent's reasoning and the spend shown live on the site.

## Question

How far does a cheap, autonomous LLM agent get at building a chess engine when every change it makes has to win games to survive, and nothing it writes can bend the measurement?

## Short answer

Results as of 2026-11-25, after the first day:

- The champion is **gen-8**, at about **1,488 ± 115** absolute Elo against limited-strength Stockfish (95% margin).
- gen-8 came from **iterative deepening with MVV-LVA move ordering**, worth **+416 ± 149** Elo over gen-7. Each evaluation tweak before it had added between 17 and 42 Elo.
- The agent is Claude Haiku 5.5 running in pi at effort `high`. A session costs about 0.01-0.02 $; the first 29 sessions cost 0.14 $ in all. The bottleneck is the referee's CPU, not the budget.

## Hardware and setup

- A MacBook Air M4 at home: 10 cores (4 performance, 6 efficiency), 16 GB, no fan, Docker Desktop. No GPU: Docker on a Mac cannot see it.
- The Docker VM gets 8 of the 10 cores, pending a one-hour load test: 2 for the agent's builds, 6 for games (3 in parallel). Under sustained load the fanless Air slows down, and the mixed cores add noise, so a verdict needs more games.
- Agent: Claude Haiku 5.5 (Anthropic by default, OpenRouter as an option) inside [pi](https://www.npmjs.com/package/@earendil-works/pi-coding-agent), pinned and driven in RPC mode, with a daily budget of 2 $ spread over the hours.
- Backend: Python 3.13, FastAPI, SQLAlchemy 2.0 async, Alembic, python-chess (uv). Ledger: SQLite.
- Frontend: React 19, TypeScript strict, Vite, Tailwind v4, shadcn/ui, TanStack Query (pnpm). Bilingual dashboard, public at https://darwin.esse.dev through a Cloudflare Tunnel.
- Games played by fastchess; anchors are a random player and Stockfish 17.

## Method

- **Genome** (`genome/`): the engine in Rust, owned by the agent. It is a separate git repository: every accepted commit is a generation.
- **Sandbox**: the agent's commands run in a Docker container with the Rust toolchain, a few vendored crates and PyTorch CPU, with no network, no Stockfish and no referee code.
- **Referee**: trusted code outside the sandbox. A candidate goes through the gates in order of cost: clean build, perft on random positions (standard counts are known and could be hardcoded), smoke games, then the match. Against the champion the match is a pentanomial SPRT (elo0 0, elo1 10, alpha and beta 0.05) at 8+0.08, played in batches; the referee re-reads every PGN with python-chess and computes the SPRT itself. Every engine process runs in its own container (no network, 1 CPU, read-only binary).
- **Anchors**: every new champion climbs a ladder of Stockfish 17 at `UCI_Elo` 1320, 1600, 2000, 2400 and 2800; the informative rungs are combined, weighted by precision, into the absolute Elo with its 95% margin.
- **Orchestrator**: wakes the agent on events (a verdict, a finished job, a batch of Lichess losses). Every iteration starts from a fresh context; state lives in the genome's git history and in the ledger. Every 10 iterations the agent rereads the whole history and rewrites its own strategy.
- **Lichess**: a bot plays the reigning champion around the clock. Lichess never judges candidates; Stockfish analyses every loss and the agent receives it as a lesson.
- Division of roles, by design: the LLM builds and optimizes the machine, and chess knowledge in the evaluation is meant to come from a network trained on the engine's self-play, not from the LLM's memory.

Details in [Architecture](docs/ARCHITECTURE.md), [Decisions](docs/DECISIONS.md), [Ledger schema](docs/DATABASE_SCHEMA.md), [Cycles](docs/CYCLES.md) and [Roadmap](docs/ROADMAP.md).

## Results

| Date | Champion | Absolute Elo | Note |
|---|---|---|---|
| 2026-11-25 | gen-3 to gen-7 | 1,129 to 1,259 | small evaluation tweaks, +17 to +42 Elo each, margins of ± 120-140 |
| 2026-11-25 | gen-8 | 1,488 ± 115 | iterative deepening with MVV-LVA ordering, +416 ± 149 over gen-7 |

The agent spent four generations on small evaluation tweaks at effort `low`. Two changes came just before the jump: reasoning effort raised to `high` (DECISIONS #25), and the periodic reflection counted from the ledger: its in-memory counter reset at every restart, so the agent had never reflected. The first real reflection (experiment 25) was followed by iterative deepening (experiment 26), which became gen-8.

The full history, generation by generation, is on the [live site](https://darwin.esse.dev) and in [CYCLES](docs/CYCLES.md).

## How to reproduce

You need Docker, uv, pnpm and an Anthropic (or OpenRouter) API key. Every session that calls the model costs money, within the daily budget.

```bash
make install
cp .env.example .env           # at the root; then set DARWIN_HOME and DARWIN_LLM_API_KEY
make images                    # sandbox, arena, anchors, test engines
make db-migrate
make genome-init               # creates the empty genome (gen-0)
make run-sessions n=3          # a few trial sessions, then stop
make dev                       # API on :4730, dashboard on :4731
```

`make run-core` runs the experiment without a session limit; `make up` runs it in Docker Compose (`core` and `api`). `make deploy` updates a remote server over ssh without interrupting the agent's session or the Lichess game in progress: it reads `DEPLOY_HOST` and `DEPLOY_DIR` from an untracked `Makefile.local`. `make check` runs format, lint, typecheck and tests.

## Limits

- One run, one model, one machine: the results are a single trajectory, not a distribution.
- The absolute Elo is measured against Stockfish at limited strength, with margins above ± 100; it is not a FIDE or Lichess rating.
- Matches use a short time control (8+0.08): gains there may not carry over to slower games.
- Haiku knows engine techniques from its training: what the experiment measures is how well an agent applies known ideas under a strict referee, not discovery.
- The opening book is generated by the referee (random moves at equal material), not yet filtered by Stockfish.
- The fanless laptop and its mixed cores add noise to the games; the referee compensates with more games, not with a correction.

## License

[MIT](LICENSE), except the cburnett chess piece images in `frontend/public/pieces/cburnett/`, which keep their GPLv2+ license.
