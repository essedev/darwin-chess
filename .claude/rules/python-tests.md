---
paths:
  - "backend/tests/**/*.py"
---
- Integration sul registro SQLite vero in `tmp_path`, mai mock del database.
- I test dell'arbitro usano un motore UCI vero, non risposte simulate.
- I test che chiamano un LLM stanno dietro `@pytest.mark.llm` e non girano in `make test`: costano.
- Un run di pytest alla volta.
