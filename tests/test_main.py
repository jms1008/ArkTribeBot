import pytest
import discord
from discord.ext import commands
import sys
import os

from main import ArkTribeBot

@pytest.mark.asyncio
async def test_bot_initialization():
    """Test para verificar que el bot se puede instanciar correctamente y configurar."""
    bot = ArkTribeBot()
    assert bot.command_prefix == "!"
    assert bot.intents.message_content is True

@pytest.mark.asyncio
async def test_on_message_ignore_self(mocker):
    """Test para asegurar que el bot ignora sus propios mensajes."""
    bot = ArkTribeBot()
    
    # Mockear user property
    mock_user = discord.Object(id=123)
    mocker.patch.object(ArkTribeBot, 'user', new_callable=mocker.PropertyMock, return_value=mock_user)
    
    mock_message = mocker.MagicMock(spec=discord.Message)
    mock_message.author.id = 123 # Mismo ID que el bot
    
    # Mockear process_commands para ver si se llama
    bot.process_commands = mocker.AsyncMock()
    
    await bot.on_message(mock_message)
    
    # No se debería llamar a process_commands si el mensaje es del bot
    bot.process_commands.assert_not_called()
