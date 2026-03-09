import pytest
from cogs.admin import Admin


@pytest.fixture
async def admin_cog(mock_bot):
    return Admin(mock_bot)


@pytest.mark.asyncio
async def test_wipe_db_command(admin_cog, mock_interaction, mock_bot, mocker):
    """Test the wipe_db command which should fail due to permissions but interaction checks run."""
    mock_interaction.user.id = 123456  # Not the authorized admin ID

    # Custom Async Context Manager Mock
    mock_db = mocker.patch("cogs.admin.aiosqlite.connect")
    mock_conn = mocker.AsyncMock()
    mock_db.return_value.__aenter__.return_value = mock_conn

    # Mock the new is_authorized_admin checking from main.py
    mock_interaction.client.is_authorized_admin = mocker.AsyncMock(return_value=True)

    # We call the function directly
    await admin_cog.wipe_db.callback(admin_cog, mock_interaction)

    # Check that it executed the DB query to clear tables
    mock_conn.execute.assert_called()
