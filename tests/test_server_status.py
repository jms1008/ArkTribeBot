import pytest
from unittest.mock import patch
from cogs.server_status import ServerStatus


@pytest.fixture
async def status_cog(mock_bot):
    cog = ServerStatus(mock_bot)
    cog.status_loop.cancel()
    cog.global_status_loop.cancel()
    return cog


@pytest.mark.asyncio
async def test_get_server_embed_offline(status_cog):
    """Test the failure branch for a server that times out."""
    with patch(
        "cogs.server_status.a2s.info", side_effect=Exception("Connection Refused")
    ):
        embed = await status_cog.get_server_embed("Gen2")

        assert embed is not None
        assert "Error" in embed.title
        assert "No se pudo conectar" in embed.description


@pytest.mark.asyncio
async def test_status_command(status_cog, mock_interaction, mocker):
    """Test the slash command directly."""
    # Mock get_server_embed to return a valid embed
    mock_embed = mocker.MagicMock()
    status_cog.get_server_embed = mocker.AsyncMock(return_value=mock_embed)

    choice = mocker.MagicMock()
    choice.value = "Gen2"

    await status_cog.status.callback(status_cog, mock_interaction, choice)

    mock_interaction.response.defer.assert_called_once()
    mock_interaction.followup.send.assert_called_once_with(embed=mock_embed)
