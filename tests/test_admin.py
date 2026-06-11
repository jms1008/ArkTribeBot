import pytest
from discord import app_commands

from cogs.admin import Admin
from utils import i18n


@pytest.fixture
async def admin_cog(mock_bot):
    return Admin(mock_bot)


@pytest.mark.asyncio
async def test_wipe_db_command(admin_cog, mock_interaction, mock_bot, mocker):
    """Verifica que /admin wipe borra realmente TODAS las tablas de datos del guild,
    incluidas las que históricamente sobrevivían (K4Ultra, perfiles, KDA, alarmas)."""
    await mock_bot.init_mock_db()
    guild_id = mock_interaction.guild_id

    # Insertamos datos en varias tablas para luego verificar el borrado.
    await mock_bot.db.execute("INSERT INTO blacklist (guild_id, player) VALUES (?, ?)", (guild_id, "Enemy"))
    await mock_bot.db.execute(
        "INSERT INTO blacklist (guild_id, player) VALUES (?, ?)", (guild_id + 1, "Otro")
    )
    await mock_bot.db.execute("INSERT INTO scouts (guild_id, tribu_enemiga) VALUES (?, ?)", (guild_id, "X"))
    # Tablas que el wipe antiguo NO borraba (regresión del contrato "borra TODO").
    await mock_bot.db.execute(
        "INSERT INTO k4ultra_playtime (guild_id, player_name, map_name, total_minutes, last_seen) "
        "VALUES (?, 'bob', 'Fjordur', 100, '2026-01-01 00:00:00')",
        (guild_id,),
    )
    await mock_bot.db.execute(
        "INSERT INTO tribe_characters (guild_id, character_name, player_name) VALUES (?, 'Char', 'Bob')",
        (guild_id,),
    )
    await mock_bot.db.execute(
        "INSERT INTO tribe_kda (guild_id, player_name, deaths) VALUES (?, 'Bob', 5)", (guild_id,)
    )
    await mock_bot.db.execute(
        "INSERT INTO map_alarms (guild_id, user_id, map_name, channel_id) VALUES (?, 1, 'Fjordur', 2)",
        (guild_id,),
    )
    await mock_bot.db.execute(
        "INSERT INTO kda_messages (guild_id, channel_id, message_id) VALUES (?, 1, 2)", (guild_id,)
    )
    await mock_bot.db.commit()

    mock_interaction.client.is_authorized_admin = mocker.AsyncMock(return_value=True)

    await admin_cog.wipe_db.callback(admin_cog, mock_interaction)

    # TODO el guild interactuado debe quedar vacío.
    for table in (
        "blacklist",
        "scouts",
        "k4ultra_playtime",
        "tribe_characters",
        "tribe_kda",
        "map_alarms",
        "kda_messages",
    ):
        rows = await mock_bot.db.fetchall(f"SELECT 1 FROM {table} WHERE guild_id = ?", (guild_id,))  # noqa: S608
        assert rows == [], f"La tabla {table} no se vació en el wipe"

    # Los datos de OTRO guild deben seguir intactos.
    other_bl = await mock_bot.db.fetchall("SELECT player FROM blacklist WHERE guild_id = ?", (guild_id + 1,))
    assert len(other_bl) == 1


@pytest.mark.asyncio
async def test_clear_updates_forgets_all_dashboards(admin_cog, mock_interaction, mock_bot, mocker):
    """Regresión: /admin clear olvidaba kda_messages y k4ultra_messages, dejando
    al ranking y al radar editando mensajes viejos."""
    await mock_bot.init_mock_db()
    guild_id = mock_interaction.guild_id

    for table in ("todo_messages", "kda_messages", "k4ultra_messages"):
        await mock_bot.db.execute(
            f"INSERT INTO {table} (guild_id, channel_id, message_id) VALUES (?, 1, 2)",  # noqa: S608
            (guild_id,),
        )
    await mock_bot.db.commit()

    mock_interaction.client.is_authorized_admin = mocker.AsyncMock(return_value=True)
    await admin_cog.clear_updates.callback(admin_cog, mock_interaction)

    for table in ("todo_messages", "kda_messages", "k4ultra_messages"):
        rows = await mock_bot.db.fetchall(f"SELECT 1 FROM {table} WHERE guild_id = ?", (guild_id,))  # noqa: S608
        assert rows == [], f"{table} no se limpió"


@pytest.mark.asyncio
async def test_idioma_persists_and_invalidates_cache(admin_cog, mock_interaction, mock_bot, mocker):
    """/idioma guarda el modo, invalida la caché y resolve_lang refleja el cambio."""
    await mock_bot.init_mock_db()
    i18n.invalidate_lang_cache()
    guild_id = mock_interaction.guild_id

    mock_interaction.client.is_authorized_admin = mocker.AsyncMock(return_value=True)

    # Calentar la caché en español.
    assert await i18n.resolve_lang(mock_bot, guild_id, "periodic") == "es"

    choice = app_commands.Choice(name="English (todo)", value=i18n.MODE_EN_TOTAL)
    await admin_cog.idioma.callback(admin_cog, mock_interaction, choice)

    # Persistido en guild_config.
    row = await mock_bot.db.fetchone("SELECT language FROM guild_config WHERE guild_id = ?", (guild_id,))
    assert row["language"] == "en_total"

    # La caché se invalidó → resolve_lang devuelve inglés en ambos scopes.
    assert await i18n.resolve_lang(mock_bot, guild_id, "periodic") == "en"
    assert await i18n.resolve_lang(mock_bot, guild_id, "command") == "en"

    mock_interaction.response.send_message.assert_called_once()


@pytest.mark.asyncio
async def test_idioma_denied_for_non_admin(admin_cog, mock_interaction, mock_bot, mocker):
    """Sin permisos de admin, /idioma no modifica nada."""
    await mock_bot.init_mock_db()
    guild_id = mock_interaction.guild_id

    mock_interaction.client.is_authorized_admin = mocker.AsyncMock(return_value=False)

    choice = app_commands.Choice(name="English", value=i18n.MODE_EN_TOTAL)
    await admin_cog.idioma.callback(admin_cog, mock_interaction, choice)

    row = await mock_bot.db.fetchone("SELECT language FROM guild_config WHERE guild_id = ?", (guild_id,))
    # No se creó/actualizó ninguna fila de idioma.
    assert row is None
