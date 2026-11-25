# Changelog

Le novità del laboratorio, dalla più recente.

## 0.4.0, 25 novembre 2026

- **Un sito più vivo**: ogni cosa ha il suo colore, uguale in tutte le pagine (la forza del campione in blu, le generazioni in viola, il verdetto in verde, la spesa in ambra, la diretta in corallo).
- **Attese animate**: mentre i dati arrivano un cavallo salta sulla scacchiera, se il laboratorio non risponde il re trema, quando non c'è ancora niente i pezzi scendono al loro posto.
- **Una partita alla volta**: la diretta segue una partita dall'inizio alla fine e mostra il risultato prima di passare alla successiva; il nostro motore sta sempre in basso, e le vittorie del match salgono partita dopo partita.

## 0.3.0, 25 novembre 2026

- **Tutto in italiano**: anche il pensiero dell'agente in diretta, la sua strategia, i suoi appunti e le istruzioni che riceve si leggono tradotti. L'originale in inglese resta a un clic; solo il codice resta com'è.
- **Aggiornamenti senza interruzioni**: quando il laboratorio si aggiorna, l'agente finisce il lavoro in corso e il bot finisce la sua partita su Lichess invece di abbandonarla.

## 0.2.0, 25 novembre 2026

La diretta e l'evoluzione ridisegnate per leggersi in un colpo d'occhio.

- **Titoli brevi**: ogni tentativo dell'agente ha un titolo di poche parole, in italiano e in inglese, al posto della sua ipotesi intera. L'ipotesi completa resta nei dettagli.
- **Un Elo onesto**: la forza del campione si legge con il suo margine di errore, e il grafico mostra quando due generazioni non si possono ancora distinguere. Il guadagno sul campione precedente è spiegato a parte.
- **Il giudizio in corso**: mentre l'arbitro giudica un candidato, la diretta mostra le partite giocate e da che parte pende la prova.
- **Una diretta che non si allunga**: tre colonne della stessa altezza, gli ultimi tre risultati e il rinvio alla storia completa. Il nome del sito è sempre nella barra.
- **Evoluzione compatta**: generazioni ed esperimenti in righe che si aprono, con i filtri per esito e dieci per pagina.

## 0.1.0, 25 novembre 2026

La prima versione: un'intelligenza artificiale scrive da sola un motore di scacchi e lo migliora una generazione dopo l'altra.

- **L'agente al lavoro**: un modello linguistico economico (Claude Haiku) riceve un motore vuoto e lo costruisce. A ogni sessione legge il verdetto precedente, fa una modifica e la consegna con la sua ipotesi. Ogni dieci sessioni si ferma a riflettere e riscrive la propria strategia.
- **Un arbitro che non si può ingannare**: ogni modifica viene compilata, controllata sulle regole degli scacchi e messa alla prova in centinaia di partite contro il campione in carica. Diventa la nuova generazione solo se vince in modo statisticamente sicuro. L'agente non può vedere né toccare l'arbitro.
- **La misura contro Stockfish**: ogni nuovo campione gioca contro Stockfish a forza limitata, per stimare il suo Elo assoluto.
- **Il campione su Lichess**: il bot darwin-chess-bot gioca di continuo contro altri bot con il campione del momento. Ogni sconfitta viene analizzata da Stockfish e torna all'agente come lezione.
- **La diretta**: la partita in corso, il pensiero dell'agente, l'ultimo verdetto e la spesa del giorno, aggiornati in tempo reale.
- **Un budget piccolo**: al massimo 2 dollari al giorno di modello linguistico, distribuiti sulle ore. Una sessione costa meno di un centesimo.
