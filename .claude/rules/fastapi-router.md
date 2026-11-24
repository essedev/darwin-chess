---
paths:
  - "backend/src/darwin/api/**/*.py"
---
- L'API legge il registro e trasmette eventi: non scrive e non comanda l'orchestratore.
- Rotte statiche prima delle parametriche; tutte sotto `/api`.
- Router sottile: query nel modulo `darwin.ledger`, mai SQL nel router.
- Un router non registrato in `app.py` non è raggiungibile.
