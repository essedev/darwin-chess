# Ledger schema

## Conventions

- SQLite through SQLAlchemy 2.0 async (`aiosqlite`), Alembic migrations in `backend/alembic/versions/` with `render_as_batch` (SQLite does not alter constraints in place).
- **Append-only**: the ledger is the history of the experiment and no row is ever deleted or rewritten, so there is no `deleted_at` (the exception is explained in `DECISIONS.md`). A row changes only to close an open state (`finished_at`, `status`).
- Integer autoincrement PK `id`. UTC timestamps: `created_at` always, `finished_at` where there is a duration.
- Variable details (perft output, SPRT parameters, tool payloads) in `JSON` columns.

Every table is created by the initial migration. Timestamps go through the `UtcDateTime` type: stored in UTC without a time zone (SQLite has none), always returned with one. SQLite connections in WAL mode with foreign keys on: `core` writes, the API reads in parallel.

## Entities

### experiments

An agent session: an iteration (hypothesis, candidate, outcome) or a periodic reflection.

| Field | Type | Notes |
|---|---|---|
| id | INTEGER | PK |
| kind | TEXT | `iteration`, `reflection` |
| phase | TEXT | `genesis`, `first_steps`, `evolution` |
| base_commit | TEXT | commit the work starts from |
| base_generation_id | INTEGER | FK `generations.id`, the reigning champion at the start |
| trigger | TEXT | event that woke the agent (`start`, `verdict`, `job_done`, `reflection`, ...) |
| hypothesis | TEXT | what the agent wants to try, in its own words |
| candidate_commit | TEXT | SHA in the genome, null if it never submits |
| diff_stat | JSON | files and lines touched |
| status | TEXT | `running`, `judging`, `rejected`, `accepted`, `abandoned` (no submission), `reflected` (reflection finished), `stale` (base overtaken and rebase failed), `error`, `budget_stop` |
| rejected_at_gate | TEXT | `build`, `perft`, `smoke`, `match`, null if accepted |
| lesson | TEXT | line written by the agent after the verdict |
| error | TEXT | traceback when `status = error` |
| progress | JSON | the match so far, rewritten after every SPRT batch: the candidate's `games`, `wins`, `draws`, `losses`, `llr` and `bounds`; null when there is no match |
| created_at | DATETIME | |
| finished_at | DATETIME | |

### gate_results

| Field | Type | Notes |
|---|---|---|
| id | INTEGER | PK |
| experiment_id | INTEGER | FK `experiments.id` |
| gate | TEXT | `build`, `perft`, `smoke`, `match` (SPRT against the random player or the champion) |
| passed | BOOLEAN | |
| detail | JSON | public part shown to the agent (e.g. the move with a wrong perft) |
| duration_ms | INTEGER | |
| created_at | DATETIME | |

### matches

A series of games: SPRT, smoke or anchor.

| Field | Type | Notes |
|---|---|---|
| id | INTEGER | PK |
| experiment_id | INTEGER | FK, null for games against anchors |
| kind | TEXT | `smoke`, `sprt`, `anchor` |
| engine_a / engine_b | TEXT | genome commit or anchor name |
| time_control | TEXT | e.g. `8+0.08` |
| wins / draws / losses | INTEGER | from `engine_a`'s point of view |
| pentanomial | JSON | pairs scoring 0, 0.5, 1, 1.5, 2 points |
| elo_diff / elo_error | REAL | estimate and interval |
| llr | REAL | final log-likelihood ratio (SPRT only) |
| verdict | TEXT | `h1`, `h0`, `inconclusive` |
| created_at / finished_at | DATETIME | |

### games

| Field | Type | Notes |
|---|---|---|
| id | INTEGER | PK |
| match_id | INTEGER | FK `matches.id` |
| white / black | TEXT | like `engine_a`/`engine_b` |
| result | TEXT | `1-0`, `0-1`, `1/2-1/2` |
| termination | TEXT | `checkmate`, `stalemate`, `repetition`, `fifty_moves`, `material`, `adjudication` (300 moves), `illegal_move`, `timeout`, `crash` |
| pgn | TEXT | |
| created_at | DATETIME | |

### generations

An accepted champion. `gen-0` is the empty seed. A passed genesis does not create a generation: it only moves the base of the following iterations.

| Field | Type | Notes |
|---|---|---|
| id | INTEGER | PK, equal to N in `gen-N` |
| experiment_id | INTEGER | FK, null for `gen-0` |
| commit_sha | TEXT | UNIQUE |
| elo_vs_parent | REAL | from the SPRT that promoted it |
| created_at | DATETIME | |

### rating_snapshots

The champion's absolute Elo estimated against the anchors, or its Lichess rating.

| Field | Type | Notes |
|---|---|---|
| id | INTEGER | PK |
| generation_id | INTEGER | FK `generations.id` |
| source | TEXT | `anchors` (Stockfish ladder), `anchors_below` (below the ladder: marks the champion as measured, `elo` is the lowest rung and must not be shown), `lichess` |
| elo / elo_error | REAL | |
| detail | JSON | results per anchor |
| created_at | DATETIME | |

### llm_calls

Basis of the spending cap: the day's spend is the sum of `cost_usd` since midnight UTC.

