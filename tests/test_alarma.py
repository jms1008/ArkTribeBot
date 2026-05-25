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
        embed = await alarma_mod.build_alarmas_embed(mock_bot, guild_id=1)
        assert "PANEL DE ALARMAS" in embed.title
        assert "Nadie en la tribu" in embed.description

    @pytest.mark.asyncio
    async def test_lists_all_guild_alarms(self, mock_bot):
        """Panel compartido: muestra alarmas de TODOS los usuarios del guild,
        agrupadas por mapa con mención de los watchers. Excluye otros guilds."""
        await mock_bot.init_mock_db()
        await mock_bot.db.executemany(
            "INSERT INTO map_alarms (guild_id, user_id, map_name, channel_id) VALUES (?, ?, ?, ?)",
            [
                (1, 42, "Ragnarok", 100),
                (1, 42, "TheIsland", 100),
                (1, 99, "Aberration", 100),  # Otro usuario del MISMO guild → debe aparecer
                (2, 42, "Extinction", 100),  # Otro guild → debe excluirse
            ],
        )
        await mock_bot.db.commit()

        embed = await alarma_mod.build_alarmas_embed(mock_bot, guild_id=1)
        desc = embed.description
        # Los 3 mapas del guild 1 deben aparecer.
        assert "Ragnarok" in desc
        assert "TheIsland" in desc
        assert "Aberration" in desc
        # Y se mencionan los usuarios que vigilan cada uno.
        assert "<@42>" in desc
        assert "<@99>" in desc
        # El otro guild se excluye.
        assert "Extinction" not in desc

    @pytest.mark.asyncio
    async def test_groups_watchers_per_map(self, mock_bot):
        """Si varios usuarios vigilan el mismo mapa, todos se listan juntos."""
        await mock_bot.init_mock_db()
        await mock_bot.db.executemany(
            "INSERT INTO map_alarms (guild_id, user_id, map_name, channel_id) VALUES (?, ?, ?, ?)",
            [
                (1, 42, "Ragnarok", 100),
                (1, 99, "Ragnarok", 100),  # Mismo mapa, otro usuario
            ],
        )
        await mock_bot.db.commit()

        embed = await alarma_mod.build_alarmas_embed(mock_bot, guild_id=1)
        desc = embed.description
        # Ragnarok aparece UNA vez con ambos watchers en la misma línea.
        assert desc.count("Ragnarok") == 1
        assert "<@42>" in desc
        assert "<@99>" in desc


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
    async def test_allied_tribe_members_are_excluded(self, mock_bot):
        """Miembros de una tribu marcada como aliada (is_ally=1) NO se consideran intrusos.

        Verifica el helper `_get_trusted_members` que une tribu propia + aliadas.
        """
        import json

        await mock_bot.init_mock_db()
        # Tribu propia + tribu aliada en el mismo guild.
        await mock_bot.db.executemany(
            "INSERT INTO k4ultra_fixed_tribes (guild_id, name, members_json, is_own, is_ally) "
            "VALUES (?, ?, ?, ?, ?)",
            [
                (1, "MiTribu", json.dumps(["Alice", "Bob"]), 1, 0),
                (1, "AliadosDelEste", json.dumps(["Charlie", "Dave"]), 0, 1),
                (1, "OtraTribu", json.dumps(["Mallory"]), 0, 0),  # No propia ni aliada
            ],
        )
        await mock_bot.db.commit()

        trusted = await alarma_mod._get_trusted_members(mock_bot, guild_id=1)
        # Propios + aliados, todos en lowercase.
        assert trusted == {"alice", "bob", "charlie", "dave"}
        # Mallory NO está → seguirá disparando alarma.
        assert "mallory" not in trusted

    @pytest.mark.asyncio
    async def test_trusted_members_isolated_per_guild(self, mock_bot):
        """Las tribus aliadas de un guild no afectan a las de otro guild."""
        import json

        await mock_bot.init_mock_db()
        await mock_bot.db.executemany(
            "INSERT INTO k4ultra_fixed_tribes (guild_id, name, members_json, is_own, is_ally) "
            "VALUES (?, ?, ?, ?, ?)",
            [
                (1, "AliadosG1", json.dumps(["Alice"]), 0, 1),
                (2, "AliadosG2", json.dumps(["Bob"]), 0, 1),
            ],
        )
        await mock_bot.db.commit()

        trusted_g1 = await alarma_mod._get_trusted_members(mock_bot, guild_id=1)
        trusted_g2 = await alarma_mod._get_trusted_members(mock_bot, guild_id=2)
        assert trusted_g1 == {"alice"}
        assert trusted_g2 == {"bob"}

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
