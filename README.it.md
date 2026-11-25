# darwin-chess

[English](README.md) · **Italiano** · [Sito](https://darwin.esse.dev)

Un agente LLM scrive un motore di scacchi in Rust partendo da un crate vuoto e continua a farlo evolvere da solo. Una modifica sopravvive solo se vince partite vere contro la versione precedente, giudicata da un arbitro che l'agente non può vedere né toccare.

Stato: in esecuzione 24/7 dal 25 novembre 2026, con le partite, il ragionamento dell'agente e la spesa mostrati in diretta sul sito.

## Domanda

Fin dove arriva un agente LLM economico e autonomo nel costruire un motore di scacchi, se ogni sua modifica deve vincere partite per sopravvivere e niente di ciò che scrive può piegare la misura?

## Risposta breve

Risultati al 25 novembre 2026, dopo il primo giorno:

- Il campione è **gen-8**, a circa **1.488 ± 115** di Elo assoluto contro Stockfish a forza limitata (margine al 95%).
- gen-8 nasce dall'**approfondimento iterativo con ordinamento delle mosse MVV-LVA**, che vale **+416 ± 149** Elo su gen-7. Ogni ritocco della valutazione prima di lui aveva aggiunto fra 17 e 42 Elo.
- L'agente è Claude Haiku 5.5 dentro pi, a sforzo `high`. Una sessione costa circa 0,01-0,02 $; le prime 29 sessioni sono costate 0,14 $ in tutto. Il collo di bottiglia è la CPU dell'arbitro, non il budget.

## Hardware e setup

- Un MacBook Air M4 in casa: 10 core (4 performance, 6 efficienza), 16 GB, senza ventola, Docker Desktop. Niente GPU: Docker su Mac non la vede.
- La VM di Docker ha 8 core su 10, in attesa di un test di carico di un'ora: 2 per le compilazioni dell'agente, 6 per le partite (3 in parallelo). Sotto carico continuo l'Air senza ventola rallenta, e i core misti aggiungono rumore, quindi un verdetto richiede più partite.
- Agente: Claude Haiku 5.5 (Anthropic di default, OpenRouter in alternativa) dentro [pi](https://www.npmjs.com/package/@earendil-works/pi-coding-agent), a versione fissata e comandato in modalità RPC, con un budget giornaliero di 2 $ distribuito sulle ore.
- Backend: Python 3.13, FastAPI, SQLAlchemy 2.0 async, Alembic, python-chess (uv). Registro: SQLite.
- Frontend: React 19, TypeScript strict, Vite, Tailwind v4, shadcn/ui, TanStack Query (pnpm). Dashboard bilingue, pubblica su https://darwin.esse.dev tramite un Cloudflare Tunnel.
- Le partite le gioca fastchess; le ancore sono un giocatore casuale e Stockfish 17.

## Metodo

- **Genoma** (`genome/`): il motore in Rust, di proprietà dell'agente. È un repository git a parte: ogni commit accettato è una generazione.
- **Sandbox**: i comandi dell'agente girano in un container Docker con la toolchain Rust, poche crate già scaricate e PyTorch CPU, senza rete, senza Stockfish e senza codice dell'arbitro.
- **Arbitro**: codice fidato fuori dal sandbox. Un candidato passa i cancelli in ordine di costo: compilazione pulita, perft su posizioni casuali (i conteggi standard sono noti e si potrebbero scrivere a mano), partite di smoke, poi il match. Contro il campione il match è uno SPRT pentanomiale (elo0 0, elo1 10, alpha e beta 0,05) a 8+0.08, giocato a lotti; l'arbitro rilegge ogni PGN con python-chess e calcola lui l'SPRT. Ogni processo motore gira nel proprio container (senza rete, 1 CPU, binario in sola lettura).
- **Ancore**: ogni nuovo campione sale una scala di Stockfish 17 a `UCI_Elo` 1320, 1600, 2000, 2400 e 2800; i gradini informativi si combinano, pesati per precisione, nell'Elo assoluto con il suo margine al 95%.
- **Orchestratore**: sveglia l'agente sugli eventi (un verdetto, un job finito, un gruppo di sconfitte su Lichess). Ogni iterazione parte da un contesto nuovo; lo stato vive nella storia git del genoma e nel registro. Ogni 10 iterazioni l'agente rilegge tutta la storia e riscrive la propria strategia.
- **Lichess**: un bot gioca di continuo con il campione in carica. Lichess non giudica mai i candidati; Stockfish analizza ogni sconfitta e l'agente la riceve come lezione.
- Divisione dei ruoli, per progetto: l'LLM costruisce e ottimizza la macchina, e la conoscenza scacchistica della valutazione deve venire da una rete addestrata sulle partite del motore contro se stesso, non dalla memoria dell'LLM.

Dettagli in [Architettura](docs/ARCHITECTURE.md), [Decisioni](docs/DECISIONS.md), [Schema del registro](docs/DATABASE_SCHEMA.md), [Cicli](docs/CYCLES.md) e [Roadmap](docs/ROADMAP.md).

## Risultati

| Data | Campione | Elo assoluto | Nota |
|---|---|---|---|
| 2026-11-25 | da gen-3 a gen-7 | da 1.129 a 1.259 | piccoli ritocchi della valutazione, fra +17 e +42 Elo l'uno, margini di ± 120-140 |
| 2026-11-25 | gen-8 | 1.488 ± 115 | approfondimento iterativo con ordinamento MVV-LVA, +416 ± 149 su gen-7 |

L'agente ha passato quattro generazioni a ritoccare la valutazione a sforzo `low`. Due cambiamenti sono arrivati subito prima del salto: lo sforzo di ragionamento portato a `high` (DECISIONS #25) e la riflessione periodica contata dal registro: il contatore in memoria si azzerava a ogni riavvio, quindi l'agente non aveva mai riflettuto. La prima riflessione vera (esperimento 25) è stata seguita dall'approfondimento iterativo (esperimento 26), diventato gen-8.

La storia completa, generazione per generazione, è sul [sito](https://darwin.esse.dev) e nei [CYCLES](docs/CYCLES.md).

## Come riprodurlo

Servono Docker, uv, pnpm e una chiave API di Anthropic (o OpenRouter). Ogni sessione che chiama il modello costa, entro il budget giornaliero.

```bash
make install
cp .env.example .env           # alla radice; poi DARWIN_HOME e DARWIN_LLM_API_KEY
make images                    # sandbox, arena, ancore, motori di test
make db-migrate
make genome-init               # crea il genoma vuoto (gen-0)
make run-sessions n=3          # qualche sessione di prova, poi si ferma
make dev                       # API su :4730, dashboard su :4731
```

`make run-core` fa girare l'esperimento senza limite di sessioni; `make up` lo fa girare in Docker Compose (`core` e `api`). `make deploy` aggiorna un server remoto via ssh senza interrompere la sessione dell'agente né la partita Lichess in corso: legge `DEPLOY_HOST` e `DEPLOY_DIR` da un `Makefile.local` non versionato. `make check` esegue format, lint, typecheck e test.

## Limiti

- Un solo run, un solo modello, una sola macchina: i risultati sono una traiettoria, non una distribuzione.
- L'Elo assoluto è misurato contro Stockfish a forza limitata, con margini sopra ± 100; non è un rating FIDE né Lichess.
- I match usano un controllo del tempo breve (8+0.08): i guadagni ottenuti lì potrebbero non valere nelle partite più lente.
- Haiku conosce le tecniche dei motori dal suo addestramento: l'esperimento misura quanto bene un agente applica idee note sotto un arbitro severo, non la scoperta.
- Il libro di aperture lo genera l'arbitro (mosse casuali a materiale pari), non è ancora filtrato da Stockfish.
- Il portatile senza ventola e i suoi core misti aggiungono rumore alle partite; l'arbitro lo compensa con più partite, non con una correzione.

## Licenza

[MIT](LICENSE), tranne le immagini dei pezzi cburnett in `frontend/public/pieces/cburnett/`, che mantengono la loro licenza GPLv2+.
