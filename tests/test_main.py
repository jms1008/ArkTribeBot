import discord
import pytest

from cogs.log_processor import LogProcessor
from main import ArkTribeBot


@pytest.mark.asyncio
async def test_bot_initialization():
    """Test para verificar que el bot se puede instanciar correctamente y configurar."""
    bot = ArkTribeBot()
    assert bot.command_prefix == "!"
    assert bot.intents.message_content is True


@pytest.mark.asyncio
async def test_log_processor_ignore_self(mocker):
    """Test para asegurar que el procesador de logs ignora mensajes del bot."""
    # Mock bot
    mock_bot = mocker.MagicMock()
    mock_bot.user.id = 123

    processor = LogProcessor(mock_bot)

    mock_message = mocker.MagicMock(spec=discord.Message)
    mock_message.author.id = 123  # Mismo ID que el bot

    # Espiar si intenta acceder a la base de datos o guild config (si lo hace es que no ignoró)
    mocker.patch("aiosqlite.connect")

    await processor.on_message(mock_message)

    # Si ignoró el mensaje, sqlite no se debe haber llamado (debería retornar rapido)
    import aiosqlite

    aiosqlite.connect.assert_not_called()


@pytest.mark.asyncio
async def test_log_processor_ignores_dm(mocker):
    """LogProcessor debe ignorar también los mensajes recibidos por DM."""
    mock_bot = mocker.MagicMock()
    mock_bot.user.id = 123

    processor = LogProcessor(mock_bot)

    mock_message = mocker.MagicMock(spec=discord.Message)
    mock_message.author.id = 999  # No es el bot
    mock_message.guild = None  # DM

    mocker.patch("aiosqlite.connect")

    await processor.on_message(mock_message)

    # En DM el procesador debe retornar antes de tocar nada.
    import aiosqlite

    aiosqlite.connect.assert_not_called()


@pytest.mark.asyncio
async def test_reject_dm_interactions_blocks_dm(mocker):
    """El interaction_check del tree rechaza interacciones sin guild (DM/grupo)."""
    bot = ArkTribeBot()

    interaction = mocker.MagicMock(spec=discord.Interaction)
    interaction.guild = None
    interaction.response.send_message = mocker.AsyncMock()
    interaction.response.is_done = mocker.MagicMock(return_value=False)

    result = await bot._reject_dm_interactions(interaction)
    assert result is False
    interaction.response.send_message.assert_called_once()
    args, kwargs = interaction.response.send_message.call_args
    # Mensaje informativo y efímero (no público).
    assert kwargs.get("ephemeral") is True


@pytest.mark.asyncio
async def test_reject_dm_interactions_allows_guild(mocker):
    """Las interacciones dentro de un guild se permiten normalmente."""
    bot = ArkTribeBot()

    interaction = mocker.MagicMock(spec=discord.Interaction)
    interaction.guild = mocker.MagicMock()  # Cualquier guild != None
    interaction.guild.id = 42

    result = await bot._reject_dm_interactions(interaction)
    assert result is True


@pytest.mark.asyncio
async def test_bot_on_message_drops_dms(mocker):
    """ArkTribeBot.on_message ignora silenciosamente los mensajes recibidos por DM."""
    bot = ArkTribeBot()
    # Evitar tocar el pipeline real de procesamiento de comandos.
    bot.process_commands = mocker.AsyncMock()

    dm_message = mocker.MagicMock(spec=discord.Message)
    dm_message.guild = None

    await bot.on_message(dm_message)

    bot.process_commands.assert_not_called()


@pytest.mark.asyncio
async def test_bot_on_message_processes_guild_messages(mocker):
    """ArkTribeBot.on_message delega los mensajes de guild al pipeline de comandos."""
    bot = ArkTribeBot()
    bot.process_commands = mocker.AsyncMock()

    guild_message = mocker.MagicMock(spec=discord.Message)
    guild_message.guild = mocker.MagicMock()

    await bot.on_message(guild_message)

    bot.process_commands.assert_called_once_with(guild_message)
