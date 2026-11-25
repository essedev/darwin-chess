# darwin-chess - Instructions for Claude

## What it is

An LLM agent (Haiku 5.5, through Anthropic or OpenRouter) writes a chess engine in Rust from scratch and evolves it on its own; a trusted referee decides which generations survive. It runs 24/7 on the server, a MacBook Air M4 at home. Vision and boundaries in `docs/ARCHITECTURE.md`.

## Stack

- Backend `backend/`: Python 3.13 + uv, package `darwin` (`referee`, `orchestrator`, `ledger`, `api`), FastAPI, SQLAlchemy 2.0 async on SQLite, Alembic, python-chess.
- Frontend `frontend/`: React 19 + TS strict + Vite + Tailwind v4 + shadcn/ui + TanStack Query.
- Sandbox `lab/`: Docker image with Rust, no network. Genome in `genome/` (separate git repository, ignored).
- Arena `arena/`: image with fastchess (pinned version) and the Docker CLI; it plays games by creating one container per engine. Anchors `anchors/`: random player on python-chess; `backend/tests/engines/` builds the faulty test engines on top of it.
- Agent (M3): pi in RPC mode, pinned version, with a TypeScript extension for our own tools.
- Ports (portsage): API 4730, Vite 4731.

## Commands

- `make install`, `make dev` (API + dashboard), `make check` (format, lint, typecheck, test)
- `make db-migrate`, `make db-revision msg='...'`
- `make run-core` (experiment), `make run-sessions n=3` (trial sessions): they need `DARWIN_LLM_API_KEY` and `make genome-init`
- `make up` / `make down`: production in Compose (`core` + `api`), with `.env` from `.env.example`
- `make deploy`: updates the server without interrupting the agent's session or the Lichess game in progress (drains `core`, then restarts). The target comes from `DEPLOY_HOST` (an ssh host) and `DEPLOY_DIR` in the untracked `Makefile.local`. `make deploy only=api` when only the site changed: restarts `api` and leaves `core` working. Never `docker compose up` by hand while it works
- `make lab-build`, `make genome-init` (creates `gen-0` from `seed/`, refuses if `genome/` exists)
- `make images` (sandbox, arena, anchors, test engines): needed before `make test`, which also runs the tests with real containers (marker `docker`, about a minute); `make test-unit` skips them

## Project rules

- **The trust boundary is never crossed**: no referee code in the sandbox, no genome binaries run on the host, the referee does not import from `orchestrator` or `api`. Anything that weakens isolation is discussed first.
- **The genome belongs to the agent**: do not edit `genome/` by hand. To change what a new genome receives, edit `seed/`.
- **LLM spend**: every run that calls the model costs money. LLM tests sit behind the `llm` marker; a batch of iterations starts only after its cost has been measured on a sample and approved.
- Public repository: code, comments, docs and commits in English; README.md is mirrored in README.it.md in the same commit.
- Agent-facing files (`seed/*.md`, prompts) are in English.

## Gotchas

- TypeScript 7: `baseUrl` no longer exists, aliases use `paths` only.
- `uv init --package` does not create `py.typed`: mypy uses `files = ["src", "tests"]`.
- In the `rust` image `CARGO_HOME` is `/usr/local/cargo`, not `~/.cargo`; the sandbox is offline (`CARGO_NET_OFFLINE`), so no crates are downloaded.
- Alembic on SQLite: `render_as_batch=True` is already on in `alembic/env.py`.
- Data and configuration live at the root: `data/` (ledger, mirror, binaries, games, agent memory, jobs) and a single `.env` (from `.env.example`), read both in development from `backend/` and by Compose.
- Containers created by the referee mount the data at the same path as on the host (`DARWIN_DATA_DIR`, absolute): a relative or different path breaks the bind mounts when `core` runs in a container.
- The server is a fanless MacBook Air M4, not a Mac mini: under sustained load it slows down.
- pi resolves relative paths against its own folder on the host: the extension (`agent/darwin-extension.ts`) maps them to `/genome` before every `docker exec`. Always start pi with the flags in `orchestrator/pi.py` (no automatic loading).
- The test `tests/orchestrator/test_docker_session.py` runs real pi against a fake model: it breaks if pi's RPC protocol or extension API changes, and it is the first check to run when upgrading pi.
- fastchess waits a fixed 60 seconds for an engine that ignores `quit`: that is why every engine goes through `arena/engine_shim.py`, which removes the container after 2 seconds. The arena image has only `python3-minimal` (no `uuid`, for example).
- The crates available to the agent resolve from `/opt/vendor` through `/.cargo/config.toml` in the `lab` image (read from any folder under `/`, even with a different `CARGO_HOME`). To add one: `cargo add` in the `vendor` stage of `lab/Dockerfile`, with a pinned version.
- PyTorch and rayon see all the machine's cores, not the `--cpus` cap: sandbox and jobs pass `OMP_NUM_THREADS` and `RAYON_NUM_THREADS`.
- In Compose the SQLite ledger lives in the `ledger` volume, not in `data/`: with Docker Desktop's folder sharing the WAL shared memory is not coherent, and connections saw rows late (foreign key errors). The API mounts the volume read-write even though it does not write: SQLite in WAL mode writes the shared index even to read. In development the ledger stays in `data/ledger.sqlite`, on the Mac's disk.
- Engine containers outlive their client: every run carries the label `darwin.run=<id>` and is cleaned up by label, even when it fails.
