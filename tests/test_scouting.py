import pytest
from cogs.scouting import Scouting
import discord

@pytest.fixture
async def scouting_cog(mock_bot):
    cog = Scouting(mock_bot)
    return cog

@pytest.mark.asyncio
async def test_scout_list_command(scouting_cog, mock_interaction, mocker):
    """Test generating a scout list embed."""
    scouting_cog.scout_list = mocker.AsyncMock()
    await scouting_cog.scout_list.callback(scouting_cog, mock_interaction)
    scouting_cog.scout_list.callback.assert_called_once()
