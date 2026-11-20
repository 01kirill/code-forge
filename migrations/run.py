import asyncio

from alembic import context
from codeforge.common.runtime import settings
from sqlalchemy import pool, text
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine


def migrate(connection: Connection) -> None:
    context.configure(connection=connection)
    with context.begin_transaction():
        context.run_migrations()


async def run() -> None:
    config = context.config
    cfg = settings()
    dsn = {"auth": cfg.auth_db, "contest": cfg.contest_db}[config.config_ini_section]
    engine = create_async_engine(
        dsn.replace("postgresql://", "postgresql+asyncpg://", 1),
        poolclass=pool.NullPool,
    )
    try:
        async with engine.begin() as connection:
            await connection.execute(text("SELECT pg_advisory_xact_lock(137920260)"))
            await connection.run_sync(migrate)
    finally:
        await engine.dispose()


asyncio.run(run())
