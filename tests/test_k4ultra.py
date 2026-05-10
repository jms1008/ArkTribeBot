import pytest
import asyncio
from unittest.mock import patch, MagicMock
from cogs.k4ultra import K4Ultra
from cogs.server_status import query_all_servers, _a2s_cache

# Setup del entorno asíncrono para pytest
pytestmark = pytest.mark.asyncio


class MockA2SPlayer:
    def __init__(self, name, duration):
        self.name = name
        self.duration = duration


class MockA2SInfo:
    def __init__(self, ping=0.15, max_players=70, map_name="Gen2"):
        self.ping = ping
        self.max_players = max_players
        self.map_name = map_name


@pytest.fixture
async def k4ultra_cog(mock_bot):
    await mock_bot.init_mock_db()
    cog = K4Ultra(mock_bot)
    cog.gather_player_data.cancel()  # Prevenir loop background
    cog.calculate_relationships.cancel()
    return cog


async def test_query_all_servers_success(mock_bot):
    """Prueba que query_all_servers sanitice nombres y devuelva datos correctos."""
    _a2s_cache.clear()

    mock_players = [
        MockA2SPlayer("R1OT ", 3600),  # Con espacio final
        MockA2SPlayer("", 100),         # Jugador anónimo (descartado)
        MockA2SPlayer("123", 200),      # Nombre normal
    ]
    mock_info = MockA2SInfo()

    servers = {"Gen2": ("127.0.0.1", 21000)}

    with patch("cogs.server_status.a2s.info", return_value=mock_info):
        with patch("cogs.server_status.a2s.players", return_value=mock_players):
            results = await query_all_servers(mock_bot, 12345, servers)

    assert "Gen2" in results
    data = results["Gen2"]
    assert data["error"] is None
    assert data["player_count"] == 2  # Uno anónimo descartado
    assert data["players"][0]["name"] == "R1OT"  # Espacio limpiado
    assert data["players"][1]["name"] == "123"


async def test_query_all_servers_timeout(mock_bot):
    """Prueba el comportamiento cuando el servidor no responde (timeout)."""
    _a2s_cache.clear()

    servers = {"Aberration": ("127.0.0.1", 21000)}

    with patch("cogs.server_status.a2s.info", side_effect=asyncio.TimeoutError("Timeout")):
        results = await query_all_servers(mock_bot, 12345, servers)

    assert "Aberration" in results
    data = results["Aberration"]
    assert data["error"] is not None  # Error registrado, no crash
    assert len(data["players"]) == 0


async def test_generate_k4ultra_embed(k4ultra_cog, mock_bot, mocker):
    """Test para verificar que el generador de Embeds de K4Ultra interactúa bien con la DB ficticia y no crashea sin base de datos real."""

    # Insertar jugador conectado manualmente Mockeado
    mock_db = mocker.patch("cogs.k4ultra.aiosqlite.connect")
    mock_db.return_value = mocker.AsyncMock()

    # Sobrescribir retorno del execute fetch
    mock_execute = mocker.AsyncMock()
    mock_execute.fetchall.return_value = [
        ("R1OT", "Gen2", "2026-03-08T12:00:00.000000", 1)
    ]
    mock_db.return_value.execute.return_value = mock_execute

    pages, top_players, aliases = await k4ultra_cog.generate_k4ultra_embed(123456, mode="radar")
    assert pages is not None
    assert len(pages) >= 1
    assert "TRACKER" in pages[0].title.upper()

    pages_t, top_t, aliases_t = await k4ultra_cog.generate_k4ultra_embed(123456, mode="tribus")
    assert pages_t is not None
    assert len(pages_t) == 1
    assert "TRIBUS" in pages_t[0].title.upper()
