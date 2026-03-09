import pytest
from unittest.mock import AsyncMock, patch
from discord import app_commands
from cogs.daily_points import DailyPoints


@pytest.fixture
async def daily_points_cog(mock_bot):
    cog = DailyPoints(mock_bot)
    cog.points_loop.cancel()
    return cog


@pytest.mark.asyncio
async def test_puntos_diarios_subscribe(daily_points_cog, mock_interaction, mocker):
    """Test subscribing to daily points."""

    await daily_points_cog.bot.init_mock_db()
    estado_choice = app_commands.Choice(name="Activar", value="on")
    zona_choice = app_commands.Choice(name="España", value="es")

    # Simular que el guild_config devuelve daily_points_enabled = 1 (activo)
    mock_row = mocker.MagicMock()
    mock_row.__getitem__ = mocker.MagicMock(return_value=1)

    with patch("cogs.daily_points.aiosqlite.connect") as mock_connect:
        mock_db = AsyncMock()
        mock_db.__aenter__ = AsyncMock(return_value=mock_db)
        mock_db.__aexit__ = AsyncMock(return_value=None)
        mock_cursor = AsyncMock()
        # Primera query: guild_config check → enabled
        # Segunda query: INSERT daily_points_users
        mock_cursor.fetchone = AsyncMock(return_value=(1,))
        mock_db.execute = AsyncMock(return_value=mock_cursor)
        mock_db.commit = AsyncMock()
        mock_connect.return_value = mock_db

        await daily_points_cog.puntos_diarios.callback(
            daily_points_cog, mock_interaction, estado=estado_choice, zona=zona_choice
        )

    mock_interaction.response.send_message.assert_called_once()
