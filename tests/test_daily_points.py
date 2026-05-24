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
async def test_puntos_diarios_subscribe(daily_points_cog, mock_interaction):
    """Test subscribing to daily points: usa bot.db real (in-memory)."""
    await daily_points_cog.bot.init_mock_db()
    estado_choice = app_commands.Choice(name="Activar", value="on")
    zona_choice = app_commands.Choice(name="España", value="es")

    await daily_points_cog.puntos_diarios.callback(
        daily_points_cog, mock_interaction, estado=estado_choice, zona=zona_choice
    )

    mock_interaction.response.send_message.assert_called_once()

    # Verificar que el usuario fue insertado en la DB real.
    row = await daily_points_cog.bot.db.fetchone(
        "SELECT alert_hour, timezone FROM daily_points_users WHERE user_id = ? AND guild_id = ?",
        (mock_interaction.user.id, mock_interaction.guild_id),
    )
    assert row is not None
    assert row["alert_hour"] == 8
    assert row["timezone"] == "es"
