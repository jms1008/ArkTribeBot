import pytest

from cogs.warfare import (
    AddBlacklistModal,
    Warfare,
    build_blacklist_embed,
    update_blacklist_dashboards,
    update_kda_dashboards,
)


@pytest.fixture
async def warfare_cog(mock_bot):
    return Warfare(mock_bot)


@pytest.mark.asyncio
async def test_blacklist_add_modal(warfare_cog, mock_interaction, mock_bot):
    """El modal inserta una fila en blacklist con los valores proporcionados."""
    await mock_bot.init_mock_db()

    modal = AddBlacklistModal(warfare_cog.bot)
    modal.player._value = "Enemy"
    modal.tribe._value = "BadTribe"
    modal.map_name._value = "Ragnarok"
    modal.notes._value = "Sospechoso"

    await modal.on_submit(mock_interaction)

    mock_interaction.response.send_message.assert_called_once()

    row = await mock_bot.db.fetchone(
        "SELECT player, tribe, map, notes FROM blacklist WHERE guild_id = ?",
        (mock_interaction.guild_id,),
    )
    assert row is not None
    assert row["player"] == "Enemy"
    assert row["tribe"] == "BadTribe"
    assert row["map"] == "Ragnarok"
    assert row["notes"] == "Sospechoso"


class TestBuildBlacklistEmbed:
    """build_blacklist_embed es función pura — devuelve ``(embed, page, total_pages)``."""

    def test_empty_state(self):
        embed, page, total_pages = build_blacklist_embed(rows=[], page=0)
        assert "BLACKLIST" in embed.title.upper()
        assert "limpia" in embed.description.lower() or "no hay" in embed.description.lower()
        assert page == 0
        assert total_pages == 1

    def test_single_row(self):
        rows = [
            {
                "id": 1,
                "player": "Enemy",
                "tribe": "T",
                "map": "Ragnarok",
                "notes": "n",
                "created_at": "2026-01-01",
                "last_seen": None,
                "total_hours": 0,
                "is_enemy": 1,
            }
        ]
        embed, _, _ = build_blacklist_embed(rows=rows, page=0)
        rendered = (embed.description or "") + "\n".join(
            (f.name or "") + " " + (f.value or "") for f in embed.fields
        )
        assert "Enemy" in rendered

    def test_pagination_clamps_high_page(self):
        rows = [
            {
                "id": 1,
                "player": "P",
                "tribe": "T",
                "map": "M",
                "notes": "",
                "created_at": None,
                "last_seen": None,
                "total_hours": 0,
                "is_enemy": 1,
            }
        ]
        # Página 99 con 1 fila debe volver a página 0.
        embed, page, total_pages = build_blacklist_embed(rows=rows, page=99)
        assert embed is not None
        assert page == 0
        assert total_pages == 1


@pytest.mark.asyncio
async def test_update_blacklist_dashboards_handles_empty(mock_bot):
    """Sin blacklist_messages registrados, update_blacklist_dashboards no debe fallar."""
    await mock_bot.init_mock_db()
    await update_blacklist_dashboards(mock_bot, guild_id=12345)


@pytest.mark.asyncio
async def test_update_kda_dashboards_handles_empty(mock_bot):
    """Sin kda_messages registrados, update_kda_dashboards no debe fallar."""
    await mock_bot.init_mock_db()
    await update_kda_dashboards(mock_bot, guild_id=12345)


@pytest.mark.asyncio
async def test_blacklist_is_guild_isolated(mock_bot):
    """Entradas de un guild no aparecen en queries de otro guild."""
    await mock_bot.init_mock_db()
    await mock_bot.db.executemany(
        "INSERT INTO blacklist (guild_id, player, tribe, map, notes, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        [
            (1, "EnemyA", "T1", "M", "n", "2026-01-01"),
            (1, "EnemyB", "T2", "M", "n", "2026-01-01"),
            (2, "OtroGuild", "T3", "M", "n", "2026-01-01"),
        ],
    )
    await mock_bot.db.commit()

    rows_g1 = await mock_bot.db.fetchall(
        "SELECT player FROM blacklist WHERE guild_id = ?", (1,)
    )
    rows_g2 = await mock_bot.db.fetchall(
        "SELECT player FROM blacklist WHERE guild_id = ?", (2,)
    )
    assert sorted(r["player"] for r in rows_g1) == ["EnemyA", "EnemyB"]
    assert [r["player"] for r in rows_g2] == ["OtroGuild"]


@pytest.mark.asyncio
async def test_kda_upsert_pattern(mock_bot):
    """Verifica el INSERT...ON CONFLICT que usa log_processor para incrementar muertes."""
    await mock_bot.init_mock_db()
    db = mock_bot.db

    # Simular dos muertes consecutivas del mismo jugador en el mismo guild.
    sql = (
        "INSERT INTO tribe_kda (guild_id, player_name, deaths) VALUES (?, ?, 1) "
        "ON CONFLICT(guild_id, player_name) DO UPDATE SET deaths = deaths + 1"
    )
    await db.execute(sql, (1, "Player"))
    await db.execute(sql, (1, "Player"))
    await db.execute(sql, (1, "Player"))
    await db.commit()

    row = await db.fetchone(
        "SELECT deaths FROM tribe_kda WHERE guild_id = ? AND player_name = ?",
        (1, "Player"),
    )
    assert row["deaths"] == 3
