import pytest
import discord
from discord.ext import commands
import sys
import os

# Asegurar que el entorno puede importar desde la raíz del proyecto
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

@pytest.fixture
def mock_bot():
    """Mock básico para representar al bot de discord."""
    class MockBot(commands.Bot):
        def __init__(self):
            intents = discord.Intents.default()
            super().__init__(command_prefix="!", intents=intents)
            self.db_name = ":memory:" # Usar base de datos en memoria para los tests

        @property
        def user(self):
            u = discord.Object(id=123)
            u.name = "TestBot"
            return u
            
        async def init_mock_db(self):
            # Copia simplificada de main.py init_db para K4Ultra y el resto de cogs
            import aiosqlite
            async with aiosqlite.connect(self.db_name) as db:
                await db.execute("CREATE TABLE IF NOT EXISTS k4ultra_sessions (id INTEGER PRIMARY KEY AUTOINCREMENT, player_name TEXT, map_name TEXT, start_time DATETIME, end_time DATETIME, is_active INTEGER DEFAULT 1)")
                await db.execute("CREATE TABLE IF NOT EXISTS k4ultra_players_log (id INTEGER PRIMARY KEY AUTOINCREMENT, player_name TEXT, map_name TEXT, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)")
                await db.execute("CREATE TABLE IF NOT EXISTS k4ultra_playtime (id INTEGER PRIMARY KEY AUTOINCREMENT, player_name TEXT, map_name TEXT, total_minutes INTEGER DEFAULT 0, last_seen DATETIME)")
                await db.execute("CREATE TABLE IF NOT EXISTS k4ultra_relationships (id INTEGER PRIMARY KEY AUTOINCREMENT, player1 TEXT, player2 TEXT, probability_score INTEGER DEFAULT 0, is_manual INTEGER DEFAULT 0, UNIQUE(player1, player2))")
                
                # Tablas adicionales requeridas por otros tests (Warfare, Admin, Scouting, etc.)
                await db.execute("CREATE TABLE IF NOT EXISTS blacklist (id INTEGER PRIMARY KEY, jugador TEXT, tribu TEXT, mapa TEXT, notas TEXT, added_by TEXT, added_at DATETIME)")
                await db.execute("CREATE TABLE IF NOT EXISTS scouts (id INTEGER PRIMARY KEY AUTOINCREMENT, tribu TEXT, server TEXT, coords TEXT, threat_level INTEGER, notas TEXT, image_url TEXT, added_by TEXT, added_at DATETIME)")
                await db.execute("CREATE TABLE IF NOT EXISTS point_subscriptions (user_id INTEGER PRIMARY KEY, hour INTEGER, timezone TEXT)")
                
                await db.commit()
    return MockBot()

@pytest.fixture
def mock_interaction(mocker):
    """Mock para discord.Interaction."""
    interaction = mocker.MagicMock(spec=discord.Interaction)
    interaction.user = mocker.MagicMock(spec=discord.Member)
    interaction.user.id = 123456789
    interaction.user.name = "TestUser"
    interaction.response = mocker.AsyncMock()
    interaction.followup = mocker.AsyncMock()
    return interaction
