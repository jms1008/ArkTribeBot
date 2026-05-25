"""Tests de cogs.k4ultra.embeds (generación de páginas para el dashboard).

El diseño actual usa ``embed.description`` con secciones `## EMOJI TÍTULO`
(en lugar de ``add_field``), siguiendo el patrón visual unificado del bot.
"""

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
    """Sin jugadores ni sesiones → la página existe con secciones EN LÍNEA y TOP."""
    await mock_bot.init_mock_db()
    pages, top, aliases = await generate_k4ultra_embed(mock_bot, guild_id=1, mode="radar")

    assert len(pages) >= 1
    assert "TRACKER K4ULTRA" in pages[0].title
    assert top == []
    assert aliases == {}
    desc = pages[0].description
    # Ambas secciones deben estar presentes aunque sin datos.
    assert "EN LÍNEA AHORA" in desc
    assert "TOP JUGADORES" in desc


@pytest.mark.asyncio
async def test_radar_shows_active_sessions(mock_bot):
    """Una sesión activa aparece con 🟢 en la sección EN LÍNEA del description."""
    await mock_bot.init_mock_db()
    await mock_bot.db.execute(
        "INSERT INTO k4ultra_sessions (guild_id, player_name, map_name, start_time, is_active) "
        "VALUES (?, ?, ?, ?, 1)",
        (1, "Alice", "Ragnarok", "2026-05-24 12:30:00"),
    )
    await mock_bot.db.execute(
        "INSERT INTO k4ultra_playtime (guild_id, player_name, map_name, total_minutes) VALUES (?, ?, ?, ?)",
        (1, "Alice", "Ragnarok", 240),
    )
    await mock_bot.db.commit()

    pages, top, _ = await generate_k4ultra_embed(mock_bot, guild_id=1, mode="radar")

    assert "Alice" in top
    desc = pages[0].description
    assert "EN LÍNEA AHORA" in desc
    assert "Alice" in desc
    assert "🟢" in desc
    assert "Ragnarok" in desc
    # Hora de la sesión: 12:30
    assert "12:30" in desc


@pytest.mark.asyncio
async def test_radar_uses_alias(mock_bot):
    """El alias se inyecta entre corchetes junto al nombre en el ranking."""
    await mock_bot.init_mock_db()
    await mock_bot.db.execute(
        "INSERT INTO k4ultra_playtime (guild_id, player_name, map_name, total_minutes) VALUES (?, ?, ?, ?)",
        (1, "Steam12345", "Ragnarok", 60),
    )
    await mock_bot.db.execute(
        "INSERT INTO k4ultra_aliases (guild_id, player_name, alias) VALUES (?, ?, ?)",
        (1, "Steam12345", "Alice"),
    )
    await mock_bot.db.commit()

    pages, top, aliases = await generate_k4ultra_embed(mock_bot, guild_id=1, mode="radar")

    assert aliases == {"Steam12345": "Alice"}
    desc = pages[0].description
    assert "TOP JUGADORES" in desc
    assert "[Alice]" in desc


@pytest.mark.asyncio
async def test_tribes_mode_empty(mock_bot):
    """Modo tribus sin datos: una sola página con mensaje de vacío."""
    await mock_bot.init_mock_db()
    pages, _, _ = await generate_k4ultra_embed(mock_bot, guild_id=1, mode="tribus")

    assert len(pages) == 1
    desc = pages[0].description
    assert "No hay tribus" in desc


@pytest.mark.asyncio
async def test_tribes_mode_shows_own_and_fixed(mock_bot):
    """Distingue NUESTRA TRIBU (is_own=1) de TRIBUS FIJADAS (is_own=0)."""
    await mock_bot.init_mock_db()
    await mock_bot.db.execute(
        "INSERT INTO k4ultra_fixed_tribes (guild_id, name, members_json, is_own) VALUES (?, ?, ?, ?)",
        (1, "MiTribu", json.dumps(["Alice", "Bob"]), 1),
    )
    await mock_bot.db.execute(
        "INSERT INTO k4ultra_fixed_tribes (guild_id, name, members_json, is_own) VALUES (?, ?, ?, ?)",
        (1, "Enemigos", json.dumps(["Carol"]), 0),
    )
    await mock_bot.db.commit()

    pages, _, _ = await generate_k4ultra_embed(mock_bot, guild_id=1, mode="tribus")

    desc = pages[0].description
    assert "NUESTRA TRIBU" in desc
    assert "TRIBUS FIJADAS" in desc
    assert "MiTribu" in desc
    assert "Alice" in desc
    assert "Enemigos" in desc
    assert "Carol" in desc


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

    desc = pages[0].description
    assert "GRUPOS PREDICHOS" in desc
    # Debe agrupar A, B y C en un solo cluster.
    for name in ("A", "B", "C"):
        assert name in desc
