"""Tests del wrapper Database (db/database.py)."""

import pytest

from db.database import Database
from db.schema import create_tables


@pytest.mark.asyncio
async def test_connect_open_and_close(tmp_path):
    db = Database(str(tmp_path / "t.db"))
    await db.connect()
    assert db.conn is not None
    await db.close()
    # Tras cerrar, acceder a .conn debe avisar claramente.
    with pytest.raises(RuntimeError):
        _ = db.conn


@pytest.mark.asyncio
async def test_helpers_roundtrip(tmp_path):
    db = Database(str(tmp_path / "t.db"))
    await db.connect()
    try:
        await create_tables(db.conn)
        await db.execute(
            "INSERT INTO guild_config (guild_id, update_interval) VALUES (?, ?)",
            (42, 5),
        )
        await db.commit()

        row = await db.fetchone("SELECT update_interval FROM guild_config WHERE guild_id = ?", (42,))
        assert row is not None
        assert row["update_interval"] == 5

        rows = await db.fetchall("SELECT guild_id FROM guild_config")
        assert [r["guild_id"] for r in rows] == [42]
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_transaction_rolls_back_on_error(tmp_path):
    db = Database(str(tmp_path / "t.db"))
    await db.connect()
    try:
        await create_tables(db.conn)

        with pytest.raises(RuntimeError):
            async with db.transaction() as conn:
                await conn.execute("INSERT INTO guild_config (guild_id) VALUES (?)", (1,))
                raise RuntimeError("simulated failure")

        # La fila no debe haberse persistido.
        row = await db.fetchone("SELECT guild_id FROM guild_config WHERE guild_id = ?", (1,))
        assert row is None
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_transaction_commits_on_success(tmp_path):
    db = Database(str(tmp_path / "t.db"))
    await db.connect()
    try:
        await create_tables(db.conn)

        async with db.transaction() as conn:
            await conn.execute("INSERT INTO guild_config (guild_id) VALUES (?)", (2,))

        row = await db.fetchone("SELECT guild_id FROM guild_config WHERE guild_id = ?", (2,))
        assert row is not None
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_connect_is_idempotent(tmp_path):
    """Llamar connect() dos veces no debe romper ni abrir dos conexiones."""
    db = Database(str(tmp_path / "t.db"))
    await db.connect()
    first = db.conn
    await db.connect()
    assert db.conn is first
    await db.close()
