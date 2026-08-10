"""Minimal stub of Supabase Auth's `auth.users` table.

This table is owned and migrated by Supabase Auth, not by us — we never
create/alter/drop it. It is declared here, on the SAME `Base.metadata`,
purely so that `ForeignKey("auth.users.id", ...)` columns elsewhere in our
models can resolve their referenced table locally (SQLAlchemy needs the
target `Table` object to exist in the same `MetaData` to compute FK
dependency ordering, e.g. in `sorted_tables`/autogenerate).

`alembic/env.py` filters this table (and anything in the `auth` schema) out
of autogenerate via `include_object`, so it never appears in a migration.
"""
from sqlalchemy import Column, Table
from sqlalchemy.dialects.postgresql import UUID

from app.db.session import Base

auth_users = Table(
    "users",
    Base.metadata,
    Column("id", UUID(as_uuid=True), primary_key=True),
    schema="auth",
)
