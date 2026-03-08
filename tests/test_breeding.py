import pytest
from cogs.breeding import Breeding
from unittest.mock import AsyncMock

@pytest.fixture
async def breeding_cog(mock_bot):
    cog = Breeding(mock_bot)
    cog.check_alarms.cancel()
    return cog

@pytest.mark.asyncio
async def test_lineas_view(breeding_cog, mock_interaction, mocker):
    """Test generating breeding view."""
    mock_embed = mocker.MagicMock()
    breeding_cog.lineas = mocker.AsyncMock()
    await breeding_cog.lineas.callback(breeding_cog, mock_interaction)
    breeding_cog.lineas.callback.assert_called_once()
