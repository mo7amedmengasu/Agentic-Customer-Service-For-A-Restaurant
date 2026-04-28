from typing import Optional

from langgraph.checkpoint.postgres import PostgresSaver
from psycopg_pool import ConnectionPool

from app.core.config import settings


_pool: Optional[ConnectionPool] = None
_checkpointer: Optional[PostgresSaver] = None


def _get_pool() -> ConnectionPool:
    global _pool
    if _pool is None:
        _pool = ConnectionPool(
            conninfo=settings.DATABASE_URL,
            max_size=20,
            kwargs={"autocommit": True, "prepare_threshold": 0},
            open=True,
        )
    return _pool


def get_checkpointer() -> PostgresSaver:
    global _checkpointer
    if _checkpointer is None:
        _checkpointer = PostgresSaver(_get_pool())
    return _checkpointer


def setup_checkpointer() -> None:
    get_checkpointer().setup()


def shutdown_checkpointer() -> None:
    global _pool, _checkpointer
    if _pool is not None:
        _pool.close()
        _pool = None
    _checkpointer = None
