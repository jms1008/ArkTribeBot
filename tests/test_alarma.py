"""Tests del cog Alarma: panel embed y detección de intrusos."""

import aiosqlite
import pytest

from cogs import alarma as alarma_mod
from db.schema import create_indexes, create_tables, run_migrations


@pytest.fixture
async def db_path(tmp_path):
    """Crea una DB temporal con el esquema real (para los tests de detección que
    necesitan abrir conexiones efímeras directamente)."""
    path = str(tmp_path / "test.db")
    async with aiosqlite.connect(path) as db:
        await create_tables(db)
        await run_migrations(db)
        await create_indexes(db)
        await db.commit()
    return path


class TestBuildAlarmasEmbed:
    @pytest.mark.asyncio
    async def test_empty_state(self, mock_bot):
        """Sin alarmas registradas → embed muestra estado vacío."""
        await mock_bot.init_mock_db()
        embed = await alarma_mod.build_alarmas_embed(mock_bot, guild_id=1, user_id=42)
        assert "PANEL DE ALARMAS" in embed.title
        assert "No tienes ninguna alarma" in embed.description

    @pytest.mark.asyncio
    async def test_lists_user_alarms(self, mock_bot):
        """Sólo se listan las alarmas del usuario actual; no las de otros usuarios o guilds."""
        await mock_bot.init_mock_db()
        await mock_bot.db.executemany(
            "INSERT INTO map_alarms (guild_id, user_id, map_name, channel_id) VALUES (?, ?, ?, ?)",
            [
                (1, 42, "Ragnarok", 100),
                (1, 42, "TheIsland", 100),
                (1, 99, "Aberration", 100),  # Otro usuario
                (2, 42, "Extinction", 100),  # Otro guild
            ],
        )
        await mock_bot.db.commit()

        embed = await alarma_mod.build_alarmas_embed(mock_bot, guild_id=1, user_id=42)
        desc = embed.description
        assert "Ragnarok" in desc
        assert "TheIsland" in desc
        assert "Aberration" not in desc  # No es del usuario
        assert "Extinction" not in desc  # No es del guild


class TestIntruderDetection:
    """Tests de la lógica de detección de nuevos jugadores no familiares.

    Verifica las reglas clave:
    - Solo jugadores que NO estaban antes son candidatos.
    - Se excluyen miembros de la tribu propia (k4ultra_fixed_tribes.is_own=1).
    - Se excluyen personajes registrados en tribe_characters.
    """

    @pytest.mark.asyncio
    async def test_new_player_unknown_is_flagged(self, db_path):
        """Un jugador que no estaba antes y no es de la tribu se detecta como intruso."""
        current = {"Intruso", "AliadoConocido"}
        previous = {"AliadoConocido"}

        async with aiosqlite.connect(db_path) as db:
            db.row_factory = aiosqlite.Row
            own_rows = await (
                await db.execute(
                    "SELECT members_json FROM k4ultra_fixed_tribes WHERE guild_id = ? AND is_own = 1",
                    (1,),
                )
            ).fetchall()
            assert own_rows == []  # No hay tribu propia

            new_entries = current - previous
            assert new_entries == {"Intruso"}

            intruders = []
            for name in new_entries:
                check = await (
                    await db.execute(
                        "SELECT 1 FROM tribe_characters WHERE guild_id = ? AND LOWER(character_name) = LOWER(?)",
                        (1, name),
                    )
                ).fetchone()
                if not check:
                    intruders.append(name)

            assert intruders == ["Intruso"]

    @pytest.mark.asyncio
    async def test_own_tribe_member_is_excluded(self, db_path):
        """Si el jugador nuevo está en la tribu propia (is_own=1), no es intruso."""
        import json

        async with aiosqlite.connect(db_path) as db:
            await db.execute(
                "INSERT INTO k4ultra_fixed_tribes (guild_id, name, members_json, is_own) VALUES (?, ?, ?, ?)",
                (1, "MiTribu", json.dumps(["Alice", "Bob"]), 1),
            )
            await db.commit()

        current = {"Alice", "Carol"}
        previous = {"Carol"}
        new_entries = current - previous  # {"Alice"}

        async with aiosqlite.connect(db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT members_json FROM k4ultra_fixed_tribes WHERE guild_id = ? AND is_own = 1",
                (1,),
            )
            own_members = set()
            for r in await cursor.fetchall():
                for m in json.loads(r["members_json"]):
                    own_members.add(m.lower())

        intruders = [n for n in new_entries if n.lower() not in own_members]
        assert intruders == []  # Alice es de la tribu propia

    @pytest.mark.asyncio
    async def test_registered_character_is_excluded(self, db_path):
        """Un personaje en tribe_characters no se considera intruso."""
        async with aiosqlite.connect(db_path) as db:
            await db.execute(
                "INSERT INTO tribe_characters (character_name, guild_id, player_name) VALUES (?, ?, ?)",
                ("DinoMan", 1, "AliceUser"),
            )
            await db.commit()

        async with aiosqlite.connect(db_path) as db:
            db.row_factory = aiosqlite.Row
            check = await (
                await db.execute(
                    "SELECT 1 FROM tribe_characters WHERE guild_id = ? AND LOWER(character_name) = LOWER(?)",
                    (1, "dinoman"),  # case insensitive
                )
            ).fetchone()
            assert check is not None
