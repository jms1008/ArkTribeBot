import os
import sys

import discord
import pytest
from discord.ext import commands

# Asegurar que el entorno puede importar desde la raíz del proyecto
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


@pytest.fixture
def mock_bot(tmp_path):
    """Mock básico para representar al bot de Discord.

    - El esquema de la DB se carga desde ``db/schema.py`` (no copia divergente).
    - ``init_mock_db()`` (async) inicializa esquema **y** abre ``bot.db``
      (conexión persistente real) sobre un fichero temporal — los cogs migrados
      a la fase 3 SQLite la consultan directamente.
    """
    db_path = str(tmp_path / "mock.db")

    class MockBot(commands.Bot):
        def __init__(self):
            intents = discord.Intents.default()
            super().__init__(command_prefix="!", intents=intents)
            self.db_name = db_path
            self.db = None
            # log_filename lo consume Breeding.log_mutation para crear el FileHandler
            # por guild. En tests apuntamos a un fichero dentro de tmp_path.
            self.log_filename = str(tmp_path / "bot.log")

        @property
        def user(self):
            u = discord.Object(id=123)
            u.name = "TestBot"
            return u

        async def init_mock_db(self):
            """Crea esquema + abre la conexión persistente (bot.db)."""
            import aiosqlite

            from db.database import Database
            from db.schema import create_indexes, create_tables, run_migrations

            async with aiosqlite.connect(self.db_name) as db:
                await create_tables(db)
                await run_migrations(db)
                await create_indexes(db)
                await db.commit()

            self.db = Database(self.db_name)
            await self.db.connect()

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
