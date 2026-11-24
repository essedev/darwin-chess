from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Declarative base for the ledger tables (see docs/DATABASE_SCHEMA.md)."""
