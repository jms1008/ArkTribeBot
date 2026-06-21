from unittest.mock import patch

import pytest

from cogs.server_status import ServerStatus


@pytest.fixture
async def status_cog(mock_bot):
    cog = ServerStatus(mock_bot)
    cog.status_loop.cancel()
    cog.global_status_loop.cancel()
    return cog


@pytest.mark.asyncio
async def test_get_server_embed_offline(status_cog):
    """El embed de error se genera correctamente cuando el servidor no responde."""
    servers = {"Gen2": ("1.2.3.4", 7777)}
    with patch("cogs.server_status.a2s.info", side_effect=Exception("Connection Refused")):
        embed = await status_cog.get_server_embed("Gen2", servers, guild_id=1)

        assert embed is not None
        assert "Error" in embed.title
        assert "No se pudo conectar" in embed.description


@pytest.mark.asyncio
async def test_status_command(status_cog, mock_interaction, mock_bot, mocker):
    """El comando /status delega correctamente en get_server_embed con los servidores del guild."""
    # Usamos bot.db real para que get_guild_servers funcione sin mocks frágiles.
    await mock_bot.init_mock_db()
    await mock_bot.db.execute(
        "INSERT INTO guild_config (guild_id, battlemetrics_urls) VALUES (?, ?)",
        (mock_interaction.guild_id, "Gen2|1.2.3.4:7777"),
    )
    await mock_bot.db.commit()

    mock_embed = mocker.MagicMock()
    status_cog.get_server_embed = mocker.AsyncMock(return_value=mock_embed)

    await status_cog.status.callback(status_cog, mock_interaction, "Gen2")

    mock_interaction.response.defer.assert_called_once_with(ephemeral=True)
    mock_interaction.followup.send.assert_called_once_with(embed=mock_embed, ephemeral=True)
    # get_server_embed se llamó con el nombre de mapa correcto y el dict parseado, junto con el guild_id.
    status_cog.get_server_embed.assert_called_once_with("Gen2", {"Gen2": ("1.2.3.4", 7777)}, mock_interaction.guild_id)
