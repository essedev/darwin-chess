# Changelog

Le novità del laboratorio, dalla più recente.

## 0.6.0, 28 novembre 2026

- **Le partite su Lichess, una per una**: ogni partita finita del bot ha la sua pagina, con la scacchiera da scorrere mossa per mossa (anche con le frecce della tastiera), la curva della valutazione, le imprecisioni, gli errori e i gravi errori segnati come li segna Lichess, la mossa in cui la partita è girata e il commento. Prima il sito mostrava solo le ultime tre partite e rimandava a Lichess, dove l'analisi non c'è.
- **Tutte le partite, da filtrare**: l'elenco, diviso per giorno, si filtra per generazione, risultato, partite con punteggio, nome dell'avversario, bot o persona e cadenza. Filtri e pagina restano nell'indirizzo: tornando indietro da una partita l'elenco è come l'avevi lasciato. Ci si arriva dalle ultime partite della diretta.
- **I lavori lunghi dell'agente, con il loro scopo**: quando l'agente avvia un lavoro lungo (partite contro sé stesso, addestramento), dice in una frase a cosa serve. Nella diretta la frase compare sotto il suo pensiero, con il collegamento alla sessione che l'ha avviato; la pagina della sessione dice com'è finito e, se è andato storto, perché. I primi due si erano fermati subito dopo la compilazione per un errore nostro, ora corretto.
- **Il bot gioca tutto il giorno**: le sfide su Lichess sono distribuite sulle ore invece di esaurirsi nelle prime cinque, e un avversario che ha già giocato 10 partite in un giorno viene rifiutato, così nessuno tiene il bot per sé. La forza di una generazione su Lichess conta solo le partite con punteggio.
- **Comodo anche sul telefono**: nessuna pagina scorre di lato, l'aiuto si apre dentro lo schermo e i nomi delle generazioni sotto il grafico dell'Elo non si sovrappongono più.

## 0.5.0, 26 novembre 2026

- **Guarda l'agente al lavoro**: ogni sessione ha la sua pagina, con tutto quello che l'agente fa, un'azione per riga e in parole semplici ("legge main.rs", "compila", "gioca un match di prova: 60 partite", "aspetta 15 minuti"). Il comando vero e quello che gli ha risposto sono a un clic; in mezzo i suoi pensieri e il suo ragionamento, che resta in inglese. Mentre la sessione è in corso la pagina si aggiorna da sola, e alla fine dice com'è andata.
- **Niente più scacchiera vuota**: quando l'arbitro non sta giocando, al centro della diretta c'è la sessione in corso, con l'azione di adesso, il conto alla rovescia quando l'agente aspetta e le ultime righe. Con una partita in corso, sotto la scacchiera una riga dice cosa sta facendo.
- **Sempre a portata di mano**: alla sessione si arriva dalla barra in alto della diretta, da ogni tentativo in Evoluzione, dalle modifiche nel Codice e da Mente, che mostra a cosa sta lavorando l'agente in questo momento.

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
