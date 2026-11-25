# Roadmap

## Stato corrente

Arbitro pronto (M1): `darwin.referee.judge` riceve un commit del genoma e una fase e restituisce il verdetto, con i cancelli build, perft, smoke e match. Testato con motori Python veri, anche difettosi apposta; manca ancora un'accettazione completa su un genoma Rust vero, che arriva con le iterazioni di prova di M3.

## Milestone

- [x] **M1 Arbitro**: compilazione pulita da un commit, perft su posizioni casuali con dettaglio per mossa, partite giocate da fastchess nel container `arena` con un container per motore, rilettura dei PGN con python-chess, SPRT a lotti calcolato da noi, giocatore casuale come prima ancora, cancelli per fase. Testato con motori UCI veri, anche difettosi apposta.
- [ ] **M2 Registro**: modelli e prima migrazione delle tabelle in `DATABASE_SCHEMA.md`.
- [ ] **M3 Orchestratore**: ciclo delle generazioni con pi in modalità RPC (versione fissata), estensione con `perft_check`, `submit`, `experiments`, `run_job`, risveglio a eventi, riflessione periodica, spesa distribuita sulle ore entro 2 $/giorno. Prima di lasciarlo libero: 3 iterazioni di prova con costo misurato.
- [ ] **M4 Dashboard**: la direzione D del concept (`docs/concepts/concept-a-dashboard.html`): generazione corrente in alto, storia a sinistra, scacchiera con giocatori e mosse, sottotitoli dell'agente, carte SPRT e spesa. Dati via SSE dall'API. Pezzi cburnett copiati nel repo con la licenza.
- [ ] **M5 Deploy e Lichess**: servizi `core` e `api` in Docker Compose su server, test di carico di un'ora per tarare core e partite in parallelo (l'Air non ha ventola). Bot Lichess sempre sul campione in carica, che gioca di continuo contro altri bot (serve un account BOT creato da Simone). Le sconfitte vanno in una coda di lezioni, analizzate da Stockfish lato arbitro, e l'agente le riceve riassunte prima di ogni iterazione. Performance Lichess calcolata per generazione.
- [ ] **M6 Ancore**: Stockfish a forza limitata per l'Elo assoluto, e libro di aperture filtrato da Stockfish al posto di quello casuale.
