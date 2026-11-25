---
paths:
  - "backend/src/darwin/api/**/*.py"
---
- The API reads the ledger and streams events: it does not write and does not command the orchestrator.
- Static routes before parametric ones; all under `/api`.
- Thin routers: queries live in the `darwin.ledger` module, never SQL in a router.
- A router not registered in `app.py` is unreachable.
