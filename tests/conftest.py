import os
import sys

import discord
import pytest
from discord.ext import commands

# Asegurar que el entorno puede importar desde la raíz del proyecto
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


@pytest.fixture
def mock_bot():
    """Mock básico para representar al bot de Discord.

    El esquema de la DB se carga desde ``db/schema.py`` para garantizar que los tests
    siempre se ejecutan sobre el esquema real (no una copia divergente).
    """

    class MockBot(commands.Bot):
        def __init__(self):
            intents = discord.Intents.default()
            super().__init__(command_prefix="!", intents=intents)
            self.db_name = ":memory:"  # SQLite en memoria, aislado por test.

        @property
        def user(self):
            u = discord.Object(id=123)
            u.name = "TestBot"
            return u

        async def init_mock_db(self):
            """Crea el esquema real en la conexión :memory: del bot."""
            import aiosqlite

            from db.schema import create_indexes, create_tables, run_migrations

            # NOTA: para :memory: cada conexión es una BD nueva; en los tests que
            # reabren el fichero la conexión persistente se gestiona dentro del cog.
            async with aiosqlite.connect(self.db_name) as db:
                await create_tables(db)
                await run_migrations(db)
                await create_indexes(db)
                await db.commit()

    return MockBot()


@pytest.fixture
def mock_interaction(mocker):
    """Mock para discord.Interaction."""
    interaction = mocker.MagicMock(spec=discord.Interaction)
    interaction.guild_id = 1234567890
    interaction.channel_id = 987654321
    interaction.user = mocker.MagicMock(spec=discord.Member)
    interaction.user.id = 123456789
    interaction.user.name = "TestUser"
    interaction.response = mocker.AsyncMock()
    interaction.followup = mocker.AsyncMock()
    return interaction
