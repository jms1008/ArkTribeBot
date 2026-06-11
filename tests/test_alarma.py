"""Tests del cog Alarma: panel embed y detección de intrusos."""

from collections import Counter

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


class TestCounterDiff:
    """Tests de la lógica Counter-based para detectar duplicados de nombre.

    Caso real: varios jugadores comparten el mismo Steam name (ej: "123", "bob")
    y necesitamos disparar la alarma cuando entra UNO MÁS, aunque ya hubiera
    otro online con el mismo nombre.
    """

    def test_counter_diff_detects_count_increase(self):
        """Si el contador de un nombre aumenta entre dos ticks → alarma."""
        prev = Counter(["alice", "bob", "123"])
        current = Counter(["alice", "bob", "123", "123"])  # un "123" más

        diff = current - prev
        assert dict(diff) == {"123": 1}
        assert "123" in set(diff.keys())

    def test_counter_diff_ignores_known_player(self):
        """Mismo conjunto → ningún nombre nuevo."""
        prev = Counter(["alice", "bob"])
        current = Counter(["alice", "bob"])
        diff = current - prev
        assert dict(diff) == {}

    def test_counter_diff_detects_brand_new_name(self):
        """Un nombre que no estaba antes aparece como nuevo (delta=1)."""
        prev = Counter(["alice"])
        current = Counter(["alice", "mallory"])
        diff = current - prev
        assert dict(diff) == {"mallory": 1}

    def test_counter_diff_ignores_disconnects(self):
        """Si alguien desconecta (cuenta baja), Counter - Counter no lo reporta."""
        prev = Counter(["alice", "bob", "123", "123"])
        current = Counter(["alice", "bob", "123"])  # un "123" desconectó
        diff = current - prev
        assert dict(diff) == {}  # No hay claves con delta positivo

    def test_counter_round_trip_via_json(self):
        """El snapshot se serializa como lista con duplicados expandidos
        (Counter.elements()) y se reconstruye correctamente al leer."""
        import json

        original = Counter(["alice", "123", "123", "bob"])
        serialized = json.dumps(list(original.elements()))
        # JSON-stable order, pero el Counter resultante es equivalente.
        deserialized = Counter(json.loads(serialized))
        assert deserialized == original


