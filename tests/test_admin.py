import pytest

from cogs.admin import Admin


@pytest.fixture
async def admin_cog(mock_bot):
    return Admin(mock_bot)


@pytest.mark.asyncio
async def test_wipe_db_command(admin_cog, mock_interaction, mock_bot, mocker):
    """Verifica que /wipe_db borra realmente las filas del guild en cuestión."""
    await mock_bot.init_mock_db()
    guild_id = mock_interaction.guild_id

    # Insertamos datos en varias tablas para luego verificar el borrado.
    await mock_bot.db.execute("INSERT INTO blacklist (guild_id, player) VALUES (?, ?)", (guild_id, "Enemy"))
    await mock_bot.db.execute(
        "INSERT INTO blacklist (guild_id, player) VALUES (?, ?)", (guild_id + 1, "Otro")
    )
    await mock_bot.db.execute("INSERT INTO scouts (guild_id, tribu_enemiga) VALUES (?, ?)", (guild_id, "X"))
    await mock_bot.db.commit()

    mock_interaction.client.is_authorized_admin = mocker.AsyncMock(return_value=True)

    await admin_cog.wipe_db.callback(admin_cog, mock_interaction)

    # Los datos del guild interactuado deben haberse borrado.
    remaining_bl = await mock_bot.db.fetchall("SELECT id FROM blacklist WHERE guild_id = ?", (guild_id,))
    remaining_scouts = await mock_bot.db.fetchall("SELECT id FROM scouts WHERE guild_id = ?", (guild_id,))
    assert remaining_bl == []
    assert remaining_scouts == []

    # Los datos de OTRO guild deben seguir intactos.
    other_bl = await mock_bot.db.fetchall("SELECT player FROM blacklist WHERE guild_id = ?", (guild_id + 1,))
    assert len(other_bl) == 1
