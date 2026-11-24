---
paths:
  - "backend/alembic/versions/*.py"
---
- Il registro è append-only: niente migrazioni che cancellano o riscrivono righe storiche.
- SQLite: le modifiche ai vincoli passano da `op.batch_alter_table` (render_as_batch è attivo).
- `down_revision` di una migrazione già applicata non si riscrive: si aggiunge una migrazione nuova.
- `docs/DATABASE_SCHEMA.md` cambia nello stesso commit.
