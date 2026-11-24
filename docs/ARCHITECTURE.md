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

- **Sandbox** (`lab/`): immagine Docker con la toolchain Rust. L'agente esegue i suoi comandi qui, senza rete, con solo `genome/` montato in scrittura e il filesystem di sistema in sola lettura.
- **Arbitro** (`darwin.referee`): oracolo perft su posizioni casuali (python-chess), controllo di legalità di ogni mossa, gestione delle partite con controllo del tempo imposto, SPRT, partite contro ancore (giocatore casuale, Stockfish a forza limitata). Ogni processo motore gira nel proprio container effimero (`--network none`, binario in sola lettura, 1 CPU): un candidato non vede e non può toccare l'avversario.
- **Orchestratore** (`darwin.orchestrator`): il ciclo delle generazioni, i tool dell'agente, il client LLM (API compatibile OpenAI, provider da configurazione) e il tetto di spesa giornaliero.
- **Registro** (`darwin.ledger`): SQLite append-only con esperimenti, verdetti, partite, generazioni, chiamate LLM ed eventi dell'agente. Schema in `DATABASE_SCHEMA.md`.
- **API** (`darwin.api`): FastAPI, legge il registro e trasmette gli eventi live via SSE.
- **Dashboard** (`frontend/`): scacchiera live, curva Elo con ancore, timeline delle generazioni, flusso dell'agente, spesa.
- **Bot Lichess** (milestone M5): il bridge ufficiale `lichess-bot` gioca con il campione in carica.

## Il ciclo di una generazione

1. **Osserva**: l'orchestratore costruisce il contesto: fase corrente, campione, ultimi N esperimenti con ipotesi ed esito, `NOTES.md` e `STRATEGY.md` del genoma.
2. **Implementa**: l'agente lavora con i suoi tool (lettura e scrittura file, shell nel sandbox, `perft_check`) entro un tetto di chiamate e token per iterazione.
3. **Consegna**: il candidato attraversa i cancelli dell'arbitro in ordine di costo, fermandosi al primo fallito: build, perft, smoke (partite lampo senza mosse illegali, crash o timeout), SPRT contro il campione.
4. **Impara**: l'esito va nel registro. Se vince, il candidato diventa un commit con tag `gen-N` nel genoma; l'agente aggiunge una lezione a `NOTES.md`.

Ogni iterazione parte con un contesto nuovo: lo stato vive nel git del genoma e nel registro, non in una conversazione che cresce.

## Fasi

Le sblocca l'arbitro, non l'agente:

1. **Genesi**: solo il cancello perft, non esiste ancora un campione.
2. **Primi passi**: battere il giocatore casuale; chi ci riesce diventa `gen-1`.
3. **Evoluzione**: SPRT contro il campione in carica.
4. **Mondo**: ogni nuovo campione va sul bot Lichess.

## Contratto del genoma

Sta in `seed/CONTRACT.md`, copiato nel genoma alla creazione: binario `target/release/genome`, protocollo UCI, comando `perft <depth>` con il dettaglio per mossa. I file rivolti all'agente (`CONTRACT.md`, `STRATEGY.md`, `NOTES.md`) sono in inglese perché finiscono nel prompt.

## Deploy

Sviluppo sul portatile, esecuzione 24/7 su server (Mac mini M4, 16 GB) via a VPN. L'LLM è nel cloud, quindi server ospita solo orchestratore, arbitro, partite e dashboard.

## Boundary

- L'arbitro non importa nulla dall'orchestratore: riceve un binario e restituisce un verdetto.
- L'agente non riceve mai codice o output interno dell'arbitro, solo il verdetto e i dettagli pubblici (per esempio la mossa con perft sbagliato).
- Stockfish lo usa solo l'arbitro per le ancore; non è mai raggiungibile dal sandbox.
- L'API legge il registro, non scrive.
