"""Conexión persistente a SQLite con helpers de uso común.

Patrón: una sola ``aiosqlite.Connection`` por proceso, expuesta como ``bot.db``.

Por qué una sola conexión:
- ``WAL`` (activado en ``db/schema.py``) permite múltiples lecturas concurrentes
  y una escritura en curso — no necesitamos un pool real.
- Evita reabrir el fichero en cada query (las 125+ ocurrencias previas).
- Las transacciones quedan implícitas en aiosqlite (commit explícito).

Concurrencia:
- ``aiosqlite`` ya serializa las operaciones internamente (cada conexión es un
  worker thread con su queue), así que no necesitamos lock externo para evitar
  corrupción.
- Para *transacciones explícitas* exponemos ``transaction()`` como contexto.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable, Sequence
from contextlib import asynccontextmanager
from typing import Any

import aiosqlite

from db.schema import apply_pragmas

logger = logging.getLogger("ArkTribeBot")


class Database:
    """Wrapper sobre ``aiosqlite.Connection`` con helpers de conveniencia."""

    def __init__(self, path: str):
        self.path = path
        self._conn: aiosqlite.Connection | None = None

    # --- ciclo de vida -------------------------------------------------------

    async def connect(self) -> None:
        """Abre la conexión persistente y aplica PRAGMAs + row_factory."""
        if self._conn is not None:
            return
        self._conn = await aiosqlite.connect(self.path)
        self._conn.row_factory = aiosqlite.Row
        await apply_pragmas(self._conn)
        logger.info(f"[DB] Conexión persistente abierta sobre {self.path}")

    async def close(self) -> None:
        if self._conn is None:
            return
        await self._conn.close()
        self._conn = None
        logger.info("[DB] Conexión persistente cerrada")

    @property
    def conn(self) -> aiosqlite.Connection:
        """Conexión cruda para casos que necesiten ``async with db.execute(...)``."""
        if self._conn is None:
            raise RuntimeError("Database no conectada — llama a connect() en setup_hook")
        return self._conn

    # --- helpers de query ----------------------------------------------------

    async def execute(self, sql: str, params: Sequence[Any] | None = None) -> aiosqlite.Cursor:
        """Ejecuta una sentencia (sin commit). Devuelve el cursor."""
        return await self.conn.execute(sql, params or ())

    async def executemany(self, sql: str, seq_of_params: Iterable[Sequence[Any]]) -> None:
        await self.conn.executemany(sql, seq_of_params)

    async def fetchone(self, sql: str, params: Sequence[Any] | None = None) -> aiosqlite.Row | None:
        async with self.conn.execute(sql, params or ()) as cursor:
            return await cursor.fetchone()

    async def fetchall(self, sql: str, params: Sequence[Any] | None = None) -> list[aiosqlite.Row]:
        async with self.conn.execute(sql, params or ()) as cursor:
            return list(await cursor.fetchall())

    async def commit(self) -> None:
        await self.conn.commit()

    @asynccontextmanager
    async def transaction(self):
        """Context manager para transacciones explícitas.

        Hace ``commit`` al salir si no hubo excepción, ``rollback`` si hubo.
        Usar para bloques con varias escrituras que deban aplicarse atómicamente.
        """
        try:
            yield self.conn
            await self.conn.commit()
        except Exception:
            await self.conn.rollback()
            raise
