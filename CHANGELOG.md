# Changelog

Le novità del laboratorio, dalla più recente.

## 0.1.0, 25 novembre 2026

La prima versione: un'intelligenza artificiale scrive da sola un motore di scacchi e lo migliora una generazione dopo l'altra.

- **L'agente al lavoro**: un modello linguistico economico (Claude Haiku) riceve un motore vuoto e lo costruisce. A ogni sessione legge il verdetto precedente, fa una modifica e la consegna con la sua ipotesi. Ogni dieci sessioni si ferma a riflettere e riscrive la propria strategia.
- **Un arbitro che non si può ingannare**: ogni modifica viene compilata, controllata sulle regole degli scacchi e messa alla prova in centinaia di partite contro il campione in carica. Diventa la nuova generazione solo se vince in modo statisticamente sicuro. L'agente non può vedere né toccare l'arbitro.
- **La misura contro Stockfish**: ogni nuovo campione gioca contro Stockfish a forza limitata, per stimare il suo Elo assoluto.
- **Il campione su Lichess**: il bot darwin-chess-bot gioca di continuo contro altri bot con il campione del momento. Ogni sconfitta viene analizzata da Stockfish e torna all'agente come lezione.
- **La diretta**: la partita in corso, il pensiero dell'agente, l'ultimo verdetto e la spesa del giorno, aggiornati in tempo reale.
- **Un budget piccolo**: al massimo 2 dollari al giorno di modello linguistico, distribuiti sulle ore. Una sessione costa meno di un centesimo.