class TestAlertDelivery:
    """Tests del DM agrupado: _deliver_intruder_alert mantiene UN mensaje-resumen
    por usuario+mapa, editándolo dentro de la ventana y renovándolo después."""

    def _make_user(self, mocker, msg_id=111):
        """Mock de discord.User con DM channel funcional."""
        msg = mocker.MagicMock()
        msg.id = msg_id
        msg.edit = mocker.AsyncMock()
        msg.delete = mocker.AsyncMock()

        dm = mocker.MagicMock()
        dm.send = mocker.AsyncMock(return_value=msg)
        dm.fetch_message = mocker.AsyncMock(return_value=msg)

        user = mocker.MagicMock()
        user.dm_channel = dm
        return user, dm, msg

    @pytest.mark.asyncio
    async def test_first_alert_sends_new_dm_and_tracks_it(self, mock_bot, mocker):
        await mock_bot.init_mock_db()
        user, dm, msg = self._make_user(mocker)
        mocker.patch.object(type(mock_bot), "get_user", lambda self, uid: user)

        await alarma_mod._deliver_intruder_alert(mock_bot, 1, 42, "Ragnarok", ["123", "bob"])

        dm.send.assert_called_once()
        content = dm.send.call_args.kwargs["content"]
        assert "Ragnarok" in content
        assert "123" in content and "bob" in content
        # La hora va como timestamp de Discord (<t:epoch:t>) → hora local de cada usuario.
        assert "<t:" in content and ":t>" in content

        row = await mock_bot.db.fetchone(
            "SELECT message_id, intruders_json FROM alarm_alert_messages "
            "WHERE guild_id = 1 AND user_id = 42 AND map_name = 'Ragnarok'"
        )
        assert row["message_id"] == 111
        import json as _json

        assert [e["name"] for e in _json.loads(row["intruders_json"])] == ["123", "bob"]

    @pytest.mark.asyncio
    async def test_second_alert_within_window_edits_same_message(self, mock_bot, mocker):
        """Una segunda detección reciente NO genera mensaje nuevo: edita el existente
        añadiendo el intruso a la lista acumulada."""
        await mock_bot.init_mock_db()
        user, dm, msg = self._make_user(mocker)
        mocker.patch.object(type(mock_bot), "get_user", lambda self, uid: user)

        await alarma_mod._deliver_intruder_alert(mock_bot, 1, 42, "Ragnarok", ["123"])
        await alarma_mod._deliver_intruder_alert(mock_bot, 1, 42, "Ragnarok", ["mallory"])

        # Solo UN send; la segunda vez editó.
        dm.send.assert_called_once()
        msg.edit.assert_called_once()
        edited = msg.edit.call_args.kwargs["content"]
        assert "123" in edited and "mallory" in edited

        row = await mock_bot.db.fetchone(
            "SELECT intruders_json FROM alarm_alert_messages WHERE guild_id = 1 AND user_id = 42"
        )
        import json as _json

        assert [e["name"] for e in _json.loads(row["intruders_json"])] == ["123", "mallory"]

    @pytest.mark.asyncio
    async def test_stale_alert_is_replaced_with_fresh_message(self, mock_bot, mocker):
        """Si la alerta previa es más vieja que la ventana, se borra y se envía una nueva
        (lista fresca) para que el usuario reciba notificación."""
        await mock_bot.init_mock_db()
        user, dm, msg = self._make_user(mocker)
        mocker.patch.object(type(mock_bot), "get_user", lambda self, uid: user)

        # Fila preexistente con timestamp viejo (fuera de ventana).
        await mock_bot.db.execute(
            "INSERT INTO alarm_alert_messages (guild_id, user_id, map_name, message_id, intruders_json, updated_at) "
            "VALUES (1, 42, 'Ragnarok', 999, '[{\"name\": \"viejo\", \"time\": \"01:00\"}]', '2020-01-01 00:00:00')"
        )
        await mock_bot.db.commit()

        await alarma_mod._deliver_intruder_alert(mock_bot, 1, 42, "Ragnarok", ["nuevo"])

        # Borró el mensaje viejo y envió uno nuevo con lista fresca.
        msg.delete.assert_called_once()
        dm.send.assert_called_once()
        content = dm.send.call_args.kwargs["content"]
        assert "nuevo" in content
        assert "viejo" not in content


class TestSnapshotInvalidation:
    """Tests del listener on_trusted_members_changed: al disparar el evento,
    map_last_players del guild se vacía → próximo tick re-evalúa a todos."""

    @pytest.mark.asyncio
    async def test_listener_clears_only_target_guild(self, mock_bot):
        """Solo se limpia el guild objetivo; los otros guilds intactos."""
        await mock_bot.init_mock_db()
        await mock_bot.db.executemany(
            "INSERT INTO map_last_players (guild_id, map_name, players_json) VALUES (?, ?, ?)",
            [
                (1, "Ragnarok", '["alice", "bob"]'),
                (1, "Aberration", '["charlie"]'),
                (2, "TheIsland", '["dave"]'),  # Otro guild — no debe tocarse
            ],
        )
        await mock_bot.db.commit()

        cog = alarma_mod.Alarma(mock_bot)
        await cog.on_trusted_members_changed(guild_id=1)

        # Guild 1 vaciado, guild 2 intacto.
        rows_g1 = await mock_bot.db.fetchall(
            "SELECT map_name FROM map_last_players WHERE guild_id = 1"
        )
        rows_g2 = await mock_bot.db.fetchall(
            "SELECT map_name FROM map_last_players WHERE guild_id = 2"
        )
        assert rows_g1 == []
        assert len(rows_g2) == 1
