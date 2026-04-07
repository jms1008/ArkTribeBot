import pytest
import discord

from main import ArkTribeBot
from cogs.log_processor import LogProcessor


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
