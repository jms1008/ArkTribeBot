import pytest
from unittest.mock import AsyncMock, patch
from cogs.warfare import Warfare, AddBlacklistModal


@pytest.fixture
async def warfare_cog(mock_bot):
    cog = Warfare(mock_bot)
    return cog


@pytest.mark.asyncio
async def test_blacklist_add_modal(warfare_cog, mock_interaction, mocker):
    """Test adding via modal (button replaces slash command)."""
    modal = AddBlacklistModal(warfare_cog.bot)
    modal.player._value = "A"
    modal.tribe._value = "B"
    modal.map_name._value = "C"
    modal.notes._value = "D"

    with patch("cogs.warfare.aiosqlite.connect") as mock_connect:
        mock_db = AsyncMock()
        mock_db.__aenter__ = AsyncMock(return_value=mock_db)
        mock_db.__aexit__ = AsyncMock(return_value=None)
        mock_db.execute = AsyncMock()
        mock_db.commit = AsyncMock()
        mock_connect.return_value = mock_db

        await modal.on_submit(mock_interaction)

    mock_interaction.response.send_message.assert_called_once()
