import pytest
from discord import app_commands

from cogs.admin import Admin
from utils import i18n


@pytest.fixture
async def admin_cog(mock_bot):
    return Admin(mock_bot)


@pytest.mark.asyncio
async def test_wipe_db_command(admin_cog, mock_interaction, mock_bot, mocker):
    """Verifica que /wipe_db borra realmente las filas del guild en cuestión."""
    await mock_bot.init_mock_db()
    guild_id = mock_interaction.guild_id

    # Insertamos datos en varias tablas para luego verificar el borrado.
    await mock_bot.db.execute("INSERT INTO blacklist (guild_id, player) VALUES (?, ?)", (guild_id, "Enemy"))
    await mock_bot.db.execute(
        "INSERT INTO blacklist (guild_id, player) VALUES (?, ?)", (guild_id + 1, "Otro")
    )
    await mock_bot.db.execute("INSERT INTO scouts (guild_id, tribu_enemiga) VALUES (?, ?)", (guild_id, "X"))
    await mock_bot.db.commit()

    mock_interaction.client.is_authorized_admin = mocker.AsyncMock(return_value=True)

    await admin_cog.wipe_db.callback(admin_cog, mock_interaction)

    # Los datos del guild interactuado deben haberse borrado.
    remaining_bl = await mock_bot.db.fetchall("SELECT id FROM blacklist WHERE guild_id = ?", (guild_id,))
    remaining_scouts = await mock_bot.db.fetchall("SELECT id FROM scouts WHERE guild_id = ?", (guild_id,))
    assert remaining_bl == []
    assert remaining_scouts == []

    # Los datos de OTRO guild deben seguir intactos.
    other_bl = await mock_bot.db.fetchall("SELECT player FROM blacklist WHERE guild_id = ?", (guild_id + 1,))
    assert len(other_bl) == 1


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
