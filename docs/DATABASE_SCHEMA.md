# Schema del registro

## Convenzioni

- SQLite via SQLAlchemy 2.0 async (`aiosqlite`), migrazioni Alembic in `backend/alembic/versions/` con `render_as_batch` (SQLite non altera i vincoli sul posto).
- **Append-only**: il registro è la storia dell'esperimento e nessuna riga si cancella né si riscrive, quindi niente `deleted_at` (deroga motivata in `DECISIONS.md`). Una riga cambia solo per chiudere uno stato aperto (`finished_at`, `status`).
- PK `id` intera autoincrementale. Timestamp UTC: `created_at` sempre, `finished_at` dove c'è una durata.
- Dettagli variabili (output perft, parametri SPRT, payload dei tool) in colonne `JSON`.

Tutte le tabelle nascono con la migrazione iniziale. I timestamp passano dal tipo `UtcDateTime`: salvati in UTC senza fuso (SQLite non li gestisce), restituiti sempre con il fuso. Connessioni SQLite in WAL con chiavi esterne attive: `core` scrive, l'API legge in parallelo.

## Entità

### experiments

Una sessione dell'agente: un'iterazione (ipotesi, candidato, esito) o una riflessione periodica.

| Campo | Tipo | Note |
|---|---|---|
| id | INTEGER | PK |
| kind | TEXT | `iteration`, `reflection` |
| phase | TEXT | `genesis`, `first_steps`, `evolution` |
| base_commit | TEXT | commit da cui parte il lavoro |
| base_generation_id | INTEGER | FK `generations.id`, il campione in carica alla partenza |
| trigger | TEXT | evento che ha svegliato l'agente (`start`, `verdict`, `job_done`, `reflection`, ...) |
| hypothesis | TEXT | cosa vuole provare l'agente, scritto da lui |
| candidate_commit | TEXT | SHA nel genoma, null se non arriva a consegnare |
| diff_stat | JSON | file e righe toccate |
| status | TEXT | `running`, `judging`, `rejected`, `accepted`, `abandoned` (nessuna consegna), `reflected` (riflessione conclusa), `stale` (base superata e rebase fallito), `error`, `budget_stop` |
| rejected_at_gate | TEXT | `build`, `perft`, `smoke`, `match`, null se accettato |
| lesson | TEXT | riga scritta dall'agente dopo il verdetto |
| error | TEXT | traceback quando `status = error` |
| progress | JSON | il match finora, riscritto dopo ogni lotto dello SPRT: `games`, `wins`, `draws`, `losses` del candidato, `llr` e `bounds`; null se non c'è match |
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
| pentanomial | JSON | coppie che totalizzano 0, 0,5, 1, 1,5, 2 punti |
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

Un campione accettato. `gen-0` è il seme vuoto. Una genesi superata non crea una generazione: sposta solo la base delle iterazioni successive.

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
| source | TEXT | `anchors` (scala Stockfish), `anchors_below` (sotto la scala: segna il campione come misurato, `elo` è il gradino più basso e non va mostrato), `lichess` |
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

### jobs

Lavori lunghi solo CPU lanciati dall'agente con `run_job`.

| Campo | Tipo | Note |
|---|---|---|
| id | INTEGER | PK |
| experiment_id | INTEGER | FK, l'iterazione che l'ha lanciato |
| command | TEXT | comando eseguito nel container del job |
| cpus / max_hours | REAL | tetti imposti |
| status | TEXT | `running`, `done`, `failed`, `killed` (tempo o quota disco: il motivo apre `log_tail`) |
| exit_code | INTEGER | |
| log_tail | TEXT | ultime righe dell'output |
| created_at / finished_at | DATETIME | |

### lichess_games

Le partite del bot su Lichess, ciascuna con il campione che l'ha giocata.

| Campo | Tipo | Note |
|---|---|---|
| id | INTEGER | PK |
| lichess_id | TEXT | UNIQUE, l'id della partita su Lichess |
| generation_id | INTEGER | FK `generations.id` |
| color | TEXT | `white`, `black` |
| opponent / opponent_rating / opponent_title | TEXT / INTEGER / TEXT | |
| rated | BOOLEAN | |
| time_control | TEXT | es. `180+2` |
| status | TEXT | stato di Lichess (`started`, `mate`, `resign`, `outoftime`, ...) |
| result | TEXT | `win`, `loss`, `draw`, `aborted`; null finché si gioca |
| moves | TEXT | mosse UCI separate da spazi |
| rating_after | INTEGER | rating del bot a partita finita |
| evals | JSON | valutazione di Stockfish per ogni semimossa, dal nostro lato (partite da almeno 10 semimosse) |
| analysis | JSON | solo sconfitte: la mossa dopo cui la valutazione crolla di più (vedi `referee/analysis.py`) |
| created_at / finished_at | DATETIME | |

### commentaries

Testi per i visitatori del sito, in italiano e inglese. L'agente non li legge mai.

| Campo | Tipo | Note |
|---|---|---|
| id | INTEGER | PK |
| kind | TEXT | `lichess_game`, `match`, `hypothesis`, `lesson`, `title` (titolo breve dell'ipotesi, scritto alla consegna), `thought` (pensiero dell'agente), `strategy`, `notes`, `prompt` (file della memoria e istruzioni) |
| subject_id | INTEGER | `lichess_games.id`, `matches.id`, `experiments.id` o `agent_events.id` secondo `kind`; per `strategy`, `notes` e `prompt` il CRC32 del testo tradotto, così ogni versione ha la sua traduzione; UNIQUE con `kind` |
| text_it / text_en | TEXT | per `hypothesis` e `lesson` l'inglese è l'originale dell'agente e l'italiano la traduzione; per `title` entrambi scritti dal modello; per pensieri, memoria e istruzioni l'inglese è l'originale |
| model | TEXT | |
| input_tokens / output_tokens | INTEGER | |
| cost_usd | REAL | conta sul tetto dei commenti, separato dal budget dell'agente |
| created_at | DATETIME | |

## Relazioni

```
generations 1 ─< experiments (base) ─< gate_results
                     │  └──< matches ─< games
                     ├──< llm_calls
                     ├──< jobs
                     └──< agent_events
generations 1 ─< rating_snapshots
experiments 1 ── 0..1 generations (promozione)
```

## Migrazioni

Vedi `backend/alembic/versions/`. Comandi: `make db-revision msg='...'`, `make db-migrate`.
