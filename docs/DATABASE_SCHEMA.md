# Schema del registro

## Convenzioni

- SQLite via SQLAlchemy 2.0 async (`aiosqlite`), migrazioni Alembic in `backend/alembic/versions/` con `render_as_batch` (SQLite non altera i vincoli sul posto).
- **Append-only**: il registro è la storia dell'esperimento e nessuna riga si cancella né si riscrive, quindi niente `deleted_at` (deroga motivata in `DECISIONS.md`). Una riga cambia solo per chiudere uno stato aperto (`finished_at`, `status`).
- PK `id` intera autoincrementale. Timestamp UTC: `created_at` sempre, `finished_at` dove c'è una durata.
- Dettagli variabili (output perft, parametri SPRT, payload dei tool) in colonne `JSON`.

Lo schema sotto è il progetto della milestone M1-M3: le tabelle nascono con la loro prima migrazione, non prima.

## Entità

### experiments

Un'iterazione dell'agente: un'ipotesi, un candidato, un esito.

| Campo | Tipo | Note |
|---|---|---|
| id | INTEGER | PK |
| phase | TEXT | `genesis`, `first_steps`, `evolution`, `world` |
| base_generation_id | INTEGER | FK `generations.id`, null in genesi |
| hypothesis | TEXT | cosa vuole provare l'agente, scritto da lui |
| candidate_commit | TEXT | SHA nel genoma, null se non arriva a consegnare |
| diff_stat | JSON | file e righe toccate |
| status | TEXT | `running`, `rejected`, `accepted`, `error`, `budget_stop` |
| rejected_at_gate | TEXT | `build`, `perft`, `smoke`, `match`, null se accettato |
| lesson | TEXT | riga scritta dall'agente dopo il verdetto |
| created_at | DATETIME | |
| finished_at | DATETIME | |

### gate_results

| Campo | Tipo | Note |
|---|---|---|
| id | INTEGER | PK |
| experiment_id | INTEGER | FK `experiments.id` |
| gate | TEXT | `build`, `perft`, `smoke`, `match` (SPRT contro il giocatore casuale o il campione) |
| passed | BOOLEAN | |
| detail | JSON | parte pubblica mostrata all'agente (es. mossa con perft errato) |
| duration_ms | INTEGER | |
| created_at | DATETIME | |

### matches

Una serie di partite: SPRT, smoke o ancora.

| Campo | Tipo | Note |
|---|---|---|
| id | INTEGER | PK |
| experiment_id | INTEGER | FK, null per le partite contro ancore |
| kind | TEXT | `smoke`, `sprt`, `anchor` |
| engine_a / engine_b | TEXT | commit del genoma o nome dell'ancora |
| time_control | TEXT | es. `8+0.08` |
| wins / draws / losses | INTEGER | dal punto di vista di `engine_a` |
| elo_diff / elo_error | REAL | stima e intervallo |
| llr | REAL | log-likelihood ratio finale (solo SPRT) |
| verdict | TEXT | `h1`, `h0`, `inconclusive` |
| created_at / finished_at | DATETIME | |

### games

| Campo | Tipo | Note |
|---|---|---|
| id | INTEGER | PK |
| match_id | INTEGER | FK `matches.id` |
| white / black | TEXT | come `engine_a`/`engine_b` |
| result | TEXT | `1-0`, `0-1`, `1/2-1/2` |
| termination | TEXT | `checkmate`, `stalemate`, `repetition`, `fifty_moves`, `material`, `adjudication` (300 mosse), `illegal_move`, `timeout`, `crash` |
| pgn | TEXT | |
| created_at | DATETIME | |

### generations

Un campione accettato. `gen-0` è il seme vuoto.

| Campo | Tipo | Note |
|---|---|---|
| id | INTEGER | PK, coincide con N di `gen-N` |
| experiment_id | INTEGER | FK, null per `gen-0` |
| commit_sha | TEXT | UNIQUE |
| elo_vs_parent | REAL | dallo SPRT che l'ha promosso |
| created_at | DATETIME | |

### rating_snapshots

Elo assoluto del campione stimato contro le ancore, o rating Lichess.

| Campo | Tipo | Note |
|---|---|---|
| id | INTEGER | PK |
| generation_id | INTEGER | FK `generations.id` |
| source | TEXT | `anchors`, `lichess` |
| elo / elo_error | REAL | |
| detail | JSON | risultati per ancora |
| created_at | DATETIME | |

### llm_calls

Base del tetto di spesa: la spesa del giorno è la somma di `cost_usd` dalla mezzanotte UTC.

| Campo | Tipo | Note |
|---|---|---|
| id | INTEGER | PK |
| experiment_id | INTEGER | FK |
| model | TEXT | es. `anthropic/claude-haiku-5.5` |
| input_tokens / cached_tokens / output_tokens | INTEGER | |
| cost_usd | REAL | costo reale riportato dal provider |
| created_at | DATETIME | indice per la somma giornaliera |

### agent_events

Il flusso mostrato in dashboard.

| Campo | Tipo | Note |
|---|---|---|
| id | INTEGER | PK |
| experiment_id | INTEGER | FK |
| kind | TEXT | `thought`, `tool_call`, `tool_result`, `note` |
| payload | JSON | |
| created_at | DATETIME | |

## Relazioni

```
generations 1 ─< experiments (base) ─< gate_results
                     │  └──< matches ─< games
                     ├──< llm_calls
                     └──< agent_events
generations 1 ─< rating_snapshots
experiments 1 ── 0..1 generations (promozione)
```

## Migrazioni

Vedi `backend/alembic/versions/`. Comandi: `make db-revision msg='...'`, `make db-migrate`.
