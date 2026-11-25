# Cicli

Un ciclo per unità di lavoro chiusa, dal più recente. Tiene gli ultimi ~15 cicli; i più vecchi vanno in `docs/archive/`.

## Ciclo 2: la pipeline completa in locale (2026-11-25)

**Obiettivo**: costruire tutti i pezzi dell'esperimento (M1-M4) e avviare deploy e ancore (M5, M6), così che manchino solo le prove a pagamento e la messa in esercizio.

**Fatto**:
- M1 Arbitro: compilazione pulita da un commit, perft su posizioni casuali con dettaglio per mossa, smoke, partite giocate da fastchess nel container `arena` con un container per motore, rilettura dei PGN con python-chess, SPRT pentanomiale a lotti calcolato da noi, giocatore casuale come prima ancora, cancelli per fase. Testato con motori UCI veri, anche difettosi apposta; uno shim elimina i container dei motori che ignorano `quit`.
- M2 Registro: tabelle, migrazione iniziale e store; SQLite in WAL, `core` scrive e l'API legge.
- M3 Orchestratore: pi in modalità RPC da una cartella vuota con il caricamento automatico spento, estensione che porta `read`/`write`/`edit`/`bash` nel sandbox e inoltra `perft_check`, `submit`, `experiments`, `run_job` all'API locale dei tool; mirror fidato da cui l'arbitro compila, memoria dell'agente fuori dal genoma, risveglio a eventi, riflessione periodica, spesa a quote orarie. Sessione completa provata da capo a fondo con un modello finto.
- M4 Dashboard: API in sola lettura (overview, partita in corso dagli eventi di fastchess, SSE) e la direzione D del concept, con i pezzi cburnett e la loro licenza.
- M5, parte: immagine unica `darwin-backend` per i servizi `core` e `api` in Compose (`make up`), dati montati allo stesso path dell'host. Provato in locale.
- M6, parte: scala di ancore Stockfish 17 a forza limitata (`UCI_Elo` da 1320 a 2800); ogni nuovo campione viene misurato dopo la promozione e la dashboard mostra l'Elo assoluto, o quello relativo al giocatore casuale sotto la scala.

**Decisioni**: #9-#16 (lezioni da Lichess, fastchess gioca e l'arbitro giudica, pi come harness, tool, ritmi, deploy in Compose, mirror fidato, test con modello finto); #5 in parte superata da #11.

**Prossimo passo**: le 3 iterazioni di prova a pagamento con costo misurato, che sono anche la prima accettazione di un genoma Rust vero. Poi deploy su server, bot Lichess, libro filtrato da Stockfish (vedi `ROADMAP.md`).

## Ciclo 1: scaffold e progetto (2026-11-24)

**Obiettivo**: fissare visione, confini di fiducia e stack, e scegliere la direzione della dashboard prima di scrivere codice.

**Fatto**: scaffold di backend, dashboard e sandbox Docker, genoma `gen-0` creato e compilato offline nel sandbox. Concept della dashboard con quattro direzioni, scelta la D con storico delle mosse e set di pezzi.

**Decisioni**: #1-#8 (divisione LLM e rete, arbitro immutabile, SQLite, registro append-only, Haiku via OpenRouter, Lichess come misura esterna, dashboard D, pezzi cburnett e icone Lucide).

**Prossimo passo**: arbitro, registro, orchestratore.
