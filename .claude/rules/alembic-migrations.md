---
paths:
  - "backend/alembic/versions/*.py"
---
- The ledger is append-only: no migrations that delete or rewrite historical rows.
- SQLite: constraint changes go through `op.batch_alter_table` (render_as_batch is on).
- The `down_revision` of a migration already applied is never rewritten: add a new migration.
- `docs/DATABASE_SCHEMA.md` changes in the same commit.
