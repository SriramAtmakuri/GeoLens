import asyncpg
from pgvector.asyncpg import register_vector
from app.config import settings

_pool: asyncpg.Pool | None = None


async def _init_conn(conn: asyncpg.Connection) -> None:
    await register_vector(conn)


async def get_pool() -> asyncpg.Pool:
    return _pool


async def init_db() -> None:
    global _pool
    _pool = await asyncpg.create_pool(
        settings.database_url,
        init=_init_conn,
        min_size=2,
        max_size=10,
        command_timeout=60,
    )


async def close_db() -> None:
    global _pool
    if _pool:
        await _pool.close()
