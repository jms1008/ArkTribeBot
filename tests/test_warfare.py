import pytest
from cogs.warfare import Warfare

@pytest.fixture
async def warfare_cog(mock_bot):
    cog = Warfare(mock_bot)
    return cog

@pytest.mark.asyncio
async def test_blacklist_add_modal(warfare_cog, mock_interaction, mocker):
    """Test generating blacklist addition."""
    mock_connect = mocker.patch("cogs.warfare.aiosqlite.connect")
    mock_connect.return_value = mocker.AsyncMock()
    await warfare_cog.blacklist_add.callback(warfare_cog, mock_interaction, jugador="A", tribu="B", mapa="C", notas="D")
    mock_interaction.response.send_message.assert_called_once()
