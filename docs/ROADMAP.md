# Roadmap

## Stato corrente

Arbitro pronto (M1): `darwin.referee.judge` riceve un commit del genoma e una fase e restituisce il verdetto, con i cancelli build, perft, smoke e match. Testato con motori Python veri, anche difettosi apposta; manca ancora un'accettazione completa su un genoma Rust vero, che arriva con le iterazioni di prova di M3.

## Milestone

- [x] **M1 Arbitro**: compilazione pulita da un commit, perft su posizioni casuali con dettaglio per mossa, partite giocate da fastchess nel container `arena` con un container per motore, rilettura dei PGN con python-chess, SPRT a lotti calcolato da noi, giocatore casuale come prima ancora, cancelli per fase. Testato con motori UCI veri, anche difettosi apposta.
- [x] **M2 Registro**: modelli e prima migrazione delle tabelle in `DATABASE_SCHEMA.md`.
- [x] **M3 Orchestratore**: ciclo delle generazioni con pi in modalità RPC (versione fissata), estensione con `perft_check`, `submit`, `experiments`, `run_job`, risveglio a eventi, riflessione periodica, spesa distribuita sulle ore entro 2 $/giorno. Provato da capo a fondo con un modello finto. Mancano le 3 iterazioni di prova a pagamento con costo misurato (serve la chiave OpenRouter) e la verifica dell'ID esatto di Haiku 5.5 su OpenRouter.
- [x] **M4 Dashboard**: la direzione D del concept (`docs/concepts/concept-a-dashboard.html`): generazione corrente in alto, storia a sinistra, scacchiera con giocatori e mosse, sottotitoli dell'agente, carte SPRT e spesa. Dati via SSE dall'API. Pezzi cburnett copiati nel repo con la licenza. L'Elo mostrato è relativo al giocatore casuale (somma dei guadagni): quello assoluto arriva con le ancore di M6.
- [ ] **M5 Deploy e Lichess**: fatto: immagine `darwin-backend` e servizi `core` e `api` in Compose (`make up`), provati in locale. Da fare: deploy su server, test di carico di un'ora per tarare core e partite in parallelo (l'Air non ha ventola). Bot Lichess sempre sul campione in carica, che gioca di continuo contro altri bot (serve un account BOT creato da Simone). Le sconfitte vanno in una coda di lezioni, analizzate da Stockfish lato arbitro, e l'agente le riceve riassunte prima di ogni iterazione. Performance Lichess calcolata per generazione.
- [ ] **M6 Ancore**: fatto: Stockfish 17 a forza limitata (`UCI_Elo` da 1320 a 2800) come scala, ogni nuovo campione viene misurato dopo la promozione e la dashboard mostra l'Elo assoluto. Da fare: libro di aperture filtrato da Stockfish al posto di quello casuale.
