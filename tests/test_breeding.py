"""Tests del cog Breeding: upsert de stats, validación de whitelist y dashboards."""

import pytest

from cogs.breeding import Breeding, update_breeding_dashboards


@pytest.fixture
async def breeding_cog(mock_bot):
    cog = Breeding(mock_bot)
    cog.check_alarms.cancel()
    return cog


@pytest.mark.asyncio
async def test_upsert_stat_inserts_new_dino(breeding_cog, mock_bot):
    """Si no existe el dino, ``upsert_stat`` crea la fila con la stat indicada."""
    await mock_bot.init_mock_db()
    action = await breeding_cog.upsert_stat("Rex", "hp", 50, guild_id=1)

    assert "nueva línea" in action.lower() or "registrada" in action.lower()
    row = await mock_bot.db.fetchone(
        "SELECT hp, melee FROM dinos WHERE especie = ? AND guild_id = ?", ("Rex", 1)
    )
    assert row is not None
    assert row["hp"] == 50
    assert row["melee"] is None


@pytest.mark.asyncio
async def test_upsert_stat_updates_existing(breeding_cog, mock_bot):
    """Si la fila existe, se actualiza el valor de la stat."""
    await mock_bot.init_mock_db()
    await breeding_cog.upsert_stat("Rex", "hp", 50, guild_id=1)
    await breeding_cog.upsert_stat("Rex", "hp", 52, guild_id=1)  # +2 = mutación

    row = await mock_bot.db.fetchone(
        "SELECT hp FROM dinos WHERE especie = ? AND guild_id = ?", ("Rex", 1)
    )
    assert row["hp"] == 52


@pytest.mark.asyncio
async def test_upsert_stat_rejects_invalid_column(breeding_cog, mock_bot):
    """Stats fuera de ALLOWED_DINO_STATS deben lanzar ValueError (defensa anti-inyección)."""
    await mock_bot.init_mock_db()

    with pytest.raises(ValueError):
        await breeding_cog.upsert_stat("Rex", "hp; DROP TABLE dinos", 50, guild_id=1)

    # La tabla dinos sigue existiendo y vacía.
    rows = await mock_bot.db.fetchall("SELECT id FROM dinos")
    assert rows == []


@pytest.mark.asyncio
async def test_upsert_stat_isolates_by_guild(breeding_cog, mock_bot):
    """Mismo dino en guilds diferentes son filas independientes."""
    await mock_bot.init_mock_db()
    await breeding_cog.upsert_stat("Rex", "hp", 50, guild_id=1)
    await breeding_cog.upsert_stat("Rex", "hp", 80, guild_id=2)

    row_g1 = await mock_bot.db.fetchone(
        "SELECT hp FROM dinos WHERE especie = ? AND guild_id = ?", ("Rex", 1)
    )
    row_g2 = await mock_bot.db.fetchone(
        "SELECT hp FROM dinos WHERE especie = ? AND guild_id = ?", ("Rex", 2)
    )
    assert row_g1["hp"] == 50
    assert row_g2["hp"] == 80


@pytest.mark.asyncio
async def test_update_dashboards_handles_empty_state(breeding_cog, mock_bot):
    """Sin breeding_messages, update_breeding_dashboards no debe lanzar."""
    await mock_bot.init_mock_db()
    await update_breeding_dashboards(mock_bot, guild_id=12345)


@pytest.mark.asyncio
async def test_breeding_alarm_can_be_inserted(breeding_cog, mock_bot):
    """Verifica la persistencia mínima en ``breeding_alarms`` (schema correcto)."""
    await mock_bot.init_mock_db()
    await mock_bot.db.execute(
        "INSERT INTO breeding_alarms (guild_id, user_id, channel_id, alert_time) "
        "VALUES (?, ?, ?, ?)",
        (1, 42, 100, "2026-01-01 12:00:00"),
    )
    await mock_bot.db.commit()

    row = await mock_bot.db.fetchone(
        "SELECT user_id FROM breeding_alarms WHERE guild_id = ?", (1,)
    )
    assert row is not None
    assert row["user_id"] == 42
