# Cycles

One cycle per closed unit of work, most recent first. It keeps the last ~15 cycles; older ones move to `docs/archive/`.

## Cycle 4: visual identity, updates without interruptions, an agent that thinks harder (2026-11-25)

**Goal**: make the site readable and recognizable, update the server without losing work, and get the agent out of the small tweaks it had been stuck on for four generations.

**Done**:
- Updates: `make deploy` drains `core` before recreating it (no new sessions or Lichess games, the ones in progress finish), and `core` handles SIGTERM; `make deploy only=api` restarts only the site and leaves `core` working.
- Translations: the agent's live thought, strategy, notes and instructions in Italian too, with refused translations avoided and retried. Commentary that tells human opponents from bots, move ordinals in Italian.
- Live page: follows one game to its end instead of jumping among the three running in parallel, our engine always at the bottom, the match wins next to the names.
- Visual identity: concept C in five rounds, variant E chosen (one colour per subject, loading, error and empty states animated in ASCII); loading centred on the page. Site changelog 0.3.0 and 0.4.0.
- Agent: knows where to find past attempts; reasons at effort `high` instead of `low`. Reflection is counted from the ledger: the in-memory counter reset at every restart of `core`, so the agent had never reflected; now it rereads the whole history (experiments, code of past attempts, Lichess losses).
- Outcome: the first real reflection (experiment 25) was followed by iterative deepening with MVV-LVA ordering (experiment 26), which became gen-8 with +416 ± 149 Elo over the champion and 1,488 ± 115 absolute Elo, up from gen-7's 1,259. At high effort a session costs 0.007-0.018 $, against about 0.002 $ at `low`; since the start of the experiment, 29 sessions for 0.14 $ in all.
- Lichess: after a 429 the bot waits as long as Lichess asks (response body or `Retry-After`), doubles the pause up to 4 hours when Lichess does not say, and logs the response. In production: at 22:44 Lichess still refuses challenges without saying how long to wait, pause up to 16 minutes; last game played at 19:59.

**Decisions**: #22-#25 (drain `core` before restarting, everything translated except the code, visual identity, high effort without subagents); #20 partly superseded by #23.

**Next step**: check that Lichess challenges resume and, if the limit holds, find out which limit it is; measure the cost and yield of high effort over a day (#25). Queued for the referee: quiescence (experiment 29), behind mate scores by distance (28).

## Cycle 3: running on the server, Lichess and the public site (2026-11-25)

**Goal**: the first paid sessions, then the experiment running 24/7 on the server with the Lichess bot and a dashboard that can be watched from outside.

**Done**:
- First paid sessions: `submit` accepts work the agent has already committed, in genesis and first steps the next session waits for the verdict (work on the old base ended up `stale`), the prompt explains every verdict.
- Lichess bot written by us, always on the reigning champion: losses analysed by Stockfish and handed to the agent as lessons, weak opponents while the rating is provisional, another challenge right away when one is declined, trials limited to N games.
- The agent's lab: vendored Rust crates, PyTorch CPU for training, disk quotas for jobs.
- The server: ledger in a Docker volume after rows went unseen between SQLite connections, containers labelled per instance and cleaned up at startup, fixes from the first hours (opening generator, submissions identical to the base, ratings interrupted by a restart). A single `data/` and a single `.env` at the root.
- Site: Evolution, Code, Mind and Lab pages, a bilingual site with commentary on games and verdicts written by Haiku, public on darwin.esse.dev through a Cloudflare Tunnel. Redesign of the Live and Evolution pages with concept B (balanced columns, Elo with its 95% margin, short experiment titles, live SPRT progress), changelog 0.1.0 and 0.2.0.
- Outcome: five generations in the afternoon; from gen-3 on the champion has an absolute Elo against Stockfish, between 1,130 and 1,190 with margins of ± 120-140.

**Decisions**: #17-#21 (Anthropic provider by default, libraries and no GPU, ledger in a volume and instances, public bilingual site with commentary kept apart from the agent, Live page with balanced columns and Elo with its margin).

**Next step**: update the server without interrupting the session and the game, translate the rest too, the site's visual identity.

## Cycle 2: the complete pipeline, locally (2026-11-25)

**Goal**: build every piece of the experiment (M1-M4) and start on deploy and anchors (M5, M6), so that only the paid trials and going live remain.

**Done**:
- M1 Referee: clean build from a commit, perft on random positions with a per-move breakdown, smoke, games played by fastchess in the `arena` container with one container per engine, PGNs re-read with python-chess, pentanomial SPRT in batches computed by us, the random player as the first anchor, gates per phase. Tested with real UCI engines, including deliberately faulty ones; a shim removes the containers of engines that ignore `quit`.
- M2 Ledger: tables, initial migration and store; SQLite in WAL mode, `core` writes and the API reads.
- M3 Orchestrator: pi in RPC mode from an empty folder with automatic loading off, an extension that brings `read`/`write`/`edit`/`bash` into the sandbox and forwards `perft_check`, `submit`, `experiments`, `run_job` to the local tools API; trusted mirror the referee builds from, agent memory outside the genome, event-driven wake-ups, periodic reflection, spend in hourly shares. A complete session tested end to end with a fake model.
- M4 Dashboard: read-only API (overview, game in progress from fastchess's events, SSE) and direction D of the concept, with the cburnett pieces and their license.
- M5, partly: a single `darwin-backend` image for the `core` and `api` services in Compose (`make up`), data mounted at the same path as on the host. Tested locally.
- M6, partly: a ladder of Stockfish 17 anchors at limited strength (`UCI_Elo` from 1320 to 2800); every new champion is measured after its promotion and the dashboard shows the absolute Elo, or the Elo relative to the random player below the ladder.

**Decisions**: #9-#16 (lessons from Lichess, fastchess plays and the referee judges, pi as the harness, tools, rhythms, deploy in Compose, trusted mirror, tests with a fake model); #5 partly superseded by #11.

**Next step**: the 3 paid trial iterations with measured cost, which are also the first acceptance of a real Rust genome. Then deploy on the server, the Lichess bot, a book filtered by Stockfish (see `ROADMAP.md`).

## Cycle 1: scaffold and design (2026-11-24)

**Goal**: settle the vision, the trust boundaries and the stack, and choose the dashboard's direction before writing code.

**Done**: scaffold of backend, dashboard and Docker sandbox, genome `gen-0` created and built offline in the sandbox. Dashboard concept with four directions, D chosen, with the move list and the piece set.

**Decisions**: #1-#8 (division between LLM and network, immutable referee, SQLite, append-only ledger, Haiku through OpenRouter, Lichess as an external measure, dashboard D, cburnett pieces and Lucide icons).

**Next step**: referee, ledger, orchestrator.