| Field | Type | Notes |
|---|---|---|
| id | INTEGER | PK |
| experiment_id | INTEGER | FK |
| model | TEXT | e.g. `anthropic/claude-haiku-5.5` |
| input_tokens / cached_tokens / output_tokens | INTEGER | |
| cost_usd | REAL | actual cost reported by the provider |
| created_at | DATETIME | index for the daily sum |

### agent_events

The stream shown on the dashboard.

| Field | Type | Notes |
|---|---|---|
| id | INTEGER | PK |
| experiment_id | INTEGER | FK |
| kind | TEXT | `status`, `reasoning`, `thought`, `tool_call`, `tool_result` |
| payload | JSON | by `kind`, below |
| created_at | DATETIME | |

Payloads. Every text is capped at 2,000 characters, cut with a trailing `...`; `cut` says whether it was.

| kind | payload |
|---|---|
| `status` | `state` (`started`, `judging`, `stopped`, `provider_error`) and its context: `kind` and `trigger`, `phase`, `reason`, `error` |
| `reasoning` | `text`, `cut`: the model's summarized thinking for one reply, as the provider returns it. Kept for the site only: never translated, never shown to the agent or the referee |
| `thought` | `text`, `cut`: what the agent writes between tool calls; translated into Italian by the commentary worker |
| `tool_call` | `tool`, `call_id` (pi's `toolCallId`), `args` (the arguments as a JSON object, each string inside cut on its own, lists kept to 20 items), `cut` |
| `tool_result` | `tool`, `call_id` (the call it answers), `error`, `text`, `cut` |

Rows written before 2026-11-26 have no `call_id` and no `cut`, and their `args` is a string: Python's repr of the arguments, cut at 2,000 characters as a whole. Readers handle both: a string `args` is the old repr, and a result without `call_id` pairs with the oldest open call of the same tool.

### jobs

Long CPU-only jobs started by the agent with `run_job`.

| Field | Type | Notes |
|---|---|---|
| id | INTEGER | PK |
| experiment_id | INTEGER | FK, the iteration that started it |
| command | TEXT | command run in the job's container |
| cpus / max_hours | REAL | caps imposed |
| status | TEXT | `running`, `done`, `failed`, `killed` (time or disk quota: the reason opens `log_tail`) |
| exit_code | INTEGER | |
| log_tail | TEXT | last lines of the output |
| created_at / finished_at | DATETIME | |

### lichess_games

The bot's games on Lichess, each with the champion that played it.

| Field | Type | Notes |
|---|---|---|
| id | INTEGER | PK |
| lichess_id | TEXT | UNIQUE, the game's id on Lichess |
| generation_id | INTEGER | FK `generations.id` |
| color | TEXT | `white`, `black` |
| opponent / opponent_rating / opponent_title | TEXT / INTEGER / TEXT | |
| rated | BOOLEAN | |
| time_control | TEXT | e.g. `180+2` |
| status | TEXT | Lichess status (`started`, `mate`, `resign`, `outoftime`, ...) |
| result | TEXT | `win`, `loss`, `draw`, `aborted`; null while the game is on |
| moves | TEXT | UCI moves separated by spaces |
| rating_after | INTEGER | the bot's rating once the game is over |
| evals | JSON | Stockfish's evaluation of every ply, from our side (games of at least 10 plies) |
| analysis | JSON | losses only: the move after which the evaluation drops the most (see `referee/analysis.py`) |
| created_at / finished_at | DATETIME | |

### lichess_challenges

Every challenge the bot sent to another bot. Lichess caps the challenges an account sends in a day (refused ones count too), so matchmaking counts the last 24 hours here.

| Field | Type | Notes |
|---|---|---|
| id | INTEGER | PK |
| opponent | TEXT | the bot challenged |
| outcome | TEXT | `created`, `refused` (Lichess turned it down at once), `rate_limited` (answered 429, not counted) |
| created_at | DATETIME | indexed |

### commentaries

Texts for the site's visitors, in Italian and English. The agent never reads them.

| Field | Type | Notes |
|---|---|---|
| id | INTEGER | PK |
| kind | TEXT | `lichess_game`, `match`, `hypothesis`, `lesson`, `title` (short title of the hypothesis, written at submission), `thought` (agent thought), `strategy`, `notes`, `prompt` (memory files and instructions) |
| subject_id | INTEGER | `lichess_games.id`, `matches.id`, `experiments.id` or `agent_events.id` depending on `kind`; for `strategy`, `notes` and `prompt` the CRC32 of the translated text, so every version has its own translation; UNIQUE with `kind` |
| text_it / text_en | TEXT | for `hypothesis` and `lesson` the English is the agent's original and the Italian the translation; for `title` both are written by the model; for thoughts, memory and instructions the English is the original |
| model | TEXT | |
| input_tokens / output_tokens | INTEGER | |
| cost_usd | REAL | counts against the commentary cap, separate from the agent's budget |
| created_at | DATETIME | |

## Relationships

```
generations 1 ─< experiments (base) ─< gate_results
                     │  └──< matches ─< games
                     ├──< llm_calls
                     ├──< jobs
                     └──< agent_events
generations 1 ─< rating_snapshots
experiments 1 ── 0..1 generations (promotion)
```

## Migrations

See `backend/alembic/versions/`. Commands: `make db-revision msg='...'`, `make db-migrate`.
