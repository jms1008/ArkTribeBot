import pytest

from cogs.warfare import AddBlacklistModal, Warfare


@pytest.fixture
async def warfare_cog(mock_bot):
    cog = Warfare(mock_bot)
    return cog


@pytest.mark.asyncio
async def test_blacklist_add_modal(warfare_cog, mock_interaction, mock_bot):
    """El modal inserta una fila en blacklist con los valores proporcionados."""
    await mock_bot.init_mock_db()

    modal = AddBlacklistModal(warfare_cog.bot)
    modal.player._value = "Enemy"
    modal.tribe._value = "BadTribe"
    modal.map_name._value = "Ragnarok"
    modal.notes._value = "Sospechoso"

    await modal.on_submit(mock_interaction)

    mock_interaction.response.send_message.assert_called_once()

    # Verificar la inserción real.
    row = await mock_bot.db.fetchone(
        "SELECT player, tribe, map, notes FROM blacklist WHERE guild_id = ?",
        (mock_interaction.guild_id,),
    )
    assert row is not None
    assert row["player"] == "Enemy"
    assert row["tribe"] == "BadTribe"
    assert row["map"] == "Ragnarok"
    assert row["notes"] == "Sospechoso"
