import pytest
import asyncio
from unittest.mock import patch
from cogs.k4ultra import K4Ultra

# Setup del entorno asíncrono para pytest
pytestmark = pytest.mark.asyncio


class MockA2SPlayer:
    def __init__(self, name, duration):
        self.name = name
        self.duration = duration


@pytest.fixture
async def k4ultra_cog(mock_bot):
    await mock_bot.init_mock_db()
    cog = K4Ultra(mock_bot)
    cog.gather_player_data.cancel()  # Prevenir loop background
    cog.calculate_relationships.cancel()
    return cog


async def test_fetch_server_players_success(k4ultra_cog):
    """Prueba que el fetching de A2S sanitice correctamente los nombres."""
    mapa_prueba = "Gen2"

    mock_response = [
        MockA2SPlayer("R1OT ", 3600),  # Con espacio final (Bug original)
        MockA2SPlayer("", 100),  # Jugador anónimo (Steam privado)
        MockA2SPlayer("123", 200),  # Nombre normal
    ]

    with patch("cogs.k4ultra.a2s.players", return_value=mock_response):
        # A2s players is synchronous but wrapped in to_thread, so we patch the sync function
        mapa, valid_players = await k4ultra_cog.fetch_server_players(
            mapa_prueba, "127.0.0.1", 21000
        )

        assert mapa == mapa_prueba
        assert len(valid_players) == 2  # Uno anónimo descartado
        assert valid_players[0]["name"] == "R1OT"  # Espacio final limpiado por .strip()
        assert valid_players[1]["name"] == "123"


async def test_fetch_server_players_timeout(k4ultra_cog):
    """Prueba el comportamiento cuando el servidor no responde (timeout)."""

    def mock_timeout_players(addr):
        import time

        time.sleep(6)  # Lógico timeout de 5s
        return []

    # We patch a2s.players to raise asyncio.TimeoutError directly since it is what wait_for does internally when blocked
    with patch("cogs.k4ultra.a2s.players", side_effect=asyncio.TimeoutError("Timeout")):
        mapa, valid_players = await k4ultra_cog.fetch_server_players(
            "Aberration", "127.0.0.1", 21000
        )
        assert mapa == "Aberration"
        assert len(valid_players) == 0  # No crashea, devuelve lista vacía


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

    embed, messages_to_remove = await k4ultra_cog.generate_k4ultra_embed(123456)

    assert embed is not None
    assert type(messages_to_remove) is list
    assert "TRACKER" in embed.title.upper()
