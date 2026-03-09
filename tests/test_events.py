import pytest
from cogs.events import Events
import aiosqlite
import os


@pytest.fixture
async def events_cog(mock_bot):
    mock_bot.db_name = "test_events.db"
    if os.path.exists(mock_bot.db_name):
        try:
            os.remove(mock_bot.db_name)
        except OSError:
            pass
    await mock_bot.init_mock_db()
    return Events(mock_bot)


@pytest.mark.asyncio
async def test_create_event_invalid_options(events_cog, mock_interaction):
    """Prueba que el comando falla si no se dan 2 opciones válidas."""
    await events_cog.create_event.callback(
        events_cog,
        mock_interaction,
        titulo="Test Bot",
        descripcion="Test desc",
        opcion_1="Opt 1",
        opcion_2="",
        opcion_3=None,
        opcion_4=None,
    )

    mock_interaction.response.send_message.assert_called_once_with(
        "Debes proporcionar al menos 2 opciones de fecha/hora válidas para la encuesta.",
        ephemeral=True,
    )

    if os.path.exists(events_cog.bot.db_name):
        try:
            os.remove(events_cog.bot.db_name)
        except OSError:
            pass


@pytest.mark.asyncio
async def test_create_event_success(events_cog, mock_interaction):
    """Prueba que el comando crea correctamente el evento en la BD y envía el Embed."""
    from unittest.mock import MagicMock
    import discord

    mock_msg = MagicMock(spec=discord.Message)
    mock_msg.id = 12345
    mock_msg.channel = MagicMock()
    mock_msg.channel.id = 67890
    mock_interaction.followup.send.return_value = mock_msg

    await events_cog.create_event.callback(
        events_cog,
        mock_interaction,
        titulo="Boss Alpha",
        descripcion="Traer 10 rexes",
        opcion_1="Viernes 20:00",
        opcion_2="Sábado 18:00",
        opcion_3=None,
        opcion_4=None,
    )

    mock_interaction.response.defer.assert_called_once()
    mock_interaction.followup.send.assert_called_once()

    # Verificar persistencia en base de datos
    async with aiosqlite.connect(events_cog.bot.db_name) as db:
        c = await db.execute("SELECT title, description FROM events")
        events = await c.fetchall()
        assert len(events) == 1
        assert events[0][0] == "Boss Alpha"
        assert events[0][1] == "Traer 10 rexes"

        c = await db.execute("SELECT option_text FROM event_options")
        options = await c.fetchall()
        assert len(options) == 2
        assert options[0][0] == "Viernes 20:00"
        assert options[1][0] == "Sábado 18:00"

    if os.path.exists(events_cog.bot.db_name):
        try:
            os.remove(events_cog.bot.db_name)
        except OSError:
            pass
