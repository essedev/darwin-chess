# Roadmap

## Stato corrente

La pipeline è completa in locale: arbitro, registro, orchestratore con pi, dashboard, scala di ancore Stockfish e servizi `core` e `api` in Compose (`make up`). È stata provata solo senza spendere: sessione completa contro un modello finto, cancelli dell'arbitro con motori Python veri. Mancano la prima iterazione con il modello vero, quindi un genoma Rust scritto dall'agente che passi per l'arbitro, e la messa in esercizio su server. La storia di M1-M4 è in `CYCLES.md`.

## Milestone

- [ ] **Prove a pagamento** (chiude M3): 3 iterazioni con costo misurato, stimato e approvato prima del lancio (`make run-sessions n=3`), che fanno anche da prima accettazione di un genoma Rust vero. Serve la chiave del provider (Anthropic di default, per DECISIONS #17).
- [ ] **M5 Deploy e Lichess**: già fatto l'avvio in Compose, provato in locale. Da fare: deploy su server e test di carico di un'ora per tarare core e partite in parallelo (l'Air non ha ventola). Bot Lichess sempre sul campione in carica, che gioca di continuo contro altri bot (serve un account BOT creato da Simone). Le sconfitte vanno in una coda di lezioni, analizzate da Stockfish lato arbitro, e l'agente le riceve riassunte prima di ogni iterazione (per DECISIONS #9). Performance Lichess calcolata per generazione.
- [ ] **M6 Libro di aperture**: libro filtrato da Stockfish al posto di quello casuale generato dall'arbitro (per DECISIONS #10). La scala di ancore è già fatta.
