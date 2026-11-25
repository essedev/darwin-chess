# Cicli

Un ciclo per unità di lavoro chiusa, dal più recente. Tiene gli ultimi ~15 cicli; i più vecchi vanno in `docs/archive/`.

## Ciclo 4: identità visiva, aggiornamenti senza interruzioni, un agente che pensa di più (2026-11-25)

**Obiettivo**: rendere il sito leggibile e riconoscibile, poter aggiornare server senza perdere lavoro, e far uscire l'agente dai ritocchi piccoli in cui era fermo da quattro generazioni.

**Fatto**:
- Aggiornamenti: `make deploy` svuota `core` prima di ricrearlo (niente sessioni né partite Lichess nuove, quelle in corso finiscono), `core` gestisce SIGTERM; `make deploy only=api` riavvia solo il sito e lascia lavorare `core`.
- Traduzioni: anche pensiero in diretta, strategia, appunti e istruzioni dell'agente in italiano, con le traduzioni rifiutate evitate e ritentate. Commenti che distinguono avversari umani dai bot, ordinali delle mosse in italiano.
- Diretta: segue una partita fino alla fine invece di saltare fra le tre in parallelo, il nostro motore sempre in basso, le vittorie del match accanto ai nomi.
- Identità visiva: concept C in cinque giri, scelta la variante E (un colore per soggetto, stati di caricamento, errore e vuoto animati in ASCII); caricamento centrato nella pagina. Changelog del sito 0.3.0 e 0.4.0.
- Agente: sa dove trovare i tentativi passati; ragiona a sforzo `high` invece di `low`. La riflessione si conta dal registro: il contatore in memoria si azzerava a ogni riavvio di `core`, quindi l'agente non aveva mai riflettuto; ora rilegge tutta la storia (esperimenti, codice dei tentativi, sconfitte Lichess).
- Esito: la prima riflessione vera (esperimento 25) è seguita dall'approfondimento iterativo con ordinamento MVV-LVA (esperimento 26), diventato gen-8 con +416 ± 149 Elo sul campione e 1.488 ± 115 di Elo assoluto, da 1.259 di gen-7. A sforzo alto una sessione costa 0,007-0,018 $, contro circa 0,002 $ a `low`; dall'avvio dell'esperimento 29 sessioni per 0,14 $ in tutto.
- Lichess: dopo un 429 il bot rispetta l'attesa chiesta da Lichess (corpo della risposta o `Retry-After`), senza indicazione raddoppia la pausa fino a 4 ore, e la risposta va nel log. In produzione: alle 22:44 Lichess rifiuta ancora le sfide senza dire quanto aspettare, pausa salita a 16 minuti; ultima partita giocata alle 19:59.

**Decisioni**: #22-#25 (svuotare `core` prima del riavvio, tutto tradotto tranne il codice, identità visiva, sforzo alto senza subagenti); #20 in parte superata da #23.

**Prossimo passo**: verificare che le sfide Lichess riprendano e, se il limite resta, capire quale limite è; misurare su una giornata costo e resa dello sforzo alto (#25). In coda all'arbitro la quiescenza (esperimento 29), dietro gli scacchi matti per distanza (28).

## Ciclo 3: in esercizio su server, Lichess e sito pubblico (2026-11-25)

**Obiettivo**: le prime sessioni a pagamento, poi l'esperimento acceso 24/7 su server con il bot Lichess e una dashboard che si può guardare da fuori.

**Fatto**:
- Prime sessioni pagate: `submit` accetta il lavoro già committato dall'agente, in genesi e nei primi passi la sessione successiva aspetta il verdetto (il lavoro sulla base vecchia finiva `stale`), il prompt spiega ogni verdetto.
- Bot Lichess scritto da noi, sempre sul campione in carica: sconfitte analizzate da Stockfish e passate all'agente come lezioni, avversari deboli finché il rating è provvisorio, un'altra sfida subito quando una viene rifiutata, prove limitate a N partite.
- Laboratorio dell'agente: crate Rust già scaricate, PyTorch CPU per l'addestramento, quote disco per i job.
- server: registro in un volume Docker dopo righe non viste fra connessioni SQLite, container etichettati per istanza e ripuliti all'avvio, correzioni delle prime ore (generatore di aperture, consegne identiche alla base, rating interrotti da un riavvio). Un solo `data/` e un solo `.env` alla radice.
- Sito: pagine Evoluzione, Codice, Mente e Laboratorio, sito bilingue con commenti su partite e verdetti scritti da Haiku, pubblico su darwin.esse.dev via Cloudflare Tunnel. Revisione di Diretta ed Evoluzione col concept B (colonne bilanciate, Elo con il margine al 95%, titoli brevi degli esperimenti, avanzamento dello SPRT in diretta), changelog 0.1.0 e 0.2.0.
- Esito: cinque generazioni nel pomeriggio; da gen-3 il campione ha un Elo assoluto contro Stockfish, fra 1.130 e 1.190 con margini di ± 120-140.

**Decisioni**: #17-#21 (provider Anthropic di default, librerie e niente GPU, registro in volume e istanze, sito pubblico bilingue con commenti separati dall'agente, Diretta a colonne bilanciate con Elo e margine).

**Prossimo passo**: aggiornare server senza interrompere sessione e partita, tradurre anche il resto, l'identità visiva del sito.

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
