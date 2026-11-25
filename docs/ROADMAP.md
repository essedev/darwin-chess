# Roadmap

## Stato corrente

Scaffold pronto: backend con config e health check, dashboard placeholder, sandbox Docker funzionante, genoma `gen-0` creato e compilato offline nel sandbox.

## Milestone

- [ ] **M1 Arbitro**: perft su posizioni casuali con dettaglio per mossa, partite UCI con controllo del tempo e legalità, motore per partita in container effimero, SPRT. Testato con un motore UCI di riferimento.
- [ ] **M2 Registro**: modelli e prima migrazione delle tabelle in `DATABASE_SCHEMA.md`.
- [ ] **M3 Orchestratore**: ciclo delle generazioni, tool dell'agente, client OpenRouter con Haiku 5.5, tetto di 2 $/giorno. Prima di lasciarlo libero: 3 iterazioni di prova con costo misurato.
- [ ] **M4 Dashboard**: la direzione D del concept (`docs/concepts/concept-a-dashboard.html`): generazione corrente in alto, storia a sinistra, scacchiera con giocatori e mosse, sottotitoli dell'agente, carte SPRT e spesa. Dati via SSE dall'API. Pezzi cburnett copiati nel repo con la licenza.
- [ ] **M5 Deploy e Lichess**: servizi in Docker Compose su server. Bot Lichess sempre sul campione in carica, che gioca di continuo contro altri bot (serve un account BOT creato da Simone). Le sconfitte vanno in una coda di lezioni, analizzate da Stockfish lato arbitro, e l'agente le riceve riassunte prima di ogni iterazione. Performance Lichess calcolata per generazione.
- [ ] **M6 Ancore**: Stockfish a forza limitata e giocatore casuale per l'Elo assoluto.
