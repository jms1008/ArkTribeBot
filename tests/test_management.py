import pytest
from cogs.management import Management

@pytest.fixture
async def mgmt_cog(mock_bot):
    return Management(mock_bot)

@pytest.mark.asyncio
async def test_management_todo_list(mgmt_cog, mock_interaction, mocker):
    """Test the todo list interaction."""
    mgmt_cog.todo_list = mocker.AsyncMock()
    await mgmt_cog.todo_list.callback(mgmt_cog, mock_interaction)
    mgmt_cog.todo_list.callback.assert_called_once()
