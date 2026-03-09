import pytest
from unittest.mock import patch, AsyncMock
from cogs.server_status import ServerStatus


@pytest.fixture
async def status_cog(mock_bot):
    cog = ServerStatus(mock_bot)
    cog.status_loop.cancel()
    cog.global_status_loop.cancel()
    return cog


@pytest.mark.asyncio
async def test_get_server_embed_offline(status_cog):
    """Test que el embed de error se genera correctamente cuando el servidor no responde."""
    servers = {"Gen2": ("1.2.3.4", 7777)}
    with patch(
        "cogs.server_status.a2s.info", side_effect=Exception("Connection Refused")
    ):
        embed = await status_cog.get_server_embed("Gen2", servers)

        assert embed is not None
        assert "Error" in embed.title
        assert "No se pudo conectar" in embed.description


@pytest.mark.asyncio
async def test_status_command(status_cog, mock_interaction, mocker):
    """Test que el comando /status devuelve el embed al canal correctamente."""
    mock_embed = mocker.MagicMock()
    # Mockear get_guild_servers para devolver servidores de prueba
    mocker.patch(
        "cogs.server_status.get_guild_servers",
        new=AsyncMock(return_value={"Gen2": ("1.2.3.4", 7777)}),
    )
    status_cog.get_server_embed = mocker.AsyncMock(return_value=mock_embed)

    await status_cog.status.callback(status_cog, mock_interaction, "Gen2")

    mock_interaction.response.defer.assert_called_once()
    mock_interaction.followup.send.assert_called_once_with(embed=mock_embed)
