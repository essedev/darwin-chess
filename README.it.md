# darwin-chess

[English](README.md) · **Italiano** · [Sito](https://darwin.esse.dev)

Un agente LLM scrive un motore di scacchi in Rust partendo da un crate vuoto e continua a farlo evolvere da solo. Una modifica sopravvive solo se vince partite vere contro la versione precedente, giudicata da un arbitro che l'agente non può vedere né toccare.

Stato: in esecuzione 24/7 dal 25 novembre 2026, con le partite, il ragionamento dell'agente e la spesa mostrati in diretta sul sito.

## Domanda

Fin dove arriva un agente LLM economico e autonomo nel costruire un motore di scacchi, se ogni sua modifica deve vincere partite per sopravvivere e niente di ciò che scrive può piegare la misura?

## Risposta breve

Risultati al 26 novembre 2026, dopo circa 27 ore:

- Il campione è **gen-15**, a circa **2.079 ± 75** di Elo assoluto contro Stockfish a forza limitata (margine al 95%, stima congiunta).
- La salita da gen-8 (1.487 ± 81) a gen-15 ha preso una notte: sette generazioni, ognuna una tecnica di ricerca o di valutazione da manuale (ricerca di quiescenza, tabella delle trasposizioni, null move pruning, late move reductions, history heuristic, tabelle pezzo-casa graduate, patta per ripetizione). Prima di gen-8 l'agente aveva passato quattro generazioni a ritoccare la valutazione, fra 17 e 42 Elo l'uno.
- L'agente è Claude Haiku 5.5 dentro pi, a sforzo `high`. Un'iterazione costa circa 0,01-0,03 $; le prime 44 sessioni sono costate 0,35 $ in tutto. Il collo di bottiglia è la CPU dell'arbitro, non il budget.
- Non è ancora partito nessun job di addestramento: la valutazione la scrive ancora l'agente a mano, non la impara la rete prevista dal progetto.

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
- **Ancore**: ogni nuovo campione gioca una scala di Stockfish 17 a `UCI_Elo` 1320, 1600, 2000, 2400 e 2800, partendo dai gradini intorno al suo Elo atteso. L'Elo assoluto con il suo margine al 95% è un'unica stima di massima verosimiglianza su tutte le prove: ogni gradino giocato da ogni campione e il match in cui ogni campione ha battuto il precedente.
- **Orchestratore**: sveglia l'agente sugli eventi (un verdetto, un job finito, un gruppo di sconfitte su Lichess). Ogni iterazione parte da un contesto nuovo; lo stato vive nella storia git del genoma e nel registro. Una sessione ha 40 minuti, 80 chiamate ai tool e 0,25 $, e l'agente lo sa; il lavoro che non sottopone viene conservato, mai giudicato. Ogni 10 iterazioni l'agente rilegge tutta la storia e riscrive la propria strategia.
- **Lichess**: un bot gioca di continuo con il campione in carica. Lichess non giudica mai i candidati; Stockfish analizza ogni sconfitta e l'agente la riceve come lezione.
- Divisione dei ruoli, per progetto: l'LLM costruisce e ottimizza la macchina, e la conoscenza scacchistica della valutazione deve venire da una rete addestrata sulle partite del motore contro se stesso, non dalla memoria dell'LLM.

Dettagli in [Architettura](docs/ARCHITECTURE.md), [Decisioni](docs/DECISIONS.md), [Schema del registro](docs/DATABASE_SCHEMA.md), [Cicli](docs/CYCLES.md) e [Roadmap](docs/ROADMAP.md).

## Risultati

L'Elo assoluto è la stima congiunta che mostra il sito (DECISIONS #29); il guadagno è quello del match che ha promosso il campione sul genitore.

| Data | Campione | Elo assoluto | Modifica | Guadagno sul genitore |
|---|---|---|---|---|
| 2026-11-25 | da gen-3 a gen-7 | fra 1.117 e 1.213, ± 52-56 | piccoli ritocchi della valutazione | fra +17 e +42 l'uno |
| 2026-11-25 | gen-8 | 1.487 ± 81 | approfondimento iterativo con ordinamento MVV-LVA | +416 ± 149 |
| 2026-11-25 | gen-9 | 1.685 ± 64 | ricerca di quiescenza | +470 ± 1.047 (match quasi a senso unico) |
| 2026-11-26 | gen-10 | 1.764 ± 53 | tabella delle trasposizioni | +94 ± 36 |
| 2026-11-26 | gen-11 | 1.818 ± 50 | null move pruning | +61 ± 28 |
| 2026-11-26 | gen-12 | 1.832 ± 50 | late move reductions | +16 ± 11 |
| 2026-11-26 | gen-13 | 1.881 ± 52 | history heuristic per ordinare le mosse | +51 ± 24 |
| 2026-11-26 | gen-14 | 2.006 ± 57 | tabelle pezzo-casa graduate | +119 ± 37 |
| 2026-11-26 | gen-15 | 2.079 ± 75 | ripetizioni valutate come patta nella ricerca | +84 ± 34 |

L'agente ha passato quattro generazioni a ritoccare la valutazione. Due cambiamenti sono arrivati subito prima del salto: lo sforzo di ragionamento portato a `high` (DECISIONS #25) e la riflessione periodica contata dal registro: il contatore in memoria si azzerava a ogni riavvio, quindi l'agente non aveva mai riflettuto. La prima riflessione vera (esperimento 25) è stata seguita dall'approfondimento iterativo (esperimento 26), diventato gen-8; i sette campioni successivi sono arrivati nella notte, una tecnica classica ciascuno.

Da gen-8 l'arbitro non ha respinto nessun candidato che ha giudicato; il lavoro perso è quello rimasto indietro. 6 delle 17 iterazioni da allora hanno preparato il candidato mentre un altro era sotto giudizio, e la loro modifica non si applicava più quando quello è diventato campione.

Ogni campione viene misurato anche da solo contro la scala di Stockfish; il sito mostra quel numero accanto alla stima congiunta. gen-15 da solo fa 1.919 ± 166, sotto gen-14 da solo (2.108 ± 130), anche se ha battuto gen-14 di +84 ± 34: con 40 partite per gradino le misure singole sono rumorose, e la stima congiunta prende in prestito le centinaia di partite dei match fra campioni.

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
- L'Elo assoluto è misurato contro Stockfish a forza limitata; non è un rating FIDE né Lichess. I margini di ± 50-80 vengono da una stima congiunta che dà al guadagno sul genitore lo stesso valore contro Stockfish: i guadagni ottenuti contro se stessi spesso si riducono contro altri avversari, e uno SPRT fermato presto sovrastima il guadagno, quindi i margini non contano questo errore.
- I match usano un controllo del tempo breve (8+0.08): i guadagni ottenuti lì potrebbero non valere nelle partite più lente.
- Haiku conosce le tecniche dei motori dal suo addestramento: l'esperimento misura quanto bene un agente applica idee note sotto un arbitro severo, non la scoperta.
- Il libro di aperture lo genera l'arbitro (mosse casuali a materiale pari), non è ancora filtrato da Stockfish.
- Il portatile senza ventola e i suoi core misti aggiungono rumore alle partite; l'arbitro lo compensa con più partite, non con una correzione.

## Licenza

[MIT](LICENSE), tranne le immagini dei pezzi cburnett in `frontend/public/pieces/cburnett/` e la favicon disegnata da uno di essi, che mantengono la loro licenza GPLv2+.
