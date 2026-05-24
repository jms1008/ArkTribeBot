"""Tests de cogs.k4ultra.embeds (generación de páginas para el dashboard)."""
import json

import pytest

from cogs.k4ultra.embeds import MAP_ACRONYMS, generate_k4ultra_embed


class TestMapAcronyms:
    def test_contains_main_maps(self):
        for m in ("Ragnarok", "The Island", "Aberration", "Extinction"):
            assert m in MAP_ACRONYMS

    def test_acronyms_are_short(self):
        # Para encajar en línea con porcentajes, todos deben caber en 4-5 chars.
        for v in MAP_ACRONYMS.values():
            assert len(v) <= 5


@pytest.mark.asyncio
async def test_radar_empty_state(mock_bot):
    """Sin jugadores ni sesiones → la página existe con mensaje de vacío."""
    await mock_bot.init_mock_db()
    pages, top, aliases = await generate_k4ultra_embed(mock_bot, guild_id=1, mode="radar")

    assert len(pages) >= 1
    assert "TRACKER K4ULTRA" in pages[0].title
    assert top == []
    assert aliases == {}
    # Field "En Línea Ahora" debe estar presente.
    field_names = [f.name for f in pages[0].fields]
    assert any("En Línea" in n for n in field_names)


@pytest.mark.asyncio
async def test_radar_shows_active_sessions(mock_bot):
    """Si hay una sesión activa, aparece como '🟢' en la lista de en-línea."""
    await mock_bot.init_mock_db()
    await mock_bot.db.execute(
        "INSERT INTO k4ultra_sessions (guild_id, player_name, map_name, start_time, is_active) "
        "VALUES (?, ?, ?, ?, 1)",
        (1, "Alice", "Ragnarok", "2026-05-24 12:30:00"),
    )
    await mock_bot.db.execute(
        "INSERT INTO k4ultra_playtime (guild_id, player_name, map_name, total_minutes) "
        "VALUES (?, ?, ?, ?)",
        (1, "Alice", "Ragnarok", 240),
    )
    await mock_bot.db.commit()

    pages, top, _ = await generate_k4ultra_embed(mock_bot, guild_id=1, mode="radar")

    assert "Alice" in top
    online_field = next(f for f in pages[0].fields if "En Línea" in f.name)
    assert "Alice" in online_field.value
    assert "🟢" in online_field.value
    assert "Ragnarok" in online_field.value
    # Hora de la sesión: 12:30
    assert "12:30" in online_field.value


@pytest.mark.asyncio
async def test_radar_uses_alias(mock_bot):
    """El alias se inyecta entre corchetes junto al nombre."""
    await mock_bot.init_mock_db()
    await mock_bot.db.execute(
        "INSERT INTO k4ultra_playtime (guild_id, player_name, map_name, total_minutes) "
        "VALUES (?, ?, ?, ?)",
        (1, "Steam12345", "Ragnarok", 60),
    )
    await mock_bot.db.execute(
        "INSERT INTO k4ultra_aliases (guild_id, player_name, alias) VALUES (?, ?, ?)",
        (1, "Steam12345", "Alice"),
    )
    await mock_bot.db.commit()

    pages, top, aliases = await generate_k4ultra_embed(mock_bot, guild_id=1, mode="radar")

    assert aliases == {"Steam12345": "Alice"}
    # Buscar el campo de Top Jugadores
    top_field = next(f for f in pages[0].fields if "Top Jugadores" in f.name)
    assert "[Alice]" in top_field.value


@pytest.mark.asyncio
async def test_tribes_mode_empty(mock_bot):
    """Modo tribus sin datos: una sola página con mensaje 'No hay tribus'."""
    await mock_bot.init_mock_db()
    pages, _, _ = await generate_k4ultra_embed(mock_bot, guild_id=1, mode="tribus")

    assert len(pages) == 1
    field = pages[0].fields[0]
    assert "No hay tribus" in field.value


@pytest.mark.asyncio
async def test_tribes_mode_shows_own_and_fixed(mock_bot):
    """Distingue 'Nuestra Tribu' (is_own=1) de tribus fijadas (is_own=0)."""
    await mock_bot.init_mock_db()
    await mock_bot.db.execute(
        "INSERT INTO k4ultra_fixed_tribes (guild_id, name, members_json, is_own) "
        "VALUES (?, ?, ?, ?)",
        (1, "MiTribu", json.dumps(["Alice", "Bob"]), 1),
    )
    await mock_bot.db.execute(
        "INSERT INTO k4ultra_fixed_tribes (guild_id, name, members_json, is_own) "
        "VALUES (?, ?, ?, ?)",
        (1, "Enemigos", json.dumps(["Carol"]), 0),
    )
    await mock_bot.db.commit()

    pages, _, _ = await generate_k4ultra_embed(mock_bot, guild_id=1, mode="tribus")

    field_names = [f.name for f in pages[0].fields]
    assert any("Nuestra Tribu" in n for n in field_names)
    assert any("Fijadas" in n for n in field_names)

    own_field = next(f for f in pages[0].fields if "Nuestra Tribu" in f.name)
    assert "MiTribu" in own_field.value
    assert "Alice" in own_field.value

    fixed_field = next(f for f in pages[0].fields if "Fijadas" in f.name)
    assert "Enemigos" in fixed_field.value
    assert "Carol" in fixed_field.value


@pytest.mark.asyncio
async def test_tribes_mode_clusters_relationships(mock_bot):
    """Jugadores con relaciones manuales se agrupan como tribu dinámica."""
    await mock_bot.init_mock_db()
    # Sin tribus fijas; tres jugadores conectados por relaciones manuales.
    await mock_bot.db.execute(
        "INSERT INTO k4ultra_relationships (guild_id, player1, player2, probability_score, is_manual, shared_minutes) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (1, "A", "B", 100, 1, 120),
    )
    await mock_bot.db.execute(
        "INSERT INTO k4ultra_relationships (guild_id, player1, player2, probability_score, is_manual, shared_minutes) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (1, "B", "C", 100, 1, 120),
    )
    await mock_bot.db.commit()

    pages, _, _ = await generate_k4ultra_embed(mock_bot, guild_id=1, mode="tribus")

    field_names = [f.name for f in pages[0].fields]
    assert any("Grupos" in n for n in field_names)

    grupos_field = next(f for f in pages[0].fields if "Grupos" in f.name)
    # Debe agrupar A, B y C en un solo cluster.
    for name in ("A", "B", "C"):
        assert name in grupos_field.value
