---
paths:
  - "backend/tests/**/*.py"
---
- Integration tests on the real SQLite ledger in `tmp_path`, never a mocked database.
- Referee tests use a real UCI engine, not simulated answers.
- Tests that call an LLM sit behind `@pytest.mark.llm` and do not run in `make test`: they cost money.
- One pytest run at a time.
