# Roadmap

## Stato corrente

L'esperimento gira 24/7 su server dal 25 novembre: agente a sforzo alto, arbitro, bot Lichess sul campione in carica e sito pubblico su darwin.esse.dev. A fine giornata il campione è gen-8, circa 1.490 Elo contro Stockfish (± 115). Si aggiorna con `make deploy` senza interrompere sessione e partita. La storia è in `CYCLES.md`.

## Milestone

- [ ] **Lichess che gioca di nuovo**: Lichess risponde 429 alle sfide senza dire quanto aspettare, e il bot non gioca dalle 19:59. Il backoff fino a 4 ore è in produzione: se le sfide non riprendono, capire quale limite scatta (sfide per bot, per giorno) e tarare `DARWIN_LICHESS_CHALLENGE_EVERY_S` o puntare sulle sfide in arrivo.
- [ ] **Sforzo alto alla prova** (per DECISIONS #25): dopo una giornata, costo per sessione e resa delle consegne a `high` contro quelle a `low`; si torna a `medium` se il costo sale molto senza vantaggi.
- [ ] **Taratura di server**: test di carico di un'ora per tarare core e partite in parallelo (l'Air non ha ventola). L'arbitro è il collo di bottiglia, non il budget: il budget del 25 è stato usato per meno del 10%.
- [ ] **M6 Libro di aperture**: libro filtrato da Stockfish al posto di quello casuale generato dall'arbitro (per DECISIONS #10). La scala di ancore è già fatta.
