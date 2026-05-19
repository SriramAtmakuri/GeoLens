"""ARQ worker settings: arq workers.run.WorkerSettings"""
import asyncpg
from pgvector.asyncpg import register_vector
from arq.connections import RedisSettings
from app.config import settings
from workers.ingestion_worker import process_ingestion


async def startup(ctx):
    async def _init(conn):
        await register_vector(conn)

    ctx["pool"] = await asyncpg.create_pool(
        settings.database_url,
        init=_init,
        min_size=1,
        max_size=5,
    )


async def shutdown(ctx):
    await ctx["pool"].close()


class WorkerSettings:
    functions = [process_ingestion]
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    max_jobs = 4
    job_timeout = 600
