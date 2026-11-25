# Code conventions

Rules specific to this project.

## Language

| Level | Language |
|---|---|
| Identifiers, file names, branches | English (route ids and i18n keys keep the Italian page names, see Glossary) |
| Code comments, docstrings, test names | English |
| `README.md` | English, canonical; `README.it.md` is its Italian mirror, updated in the same commit |
| `docs/`, `CLAUDE.md`, `.claude/rules/` | English |
| Commit messages | English, Conventional Commits |
| Agent-facing text (`seed/*.md`, prompts in `darwin.orchestrator` and `darwin.commentary`, tool descriptions in `agent/darwin-extension.ts`) | English; it enters the model's context, so changing it changes the experiment |
| Dashboard UI | Italian and English, typed dictionaries in `frontend/src/i18n/` |
| `CHANGELOG.md` | Italian, shown on the site; `CHANGELOG.en.md` is its English twin |
| `docs/concepts/` | Italian, the language of the UI they mock |

The exceptions are declared in `.prose-allow`. `make lint` runs `scripts/check-prose.py`, which fails on Italian prose outside them and on a README pair out of step, and ruff's `D100`, which requires a module docstring in `backend/src/darwin`.

## Glossary

Domain terms and their English rendering. Docs, comments and commits use only these.

| Italian | English | Notes |
|---|---|---|
| arbitro | referee | the trusted code that judges candidates |
| campione | champion | the generation in charge |
| candidato | candidate | a commit submitted for judgement |
| generazione | generation | `gen-N`, an accepted champion |
| esperimento | experiment | one agent session, `exp-N` |
| genoma | genome | the engine repository the agent owns |
| registro | ledger | the append-only SQLite database |
| riflessione | reflection | the periodic session that rewrites the strategy |
| svuotamento | drain | what `make deploy` asks of `core` before a restart |
| ancore | anchors | the fixed opponents that measure absolute Elo |
| Diretta, Evoluzione, Codice, Mente, Laboratorio | Live, Evolution, Code, Mind, Lab | UI section names: Italian labels in `it.ts`, English in `en.ts`. Docs and comments use the English label; route ids and i18n keys keep the Italian name (`#/codice`, `nav.codice`) |

## General

- Line length 100.
- File names: `snake_case` in Python, `kebab-case` in the frontend.

## Python backend

- Type hints everywhere, mypy strict green.
- Async for all I/O: database, engine subprocesses, LLM calls.
- Typed errors per domain (`RefereeError`, `BudgetExceeded`, ...). Never `except: pass`: an unexpected error closes the experiment with `status = error` and the traceback in the ledger.
- Structured logging with `logging`, one logger per module. Events the dashboard shows go to `agent_events`, not to the logs.
- Configuration only from `darwin.config.Settings` (`DARWIN_*` variables), never scattered `os.environ`.
- At most ~300 lines per file.

## Referee

- No imports from `darwin.orchestrator` or `darwin.api`: it receives a binary and returns a verdict.
- Every engine process runs in its own ephemeral container: no genome binary ever runs on the host.
- What the agent is shown is explicit (the public `detail`), never raw internal output.

## React frontend

- Function components, features in `src/features/<name>/` with their own hooks.
- TanStack Query for server state, `EventSource` for live data, `useState` for UI state.
- Icons from Lucide only (`lucide-react`, the same set as the shadcn components): one stroke width, 16 px in text and 20 px in controls, and only where they add meaning.
- Chess pieces: the cburnett set, SVGs in `frontend/public/pieces/cburnett/` with their license file (GPLv2+, Colin M.L. Burnett); nothing loaded from external CDNs.
- Every view handles loading, empty, error and success.
- Explicit `cursor-pointer` on interactive elements (Tailwind v4 removes it from buttons).
- No `max-width` on content. Mobile designed from the first screen.
- At most ~200 lines per component.

## Tests

- Backend: pytest. Integration tests on the real SQLite ledger in a temporary folder, never a mocked database.
- Referee: tests run against a real UCI engine (a reference engine in the sandbox), not canned answers.
- LLM calls only behind the `llm` marker and only in explicit runs: they cost money.
- Frontend: critical components only.

## Cleanup

- No dead code, no TODO without a reference in `ROADMAP.md`.
- New code follows these rules; old code is fixed when its area is touched.
