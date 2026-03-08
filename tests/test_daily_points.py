import pytest
from cogs.daily_points import DailyPoints

@pytest.fixture
async def daily_points_cog(mock_bot):
    cog = DailyPoints(mock_bot)
    cog.points_loop.cancel()
    return cog

from discord import app_commands

@pytest.mark.asyncio
async def test_puntos_diarios_subscribe(daily_points_cog, mock_interaction, mocker):
    """Test subscribing to daily points."""
    
    # Configurar DB asíncrona real y Choice
    await daily_points_cog.bot.init_mock_db()
    estado_choice = app_commands.Choice(name="Activar", value="on")
    zona_choice = app_commands.Choice(name="España", value="es")
    
    await daily_points_cog.puntos_diarios.callback(daily_points_cog, mock_interaction, estado=estado_choice, zona=zona_choice)
    mock_interaction.response.send_message.assert_called_once()
