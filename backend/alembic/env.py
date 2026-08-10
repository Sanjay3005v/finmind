import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

# Make `app.*` importable regardless of the cwd alembic is invoked from.
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.config import get_settings  # noqa: E402
import app.models  # noqa: E402,F401  (registers every model on Base.metadata)
from app.db.session import Base  # noqa: E402

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Our ORM metadata — enables `alembic revision --autogenerate`.
target_metadata = Base.metadata

# Use the same DATABASE_URL the app itself reads from `.env`/environment,
# so migrations always target the same database as the running service.
config.set_main_option("sqlalchemy.url", get_settings().DATABASE_URL)


def include_object(object, name, type_, reflected, compare_to):
    """Never manage `auth.*` — that schema belongs to Supabase Auth. It's
    only present in our metadata (see `app/models/_supabase_auth_stub.py`)
    so local ForeignKey columns can resolve their referenced table."""
    if getattr(object, "schema", None) == "auth":
        return False
    return True


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (emits SQL without a DB connection)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_object=include_object,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection, target_metadata=target_metadata, include_object=include_object
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Create an async Engine and run migrations against it (online mode)."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
