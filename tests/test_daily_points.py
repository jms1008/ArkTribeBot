import pytest
from unittest.mock import AsyncMock, patch
from discord import app_commands
from cogs.daily_points import DEFAULT_VOTE_URLS, DailyPoints, parse_vote_urls


class TestParseVoteUrls:
    """parse_vote_urls es una función pura — tests sin mocks."""

    def test_empty_returns_defaults(self):
        assert parse_vote_urls("") == DEFAULT_VOTE_URLS
        assert parse_vote_urls(None) == DEFAULT_VOTE_URLS

    def test_single_url_with_label(self):
        result = parse_vote_urls("Ragnarok|https://ark.example.com/vote/1")
        assert result == ["https://ark.example.com/vote/1"]

    def test_multiple_urls_with_labels(self):
        result = parse_vote_urls(
            "Ragnarok|https://a.com/1,TheIsland|https://b.com/2,Aberration|https://c.com/3"
        )
        assert result == [
            "https://a.com/1",
            "https://b.com/2",
            "https://c.com/3",
        ]

    def test_bare_urls_without_label(self):
        result = parse_vote_urls("https://a.com,https://b.com")
        assert result == ["https://a.com", "https://b.com"]

    def test_mixes_formats(self):
        result = parse_vote_urls("Ragnarok|https://a.com,https://b.com")
        assert result == ["https://a.com", "https://b.com"]

    def test_skips_garbage_entries_and_falls_back_when_none_valid(self):
        # Ni '|' ni empieza por http → entrada descartada.
        assert parse_vote_urls("garbage,more-garbage") == DEFAULT_VOTE_URLS

    def test_trims_whitespace(self):
        result = parse_vote_urls("  Ragnarok | https://a.com  ")
        assert result == ["https://a.com"]


class TestDefaultVoteUrls:
    def test_defaults_are_https(self):
        assert all(u.startswith("https://") for u in DEFAULT_VOTE_URLS)

    def test_defaults_non_empty(self):
        assert len(DEFAULT_VOTE_URLS) >= 1


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
