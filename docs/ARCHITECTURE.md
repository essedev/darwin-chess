# Architettura

## Visione d'insieme

Un agente LLM economico parte da un crate Rust vuoto e costruisce un motore di scacchi, migliorandolo a ogni generazione senza intervento umano. L'esperimento misura fin dove arriva un agente autonomo quando ogni sua modifica deve vincere partite vere per sopravvivere. La conoscenza scacchistica della valutazione la impara una rete dalle partite del motore contro se stesso, non l'LLM a memoria.

## I tre mondi

| Mondo | Dove | Fiducia | Chi lo modifica |
|---|---|---|---|
| Genoma | `genome/` (repo git separato, ignorato) | nessuna | solo l'agente |
| Arbitro | `backend/src/darwin/referee/` | totale | solo noi |
| Orchestratore | `backend/src/darwin/orchestrator/` | totale | solo noi |

Il confine di fiducia è il punto centrale del progetto. Un LLM a cui si chiede di far salire un numero trova la scorciatoia più facile: scrivere a mano i conteggi perft, allungarsi il tempo, uccidere il processo avversario. Per questo l'arbitro vive fuori dal sandbox e ogni motore gira isolato.

## Componenti

- **Sandbox** (`lab/`): immagine Docker con la toolchain Rust, un insieme di crate già scaricate (rand, rayon, bytemuck, versioni fissate, risolte offline tramite `/.cargo/config.toml`) e Python con PyTorch CPU e numpy per l'addestramento. Niente GPU: Docker su Mac non la vede. I job usano la stessa immagine con 2 CPU, 4 GB, al massimo 12 ore e una quota disco (10 GB per job, 40 GB in tutto, sul disco interno). I comandi dell'agente girano qui, senza rete, con `genome/` e `/memory` in scrittura, il mirror e `/jobs` in sola lettura, il filesystem di sistema in sola lettura. Un container nuovo per ogni sessione.
- **Mirror** (`data/mirror.git`): repository bare fidato con ogni commit che conta (`refs/darwin/gen-N`, `refs/darwin/exp-N`). Lo scrive solo l'orchestratore; la compilazione dell'arbitro e il reset del genoma partono da qui, così l'agente non può alterare o cancellare la storia dei campioni.
- **Memoria** (`data/agent/memory`): `NOTES.md` e `STRATEGY.md` dell'agente, fuori dal genoma, così sopravvivono agli esperimenti bocciati.
- **Arbitro** (`darwin.referee`): oracolo perft su posizioni casuali (python-chess), compilazione pulita del candidato, partite e SPRT. Le partite le gioca fastchess nel container `arena`; l'arbitro prepara le aperture, rilegge ogni PGN con python-chess per verificare legalità ed esito, e calcola lui l'SPRT a lotti; dopo ogni lotto scrive l'avanzamento del match sull'esperimento (`progress`), che la diretta mostra. Ogni processo motore gira nel proprio container effimero (`--network none`, binario in sola lettura, 1 CPU): un candidato non vede e non può toccare l'avversario. Le ancore sono il giocatore casuale e Stockfish 17 a forza limitata (`UCI_Elo` 1320, 1600, 2000, 2400, 2800): ogni nuovo campione sale la scala finché vince troppo per misurare qualcosa, e le stime delle ancore informative si combinano pesandole per precisione. Sotto 1320 il campione resta "sotto la scala". La dashboard mostra l'Elo assoluto sempre con il suo margine al 95% (DECISIONS #21).
- **Orchestratore** (`darwin.orchestrator`): il ciclo delle generazioni, i ritmi descritti sotto, il tetto di spesa. L'agente gira dentro pi, comandato in modalità RPC.
- **Registro** (`darwin.ledger`): SQLite append-only con esperimenti, verdetti, partite, generazioni, chiamate LLM ed eventi dell'agente. Schema in `DATABASE_SCHEMA.md`.
- **Commenti** (`darwin.commentary`, dentro `core`): Haiku scrive per i visitatori, in italiano e inglese con una sola chiamata, un commento per ogni partita Lichess (basato sulle valutazioni di Stockfish di ogni semimossa) e uno per ogni match dell'arbitro (basato su risultati e statistiche delle partite), traduce in italiano ipotesi e lezioni dell'agente e dà a ogni ipotesi un titolo breve nelle due lingue (titolo e traduzione partono alla consegna). Traduce anche ogni pensiero dell'agente appena scritto e, al massimo una volta l'ora, la versione corrente di strategia, appunti e istruzioni (fino a 16.000 caratteri). Resta in inglese solo il codice. Coda con un solo consumatore, tetto suo di 0,20 $ al giorno, recupero di ciò che manca all'avvio. Solo con provider Anthropic. L'agente non li vede.
- **API** (`darwin.api`): FastAPI in sola lettura, pubblica. `/api/overview` (fase, generazioni, esperimento in corso, in giudizio e ultimo verdetto, spesa, ultimi eventi), `/api/live` (una partita dell'arbitro seguita fino alla fine, letta dal flusso di eventi di fastchess sotto `data/matches`, con le vittorie del match finora), `/api/lichess` (partita in corso e ultime partite del bot con il commento), `/api/stream` (SSE: eventi dell'agente e partita, controllati ogni secondo). Per le pagine secondarie `/api/generations/detail`, `/api/experiments`, `/api/matches`, `/api/code/*` (albero, file e diff del genoma letti dal mirror), `/api/mind` (memoria e istruzioni dell'agente) e `/api/lab` (totali, costo per generazione, changelog).
- **Dashboard** (`frontend/`): bilingue (italiano e inglese, dizionari tipizzati in `src/i18n`), con le schede Diretta, Evoluzione, Codice, Mente e Laboratorio. La Diretta (DECISIONS #7, rivista con #21) ha tre colonne della stessa altezza e niente che cresce con la storia: a sinistra le ultime generazioni con la curva Elo, al centro una partita alla volta, con il nostro motore sempre in basso, e il pensiero dell'agente, a destra il giudizio in corso, gli ultimi risultati e la spesa. Un colore per soggetto e stati di caricamento, errore e vuoto animati in ASCII (DECISIONS #24). Tema chiaro e scuro dal sistema.
- **Bot Lichess** (`darwin.lichess`, dentro `core`): gioca di continuo con il campione in carica, accetta le sfide compatibili e ne lancia ad altri bot, mirando a 1200 finché il rating è provvisorio. Dopo un 429 rispetta l'attesa che Lichess indica; se non la indica, smette di lanciare sfide per una pausa che raddoppia fino a 4 ore. Il motore gira nel suo container senza rete; il token resta in `core`. Scritto da noi invece del `lichess-bot` ufficiale, che avrebbe dovuto avviare i container dei motori e quindi avere accesso a Docker accanto al token. Due usi: la misura nel mondo vero (performance calcolata per generazione, perché l'account mescola le versioni) e la fonte di lezioni. Ogni sconfitta viene analizzata da Stockfish lato arbitro, che segna dove la valutazione crolla, e arriva all'agente riassunta. Lichess non giudica i candidati: troppo lento e rumoroso per quello.

## L'agente: pi e i suoi tool

L'orchestratore avvia pi (`agent/`, versione fissata) come processo figlio e lo comanda via JSON su stdin e stdout (modalità RPC). pi gira in una cartella vuota con ogni caricamento automatico spento (configurazione di progetto, estensioni, skill, template, file di contesto, MCP): niente di ciò che l'agente scrive può essere caricato da pi, solo la nostra estensione. pi ragiona a sforzo `high` (`DARWIN_LLM_THINKING`, DECISIONS #25). Ogni evento di pi (testo dell'agente, chiamate ai tool, uso dei token) passa dall'orchestratore, che lo scrive in `agent_events` e `llm_calls`: da lì nascono i sottotitoli della dashboard e il conteggio della spesa. pi non entra nel sandbox: ci entrano solo i suoi comandi, mentre la chiave API resta all'orchestratore. Versione di pi fissata, il progetto è giovane.

Tool standard, eseguiti nel sandbox: `read`, `write`, `edit`, `bash`. Con la bash l'agente compila, testa, usa il git del genoma e fa giocare il suo motore contro il campione ricompilato dal tag.

Tool nostri, aggiunti con un'estensione TypeScript sottile che inoltra ogni chiamata all'API locale dell'orchestratore (la logica resta in Python):

| Tool | Cosa fa | Da |
|---|---|---|
| `perft_check` | perft dell'arbitro su posizioni casuali, restituisce la prima mossa con conteggio sbagliato | M3 |
| `submit` | consegna il candidato con l'ipotesi obbligatoria e chiude l'iterazione | M3 |
| `experiments` | cerca negli esperimenti passati (ipotesi, esito, margine) | M3 |
| `run_job` | lancia un lavoro lungo solo CPU (self-play, addestramento) con tetto di CPU, e ne legge lo stato | M3 |
| `lichess_losses` | legge la coda delle sconfitte con l'analisi di Stockfish | M5 |

Regola: diventa un tool solo ciò che il sandbox non può fare da solo. L'agente non ha rete, Stockfish, accesso all'arbitro, al tag `gen-N` (lo mette l'orchestratore) né al controllo del tempo.

## Il ciclo di una generazione

1. **Osserva**: l'orchestratore riporta il genoma alla base (l'ultimo commit accettato) e costruisce il contesto: fase, campione, ultimo verdetto con i dettagli dei cancelli, ultimi esperimenti, job, `STRATEGY.md` e la coda di `NOTES.md` (letti attraverso il sandbox: sono file dell'agente).
2. **Implementa**: l'agente lavora con i suoi tool entro un tetto di chiamate e token per iterazione; l'orchestratore conta i token dagli eventi di pi e lo ferma se lo supera.
3. **Consegna**: `submit` committa il working tree nel sandbox, copia il commit nel mirror e lo mette in coda all'arbitro, che lo fa passare per i cancelli in ordine di costo: build, perft, smoke (partite lampo senza mosse illegali, crash o timeout), match della fase. Se nel frattempo è nato un nuovo campione, il candidato viene prima riapplicato sopra; se va in conflitto l'esperimento è `stale`.
4. **Impara**: l'esito va nel registro. Se vince diventa `refs/darwin/gen-N` nel mirror. La sessione successiva riceve il verdetto e consegna la lezione con `lesson_for_previous`.

Ogni iterazione parte con un contesto nuovo: lo stato vive nel git del genoma e nel registro, non in una conversazione che cresce.

## Ritmi

Quello che fa sembrare vivo il sistema non deve costare: la CPU lavora sempre, l'LLM a impulsi.

1. **Sempre acceso, costo zero**: partite di valutazione, self-play per l'addestramento, il bot Lichess. Sulla dashboard c'è sempre una partita in corso.
2. **Risveglio a eventi**: l'agente parte quando arriva un verdetto, finisce un `run_job` o arriva un gruppo di sconfitte Lichess, non a orario. In evoluzione, mentre l'arbitro giudica il candidato N, l'agente prepara N+1, con al massimo un candidato in coda; in genesi e nei primi passi aspetta il verdetto, perché lì un candidato di solito passa e sposta la base, e il lavoro iniziato sulla base vecchia andrebbe perso.
3. **Riflessione periodica**: ogni 10 iterazioni, contate dal registro così che un riavvio non azzeri il conto, l'agente rilegge tutta la storia (esperimenti, codice dei tentativi, sconfitte Lichess) e riscrive `STRATEGY.md`, cioè sceglie da solo la prossima direzione.

La spesa giornaliera si distribuisce sulle ore (2 $ al giorno, circa 8 centesimi l'ora): quando la quota dell'ora è finita l'agente dorme e la macchina continua a giocare. Misurato in esercizio: con Haiku 5.5 e la cache una sessione costa 0,2 centesimi a sforzo `low` e 0,7-1,8 a `high`. Il collo di bottiglia è la CPU dell'arbitro, non il budget.

## Fasi

Le sblocca l'arbitro, non l'agente:

1. **Genesi**: solo build e perft, non esiste ancora un campione.
2. **Primi passi**: battere il giocatore casuale; chi ci riesce diventa `gen-1`.
3. **Evoluzione**: SPRT contro il campione in carica.
4. **Mondo**: ogni nuovo campione va sul bot Lichess.

## Contratto del genoma

Sta in `seed/CONTRACT.md`, copiato nel genoma alla creazione: binario `target/release/genome`, protocollo UCI, comando `perft <depth>` con il dettaglio per mossa. I file rivolti all'agente (`CONTRACT.md`, `STRATEGY.md`, `NOTES.md`) sono in inglese perché finiscono nel prompt.

## Deploy

Sviluppo sul portatile, esecuzione 24/7 su server via a VPN. server è un MacBook Air M4 (10 core, 4 veloci e 6 efficienti, 16 GB, senza ventola) con Docker Desktop, e ospita già other services e la trascrizione di Nexus.

```
server (Docker Compose, restart automatico)
├─ core          orchestratore + arbitro, un solo processo Python, con pi (Node)
│                e bot Lichess; rete: provider del modello e Lichess; unico servizio con accesso a Docker
├─ api           FastAPI + dashboard compilata, legge il registro
└─ container effimeri creati da core:
   ├─ sandbox    uno per iterazione, qui girano i comandi di pi
   ├─ build      compilazione pulita del candidato da un commit
   ├─ arena      fastchess, crea i container dei motori
   ├─ motore     uno per motore: senza rete, 1 CPU, binario in sola lettura
   └─ job        i lavori di run_job, con tetto di CPU
```

- Avvio: `.env` con `DARWIN_HOME` (path assoluto del repository) e la chiave, poi `make genome-init` e `make up`. Su server `make up-public` avvia anche `tunnel`: `cloudflared` (versione fissata) pubblica l'API, e con lei la dashboard, su https://darwin.esse.dev senza aprire porte. Le credenziali del tunnel `darwin` stanno in `~/.cloudflared` su server, create una volta con `cloudflared tunnel login` e `tunnel create`; il record DNS lo ha creato `tunnel route dns`. `core` applica le migrazioni all'avvio; `api` serve anche la dashboard compilata.
- Aggiornamento: `make deploy` dal portatile copia il codice su server, costruisce le immagini e chiede a `core` di svuotarsi (il file `data/control/drain`): niente sessioni nuove né partite Lichess nuove, quelle in corso finiscono. Quando `core` risponde con `data/control/drained`, `core` e `api` vengono ricreati sulle immagini nuove. `make deploy only=api` ricrea solo `api`, per i cambi al sito, e lascia lavorare `core`. Il giudizio in corso non si aspetta: dopo il riavvio l'arbitro lo rifà da capo, che costa solo CPU. Fermato, `core` chiude in ordine entro 30 secondi (SIGTERM) e rimuove i container della sua istanza.
- Orchestratore e arbitro stanno nello stesso processo: sono entrambi fidati e il registro SQLite mantiene un solo scrittore. La separazione la garantisce la regola sugli import.
- I dati (`DARWIN_DATA_DIR`: binari, partite, registro, artefatti) sono montati nei container allo stesso path che hanno sull'host, così i bind mount dei container creati da `core` e da `arena` si risolvono uguali in sviluppo e in produzione.
- CPU, da tarare con un test di carico di un'ora: alla VM di Docker 8 core su 10; dentro, 2 per le compilazioni dell'agente e 6 per le partite (3 in parallelo). Un addestramento prende core dalle partite, non si somma. Senza ventola l'Air rallenta sotto carico continuo, e i core misti aggiungono rumore alle partite: servono più partite per un verdetto, non c'è distorsione sistematica.

## Boundary

- L'arbitro non importa nulla dall'orchestratore: riceve un commit o un binario e restituisce un verdetto.
- L'agente non riceve mai codice o output interno dell'arbitro, solo il verdetto e i dettagli pubblici (per esempio la mossa con perft sbagliato).
- Comandano Docker solo `core` e `arena`, che esegue fastchess (codice fidato, non dell'agente). Sandbox, motori, job e il bot Lichess non vedono mai il socket.
- Nessun comando git gira sull'host dentro il genoma: hook e configurazione del repository sono dell'agente. Ogni operazione git passa da un container.
- I file dell'agente si leggono dall'host solo attraverso il sandbox o dopo aver verificato che il percorso risolto resti nel genoma: un link simbolico potrebbe puntare ovunque.
- Stockfish lo usa solo l'arbitro; non è mai raggiungibile dal sandbox.
- L'API legge il registro, non scrive.
