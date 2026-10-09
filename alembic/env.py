import asyncio
import os
import sys
from logging.config import fileConfig
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config
from alembic import context

# Append current directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.config import settings
from app.db.models import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

def get_normalized_database_url() -> str:
    raw_url = os.getenv("DATABASE_URL") or settings.DATABASE_URL
    clean = (raw_url or "").strip()
    if clean.startswith("postgres://"):
        return "postgresql+asyncpg://" + clean[len("postgres://"):]
    if clean.startswith("postgresql://"):
        return "postgresql+asyncpg://" + clean[len("postgresql://"):]
    if clean.startswith("postgresql+psycopg://"):
        return "postgresql+asyncpg://" + clean[len("postgresql+psycopg://"):]
    if clean.startswith("postgresql+psycopg2://"):
        return "postgresql+asyncpg://" + clean[len("postgresql+psycopg2://"):]
    return clean

def run_migrations_offline() -> None:
    url = get_normalized_database_url()
    if url.startswith("postgresql+asyncpg://"):
        url = "postgresql://" + url[len("postgresql+asyncpg://"):]
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()

def do_run_migrations(connection):
    context.configure(
        connection=connection,
        target_metadata=target_metadata
    )
    with context.begin_transaction():
        context.run_migrations()

async def run_async_migrations() -> None:
    configuration = config.get_section(config.config_ini_section) or {}
    configuration["sqlalchemy.url"] = get_normalized_database_url()

    connectable = async_engine_from_config(
        configuration,
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

