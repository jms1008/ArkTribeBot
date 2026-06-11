"""Tests de los subcomandos de gestión de miembros del grupo /tribu."""

import json

import pytest

from cogs.k4ultra.cog import K4Ultra


@pytest.fixture
async def k4_cog(mock_bot):
    cog = K4Ultra(mock_bot)
    cog.gather_player_data.cancel()
    cog.weekly_snapshot_task.cancel() if hasattr(cog, "weekly_snapshot_task") else None
    return cog


@pytest.mark.asyncio
async def test_miembro_borrar_removes_everything(k4_cog, mock_interaction, mock_bot, mocker):
    """/tribu miembro borrar elimina perfil, personaje, alias, idioma y saca el
    Steam name de la tribu propia (disparando la invalidación de alarmas)."""
    await mock_bot.init_mock_db()
    guild_id = mock_interaction.guild_id
    db = mock_bot.db

    # Estado previo: ficha completa registrada + tribu propia que lo incluye.
    await db.execute(
        "INSERT INTO tribe_profiles (guild_id, discord_id, ark_character, steam_id, alias) "
        "VALUES (?, 555, 'Bob', 'BobSteam', 'Bobby')",
        (guild_id,),
    )
    await db.execute(
        "INSERT INTO tribe_characters (guild_id, character_name, player_name) VALUES (?, 'Bob', 'BobDiscord')",
        (guild_id,),
    )
    await db.execute(
        "INSERT INTO k4ultra_aliases (guild_id, player_name, alias) VALUES (?, 'Bob', 'Bobby')",
        (guild_id,),
    )
    await db.execute(
        "INSERT INTO user_language (guild_id, user_id, lang) VALUES (?, 555, 'en')", (guild_id,)
    )
    await db.execute(
        "INSERT INTO k4ultra_fixed_tribes (guild_id, name, members_json, is_own) "
        "VALUES (?, 'MiTribu', ?, 1)",
        (guild_id, json.dumps(["BobSteam", "Alice"])),
    )
    await db.commit()

    mock_interaction.client.is_authorized_admin = mocker.AsyncMock(return_value=True)
    usuario = mocker.MagicMock()
    usuario.id = 555
    usuario.mention = "<@555>"

    dispatched = []
    mocker.patch.object(type(mock_bot), "dispatch", lambda self, ev, *a: dispatched.append(ev))

    await k4_cog.tribu_miembro_borrar.callback(k4_cog, mock_interaction, usuario)

    # Todo el rastro del miembro debe haber desaparecido.
    assert await db.fetchone("SELECT 1 FROM tribe_profiles WHERE guild_id = ? AND discord_id = 555", (guild_id,)) is None
    assert await db.fetchone("SELECT 1 FROM tribe_characters WHERE guild_id = ? AND character_name = 'Bob'", (guild_id,)) is None
    assert await db.fetchone("SELECT 1 FROM k4ultra_aliases WHERE guild_id = ? AND player_name = 'Bob'", (guild_id,)) is None
    assert await db.fetchone("SELECT 1 FROM user_language WHERE guild_id = ? AND user_id = 555", (guild_id,)) is None

    # La tribu propia ya no contiene su Steam name (pero conserva al resto).
    own = await db.fetchone(
        "SELECT members_json FROM k4ultra_fixed_tribes WHERE guild_id = ? AND is_own = 1", (guild_id,)
    )
    assert json.loads(own["members_json"]) == ["Alice"]

    # Se invalidó el snapshot de alarmas (volverá a contar como intruso).
    assert "trusted_members_changed" in dispatched


@pytest.mark.asyncio
async def test_miembro_borrar_without_profile_is_noop(k4_cog, mock_interaction, mock_bot, mocker):
    """Si el usuario no tiene ficha, el comando avisa y no toca nada."""
    await mock_bot.init_mock_db()
    mock_interaction.client.is_authorized_admin = mocker.AsyncMock(return_value=True)
    usuario = mocker.MagicMock()
    usuario.id = 999
    usuario.mention = "<@999>"

    await k4_cog.tribu_miembro_borrar.callback(k4_cog, mock_interaction, usuario)

    mock_interaction.response.send_message.assert_called_once()
    msg = mock_interaction.response.send_message.call_args.args[0]
    assert "<@999>" in msg
