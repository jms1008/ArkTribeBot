"""Tests del caché compartido de consultas A2S en cogs.server_status."""
import pytest

from cogs import server_status as ss


@pytest.fixture(autouse=True)
def _clear_cache():
    """Asegura aislamiento entre tests limpiando el caché global del módulo."""
    ss._a2s_cache.clear()
    yield
    ss._a2s_cache.clear()


@pytest.mark.asyncio
async def test_returns_cached_within_ttl(mocker):
    """Si hay un valor cacheado fresco, no se llama a A2S."""
    fake_data = {"players": [], "info": None, "error": None}
    ss._a2s_cache[(1, "Ragnarok")] = {"data": fake_data, "ts": ss._time.time()}

    spy_fetch = mocker.patch(
        "cogs.server_status._fetch_single_server",
        side_effect=AssertionError("No debería llamarse"),
    )

    bot = mocker.MagicMock()
    bot.db_name = ":memory:"

    servers = {"Ragnarok": ("1.1.1.1", 27015)}
    result = await ss.query_all_servers(bot, 1, servers)
    assert result == {"Ragnarok": fake_data}
    spy_fetch.assert_not_called()


@pytest.mark.asyncio
async def test_refetches_when_cache_expired(mocker):
    """Si el caché ha expirado, vuelve a consultar A2S."""
    fake_old = {"players": [], "info": None, "error": None}
    # Marca de tiempo más antigua que el TTL.
    ss._a2s_cache[(1, "Ragnarok")] = {
        "data": fake_old,
        "ts": ss._time.time() - (ss._A2S_CACHE_TTL + 1),
    }

    fake_info = mocker.MagicMock(ping=0.05, max_players=70)
    fake_player = mocker.MagicMock(name_attr="P1", duration=12.0)
    fake_player.name = "P1"  # discord-style attribute, no propiedad name

    async def _fake_fetch(name, ip, port):
        return fake_info, [fake_player]

    mocker.patch("cogs.server_status._fetch_single_server", side_effect=_fake_fetch)

    bot = mocker.MagicMock()
    servers = {"Ragnarok": ("1.1.1.1", 27015)}
    result = await ss.query_all_servers(bot, 1, servers)

    assert result["Ragnarok"]["player_count"] == 1
    assert result["Ragnarok"]["players"][0]["name"] == "P1"
    # El caché se ha refrescado.
    assert ss._a2s_cache[(1, "Ragnarok")]["data"]["player_count"] == 1


@pytest.mark.asyncio
async def test_records_error_when_fetch_fails(mocker):
    """Si la consulta A2S explota, se devuelve un dict con 'error' no nulo."""
    async def _boom(name, ip, port):
        raise TimeoutError("simulated")

    mocker.patch("cogs.server_status._fetch_single_server", side_effect=_boom)

    bot = mocker.MagicMock()
    servers = {"Aberration": ("9.9.9.9", 27020)}
    result = await ss.query_all_servers(bot, 42, servers)

    assert result["Aberration"]["error"] == "simulated"
    assert result["Aberration"]["players"] == []
