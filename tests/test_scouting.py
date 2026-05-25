"""Tests del cog Scouting: persistencia real de scouts, aislamiento por guild,
validación del modal y refresh de dashboards.
"""

import pytest

from cogs.scouting import AddScoutModal, Scouting, update_scout_dashboards


@pytest.fixture
async def scouting_cog(mock_bot):
    return Scouting(mock_bot)


@pytest.mark.asyncio
async def test_add_scout_modal_inserts_row(scouting_cog, mock_interaction, mock_bot, mocker):
    """El modal añade un scout en la DB con todos los campos correctos."""
    await mock_bot.init_mock_db()
    # Evitar la llamada a update_scout_dashboards que requeriría Discord channels reales.
    mocker.patch("cogs.scouting.update_scout_dashboards", new=mocker.AsyncMock())

    modal = AddScoutModal(mock_bot)
    modal.tribu._value = "Raiders"
    modal.mapa._value = "Fjordur"
    modal.coords._value = "45.2, 78.3"
    modal.amenaza._value = "4"
    modal.notas._value = "Base con torretas"

    await modal.on_submit(mock_interaction)

    mock_interaction.response.send_message.assert_called_once()

    row = await mock_bot.db.fetchone(
        "SELECT tribu_enemiga, mapa, coordenadas, nivel_amenaza, notas FROM scouts WHERE guild_id = ?",
        (mock_interaction.guild_id,),
    )
    assert row is not None
    assert row["tribu_enemiga"] == "Raiders"
    assert row["mapa"] == "Fjordur"
    assert row["coordenadas"] == "45.2, 78.3"
    assert row["nivel_amenaza"] == 4
    assert row["notas"] == "Base con torretas"


@pytest.mark.asyncio
async def test_add_scout_modal_rejects_invalid_threat(scouting_cog, mock_interaction, mock_bot):
    """Amenaza fuera de 1-5 debe rechazarse sin insertar."""
    await mock_bot.init_mock_db()

    modal = AddScoutModal(mock_bot)
    modal.tribu._value = "Raiders"
    modal.mapa._value = "Fjordur"
    modal.coords._value = "0,0"
    modal.amenaza._value = "9"  # inválido
    modal.notas._value = ""

    await modal.on_submit(mock_interaction)

    mock_interaction.response.send_message.assert_called_once()
    args, _ = mock_interaction.response.send_message.call_args
    assert "❌" in args[0]

    # Nada insertado.
    rows = await mock_bot.db.fetchall("SELECT id FROM scouts")
    assert rows == []


@pytest.mark.asyncio
async def test_add_scout_modal_rejects_non_numeric_threat(scouting_cog, mock_interaction, mock_bot):
    """Amenaza no numérica también se rechaza."""
    await mock_bot.init_mock_db()

    modal = AddScoutModal(mock_bot)
    modal.tribu._value = "X"
    modal.mapa._value = "Y"
    modal.coords._value = "0,0"
    modal.amenaza._value = "?"
    modal.notas._value = ""

    await modal.on_submit(mock_interaction)
    rows = await mock_bot.db.fetchall("SELECT id FROM scouts")
    assert rows == []


@pytest.mark.asyncio
async def test_update_dashboards_handles_empty_state(scouting_cog, mock_bot):
    """Sin scouts ni mensajes registrados, update_scout_dashboards no debe fallar."""
    await mock_bot.init_mock_db()
    # No hay scout_messages → no debería intentar editar nada ni petar.
    await update_scout_dashboards(mock_bot, 12345)


@pytest.mark.asyncio
async def test_scouts_are_guild_isolated(mock_bot):
    """Un scout de un guild no debe filtrarse al consultar otro."""
    await mock_bot.init_mock_db()
    await mock_bot.db.executemany(
        "INSERT INTO scouts (guild_id, tribu_enemiga, mapa, coordenadas, nivel_amenaza, url_imagen, notas) "
        "VALUES (?, ?, ?, ?, ?, 'N/A', '')",
        [
            (1, "EnemyA", "Ragnarok", "10,20", 3),
            (1, "EnemyB", "TheIsland", "30,40", 5),
            (2, "OtroGuild", "Aberration", "50,60", 1),
        ],
    )
    await mock_bot.db.commit()

    rows_g1 = await mock_bot.db.fetchall("SELECT tribu_enemiga FROM scouts WHERE guild_id = ?", (1,))
    rows_g2 = await mock_bot.db.fetchall("SELECT tribu_enemiga FROM scouts WHERE guild_id = ?", (2,))
    assert sorted(r["tribu_enemiga"] for r in rows_g1) == ["EnemyA", "EnemyB"]
    assert [r["tribu_enemiga"] for r in rows_g2] == ["OtroGuild"]
