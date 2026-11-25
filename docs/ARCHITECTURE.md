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

- **Sandbox** (`lab/`): immagine Docker con la toolchain Rust. I comandi dell'agente girano qui, senza rete, con solo `genome/` montato in scrittura e il filesystem di sistema in sola lettura. Un container nuovo per ogni iterazione.
- **Arbitro** (`darwin.referee`): oracolo perft su posizioni casuali (python-chess), compilazione pulita del candidato, partite e SPRT. Le partite le gioca fastchess nel container `arena`; l'arbitro prepara le aperture, rilegge ogni PGN con python-chess per verificare legalità ed esito, e calcola lui l'SPRT a lotti. Ogni processo motore gira nel proprio container effimero (`--network none`, binario in sola lettura, 1 CPU): un candidato non vede e non può toccare l'avversario. Le ancore sono il giocatore casuale (da M1) e Stockfish a forza limitata (M6).
- **Orchestratore** (`darwin.orchestrator`): il ciclo delle generazioni, i ritmi descritti sotto, il tetto di spesa. L'agente gira dentro pi, comandato in modalità RPC.
- **Registro** (`darwin.ledger`): SQLite append-only con esperimenti, verdetti, partite, generazioni, chiamate LLM ed eventi dell'agente. Schema in `DATABASE_SCHEMA.md`.
- **API** (`darwin.api`): FastAPI, legge il registro e trasmette gli eventi live via SSE.
- **Dashboard** (`frontend/`): scacchiera live, curva Elo con ancore, timeline delle generazioni, flusso dell'agente, spesa.
- **Bot Lichess** (milestone M5): il bridge ufficiale `lichess-bot` gioca di continuo con il campione in carica. Due usi: la misura nel mondo vero (performance calcolata per generazione, perché l'account mescola le versioni) e la fonte di lezioni. Ogni sconfitta viene analizzata da Stockfish lato arbitro, che segna dove la valutazione crolla, e arriva all'agente riassunta. Lichess non giudica i candidati: troppo lento e rumoroso per quello.

## L'agente: pi e i suoi tool

L'orchestratore avvia pi come processo figlio e lo comanda via JSON su stdin e stdout (modalità RPC). Ogni evento di pi (testo dell'agente, chiamate ai tool, uso dei token) passa dall'orchestratore, che lo scrive in `agent_events` e `llm_calls`: da lì nascono i sottotitoli della dashboard e il conteggio della spesa. pi non entra nel sandbox: ci entrano solo i suoi comandi, mentre la chiave API resta all'orchestratore. Versione di pi fissata, il progetto è giovane.

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

1. **Osserva**: l'orchestratore costruisce il contesto: fase corrente, campione, ultimi N esperimenti con ipotesi ed esito, `NOTES.md` e `STRATEGY.md` del genoma, una riga sulle sconfitte Lichess nuove.
2. **Implementa**: l'agente lavora con i suoi tool entro un tetto di chiamate e token per iterazione; l'orchestratore conta i token dagli eventi di pi e lo ferma se lo supera.
3. **Consegna**: con `submit` il candidato attraversa i cancelli dell'arbitro in ordine di costo, fermandosi al primo fallito: build, perft, smoke (partite lampo senza mosse illegali, crash o timeout), match della fase.
4. **Impara**: l'esito va nel registro. Se vince, il candidato diventa un commit con tag `gen-N` nel genoma; l'agente aggiunge una lezione a `NOTES.md`.

Ogni iterazione parte con un contesto nuovo: lo stato vive nel git del genoma e nel registro, non in una conversazione che cresce.

## Ritmi

Quello che fa sembrare vivo il sistema non deve costare: la CPU lavora sempre, l'LLM a impulsi.

1. **Sempre acceso, costo zero**: partite di valutazione, self-play per l'addestramento, più avanti Lichess. Sulla dashboard c'è sempre una partita in corso.
2. **Risveglio a eventi**: l'agente parte quando arriva un verdetto, finisce un `run_job` o arriva un gruppo di sconfitte Lichess, non a orario. Mentre l'arbitro giudica il candidato N l'agente prepara N+1, con al massimo un candidato in coda.
3. **Riflessione periodica**: ogni 10 generazioni circa, o una volta al giorno, l'agente rilegge l'andamento e riscrive `STRATEGY.md`, cioè sceglie da solo la prossima direzione.

La spesa giornaliera si distribuisce sulle ore (2 $ al giorno, circa 8 centesimi l'ora): quando la quota dell'ora è finita l'agente dorme e la macchina continua a giocare. Stima da misurare in M3: 2-5 centesimi per iterazione con Haiku 5.5 e la cache, quindi 40-100 iterazioni al giorno. Il collo di bottiglia atteso è la CPU dell'arbitro, non il budget.

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
│                rete: solo OpenRouter; unico servizio con accesso a Docker
├─ api           FastAPI + dashboard compilata, legge il registro
├─ (M5) lichess-bot
└─ container effimeri creati da core:
   ├─ sandbox    uno per iterazione, qui girano i comandi di pi
   ├─ build      compilazione pulita del candidato da un commit
   ├─ arena      fastchess, crea i container dei motori
   ├─ motore     uno per motore: senza rete, 1 CPU, binario in sola lettura
   └─ job        i lavori di run_job, con tetto di CPU
```

- Orchestratore e arbitro stanno nello stesso processo: sono entrambi fidati e il registro SQLite mantiene un solo scrittore. La separazione la garantisce la regola sugli import.
- I dati (`DARWIN_DATA_DIR`: binari, partite, registro, artefatti) sono montati nei container allo stesso path che hanno sull'host, così i bind mount dei container creati da `core` e da `arena` si risolvono uguali in sviluppo e in produzione.
- CPU, da tarare con un test di carico di un'ora: alla VM di Docker 8 core su 10; dentro, 2 per le compilazioni dell'agente e 6 per le partite (3 in parallelo). Un addestramento prende core dalle partite, non si somma. Senza ventola l'Air rallenta sotto carico continuo, e i core misti aggiungono rumore alle partite: servono più partite per un verdetto, non c'è distorsione sistematica.

## Boundary

- L'arbitro non importa nulla dall'orchestratore: riceve un commit o un binario e restituisce un verdetto.
- L'agente non riceve mai codice o output interno dell'arbitro, solo il verdetto e i dettagli pubblici (per esempio la mossa con perft sbagliato).
- Comandano Docker solo `core` e `arena`, che esegue fastchess (codice fidato, non dell'agente). Sandbox, motori, job e il bot Lichess non vedono mai il socket.
- Stockfish lo usa solo l'arbitro; non è mai raggiungibile dal sandbox.
- L'API legge il registro, non scrive.
